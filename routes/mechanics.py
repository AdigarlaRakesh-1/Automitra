from decimal import Decimal
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, Mechanic, ServiceDetail

mechanics_bp = Blueprint('mechanics', __name__, url_prefix='/mechanics')

@mechanics_bp.route('/')
def index():
    status_filter = request.args.get('status', '').strip()
    query = Mechanic.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    mechanics = query.order_by(Mechanic.name.asc()).all()
    return render_template('mechanics/index.html', mechanics=mechanics, status_filter=status_filter)

@mechanics_bp.route('/allocation')
def allocation():
    """Visual mechanic allocation view for service managers."""
    mechanics = Mechanic.query.all()
    active_jobs = ServiceDetail.query.filter(ServiceDetail.status.in_(['Assigned', 'In Progress', 'Awaiting Parts'])).all()
    unassigned_jobs = ServiceDetail.query.filter(ServiceDetail.mechanic_id.is_(None)).all()
    return render_template('mechanics/allocation.html', mechanics=mechanics, active_jobs=active_jobs, unassigned_jobs=unassigned_jobs)

ALLOWED_MECHANIC_STATUSES = {'Available', 'Busy', 'On Leave'}

@mechanics_bp.route('/new', methods=['GET', 'POST'])
def new_mechanic():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        specialty = request.form.get('specialty', '').strip()
        status = request.form.get('status', 'Available')

        if not name or not phone or not specialty:
            flash('Name, phone, and primary specialty are required.', 'danger')
            return render_template('mechanics/form.html', mechanic=None, action='Add New')

        if status not in ALLOWED_MECHANIC_STATUSES:
            flash(f'Invalid mechanic status "{status}". Allowed: {", ".join(sorted(ALLOWED_MECHANIC_STATUSES))}.', 'danger')
            return render_template('mechanics/form.html', mechanic=None, action='Add New')

        try:
            raw_rate = request.form.get('hourly_rate', '45.00')
            hourly_rate = Decimal(str(raw_rate)).quantize(Decimal('0.01'))
            if hourly_rate < Decimal('0.00'):
                flash('Hourly rate cannot be negative.', 'danger')
                return render_template('mechanics/form.html', mechanic=None, action='Add New')
        except Exception:
            flash('Hourly rate must be a valid non-negative number.', 'danger')
            return render_template('mechanics/form.html', mechanic=None, action='Add New')

        try:
            m = Mechanic(
                name=name,
                phone=phone,
                specialty=specialty,
                status=status,
                hourly_rate=hourly_rate
            )
            db.session.add(m)
            db.session.commit()
            flash(f'Mechanic {m.name} registered successfully!', 'success')
            return redirect(url_for('mechanics.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding mechanic: {str(e)}', 'danger')

    return render_template('mechanics/form.html', mechanic=None, action='Add New')

@mechanics_bp.route('/<int:mechanic_id>/edit', methods=['GET', 'POST'])
def edit_mechanic(mechanic_id):
    mechanic = Mechanic.query.get_or_404(mechanic_id)
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        specialty = request.form.get('specialty', '').strip()
        status = request.form.get('status', 'Available')

        if not name or not phone or not specialty:
            flash('Name, phone, and primary specialty are required.', 'danger')
            return render_template('mechanics/form.html', mechanic=mechanic, action='Edit')

        if status not in ALLOWED_MECHANIC_STATUSES:
            flash(f'Invalid mechanic status "{status}". Allowed: {", ".join(sorted(ALLOWED_MECHANIC_STATUSES))}.', 'danger')
            return render_template('mechanics/form.html', mechanic=mechanic, action='Edit')

        try:
            raw_rate = request.form.get('hourly_rate', '45.00')
            hourly_rate = Decimal(str(raw_rate)).quantize(Decimal('0.01'))
            if hourly_rate < Decimal('0.00'):
                flash('Hourly rate cannot be negative.', 'danger')
                return render_template('mechanics/form.html', mechanic=mechanic, action='Edit')
        except Exception:
            flash('Hourly rate must be a valid non-negative number.', 'danger')
            return render_template('mechanics/form.html', mechanic=mechanic, action='Edit')

        try:
            mechanic.name = name
            mechanic.phone = phone
            mechanic.specialty = specialty
            mechanic.status = status
            mechanic.hourly_rate = hourly_rate
            db.session.commit()
            flash('Mechanic profile updated.', 'success')
            return redirect(url_for('mechanics.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating mechanic: {str(e)}', 'danger')

    return render_template('mechanics/form.html', mechanic=mechanic, action='Edit')

@mechanics_bp.route('/<int:mechanic_id>/status', methods=['POST'])
def update_status(mechanic_id):
    mechanic = Mechanic.query.get_or_404(mechanic_id)
    new_status = request.form.get('status')
    if new_status in ALLOWED_MECHANIC_STATUSES:
        mechanic.status = new_status
        db.session.commit()
        flash(f'Updated status for {mechanic.name} to "{new_status}".', 'info')
    else:
        flash(f'Invalid mechanic status "{new_status}".', 'danger')
    return redirect(request.referrer or url_for('mechanics.index'))

@mechanics_bp.route('/<int:mechanic_id>')
def view_mechanic(mechanic_id):
    mechanic = Mechanic.query.get_or_404(mechanic_id)
    assigned_jobs = ServiceDetail.query.filter_by(mechanic_id=mechanic.id).order_by(ServiceDetail.id.desc()).all()
    return render_template('mechanics/view.html', mechanic=mechanic, assigned_jobs=assigned_jobs)
