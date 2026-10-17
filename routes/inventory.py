from decimal import Decimal
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, SparePart, PartUsage

inventory_bp = Blueprint('inventory', __name__, url_prefix='/inventory')

@inventory_bp.route('/')
def index():
    search = request.args.get('search', '').strip()
    category = request.args.get('category', '').strip()
    stock_status = request.args.get('status', '').strip()

    query = SparePart.query
    if search:
        query = query.filter(
            (SparePart.part_number.ilike(f'%{search}%')) |
            (SparePart.name.ilike(f'%{search}%')) |
            (SparePart.location_bin.ilike(f'%{search}%'))
        )
    if category:
        query = query.filter(SparePart.category == category)
    if stock_status == 'low':
        query = query.filter(SparePart.stock_quantity <= SparePart.min_reorder_level)
    elif stock_status == 'out':
        query = query.filter(SparePart.stock_quantity == 0)

    parts = query.order_by(SparePart.name.asc()).all()
    categories = db.session.query(SparePart.category).distinct().all()
    categories = [c[0] for c in categories if c[0]]

    # Low stock counter
    low_stock_count = SparePart.query.filter(SparePart.stock_quantity <= SparePart.min_reorder_level).count()

    return render_template(
        'inventory/index.html',
        parts=parts,
        categories=categories,
        search=search,
        selected_category=category,
        stock_status=stock_status,
        low_stock_count=low_stock_count
    )

@inventory_bp.route('/low_stock')
def low_stock():
    """Dedicated low stock alert and reordering page."""
    low_stock_parts = SparePart.query.filter(SparePart.stock_quantity <= SparePart.min_reorder_level).order_by(SparePart.stock_quantity.asc()).all()
    return render_template('inventory/low_stock.html', parts=low_stock_parts)

@inventory_bp.route('/new', methods=['GET', 'POST'])
def new_part():
    if request.method == 'POST':
        part_number = request.form.get('part_number', '').strip().upper()
        name = request.form.get('name', '').strip()
        category = request.form.get('category', '').strip()
        try:
            raw_cost = request.form.get('cost_price', '0')
            cost_price = Decimal(str(raw_cost)) if str(raw_cost).strip() != '' else Decimal('0.00')
            raw_selling = request.form.get('selling_price', '0')
            selling_price = Decimal(str(raw_selling)) if str(raw_selling).strip() != '' else Decimal('0.00')
            stock_quantity = int(request.form.get('stock_quantity', '0'))
            min_reorder_level = int(request.form.get('min_reorder_level', '5'))

            if cost_price < 0 or selling_price < 0 or stock_quantity < 0 or min_reorder_level < 0:
                flash('Prices, stock quantity, and reorder level cannot be negative.', 'danger')
                return render_template('inventory/form.html', part=None, action='Add New')
        except (ValueError, TypeError, Exception):
            flash('Invalid numeric values for prices or stock quantities.', 'danger')
            return render_template('inventory/form.html', part=None, action='Add New')

        existing = SparePart.query.filter_by(part_number=part_number).first()
        if existing:
            flash(f'Part number "{part_number}" already exists: {existing.name}.', 'danger')
            return render_template('inventory/form.html', part=None, action='Add New')

        try:
            part = SparePart(
                part_number=part_number,
                name=name,
                category=category,
                cost_price=cost_price,
                selling_price=selling_price,
                stock_quantity=stock_quantity,
                min_reorder_level=min_reorder_level,
                location_bin=location_bin or None
            )
            db.session.add(part)
            db.session.commit()
            flash(f'Spare part "{part.name}" ({part.part_number}) added to inventory!', 'success')
            return redirect(url_for('inventory.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding spare part: {str(e)}', 'danger')

    return render_template('inventory/form.html', part=None, action='Add New')

@inventory_bp.route('/<int:part_id>/edit', methods=['GET', 'POST'])
def edit_part(part_id):
    part = SparePart.query.get_or_404(part_id)
    if request.method == 'POST':
        part_number = request.form.get('part_number', '').strip().upper()
        name = request.form.get('name', '').strip()
        category = request.form.get('category', '').strip()
        location_bin = request.form.get('location_bin', '').strip()

        if not part_number or not name or not category:
            flash('Part number, name, and category are required.', 'danger')
            return render_template('inventory/form.html', part=part, action='Edit')

        try:
            raw_cost = request.form.get('cost_price', '0')
            cost_price = Decimal(str(raw_cost)) if str(raw_cost).strip() != '' else Decimal('0.00')
            raw_selling = request.form.get('selling_price', '0')
            selling_price = Decimal(str(raw_selling)) if str(raw_selling).strip() != '' else Decimal('0.00')
            stock_quantity = int(request.form.get('stock_quantity', '0'))
            min_reorder_level = int(request.form.get('min_reorder_level', '5'))

            if cost_price < 0 or selling_price < 0 or stock_quantity < 0 or min_reorder_level < 0:
                flash('Prices, stock quantity, and reorder level cannot be negative.', 'danger')
                return render_template('inventory/form.html', part=part, action='Edit')
        except (ValueError, TypeError, Exception):
            flash('Invalid numeric values for prices or stock quantities.', 'danger')
            return render_template('inventory/form.html', part=part, action='Edit')

        # Uniqueness check
        existing = SparePart.query.filter(SparePart.part_number == part_number, SparePart.id != part.id).first()
        if existing:
            flash(f'Part number "{part_number}" is already used by "{existing.name}".', 'danger')
            return render_template('inventory/form.html', part=part, action='Edit')

        try:
            part.part_number = part_number
            part.name = name
            part.category = category
            part.cost_price = cost_price
            part.selling_price = selling_price
            part.stock_quantity = stock_quantity
            part.min_reorder_level = min_reorder_level
            part.location_bin = location_bin or None
            db.session.commit()
            flash(f'Spare part "{part.name}" updated successfully.', 'success')
            return redirect(url_for('inventory.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating part: {str(e)}', 'danger')

    return render_template('inventory/form.html', part=part, action='Edit')

@inventory_bp.route('/<int:part_id>/restock', methods=['POST'])
def restock_part(part_id):
    part = SparePart.query.get_or_404(part_id)
    try:
        added_qty = int(request.form.get('quantity', '0'))
    except (ValueError, TypeError):
        added_qty = 0

    if added_qty <= 0:
        flash('Restock quantity must be positive.', 'warning')
        return redirect(request.referrer or url_for('inventory.index'))

    try:
        db.session.query(SparePart).filter(SparePart.id == part.id).update(
            {SparePart.stock_quantity: SparePart.stock_quantity + added_qty},
            synchronize_session='fetch'
        )
        db.session.commit()
        part = db.session.get(SparePart, part_id)
        flash(f'Successfully restocked {part.name} (+{added_qty}). New Stock: {part.stock_quantity} units.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error restocking part: {str(e)}', 'danger')

    return redirect(request.referrer or url_for('inventory.index'))

@inventory_bp.route('/<int:part_id>/delete', methods=['POST'])
def delete_part(part_id):
    part = SparePart.query.get_or_404(part_id)
    # Check if part has existing usage history
    if part.usages:
        flash(f'Cannot delete part "{part.name}" because it is linked to {len(part.usages)} historical service orders. Adjust stock to 0 instead.', 'danger')
        return redirect(url_for('inventory.index'))

    try:
        db.session.delete(part)
        db.session.commit()
        flash(f'Part "{part.name}" removed from inventory.', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting part: {str(e)}', 'danger')

    return redirect(url_for('inventory.index'))
