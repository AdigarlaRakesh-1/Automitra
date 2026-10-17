from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from models import db, Customer, Vehicle, ServiceBooking, Bill

customers_bp = Blueprint('customers', __name__, url_prefix='/customers')

@customers_bp.route('/')
def index():
    search = request.args.get('search', '').strip()
    query = Customer.query
    if search:
        query = query.filter(
            (Customer.name.ilike(f'%{search}%')) |
            (Customer.phone.ilike(f'%{search}%')) |
            (Customer.email.ilike(f'%{search}%'))
        )
    customers = query.order_by(Customer.id.desc()).all()
    return render_template('customers/index.html', customers=customers, search=search)

@customers_bp.route('/new', methods=['GET', 'POST'])
def new_customer():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()
        address = request.form.get('address', '').strip()

        if not name or not phone:
            flash('Customer name and phone number are required.', 'danger')
            return render_template('customers/form.html', customer=None, action='Add New')

        # Check for duplicate customer
        duplicate = Customer.check_duplicate(phone, email)
        if duplicate:
            flash(f'Duplicate detected! A customer already exists with phone "{duplicate.phone}" or email "{duplicate.email}": {duplicate.name} (ID #{duplicate.id}).', 'warning')
            return render_template('customers/form.html', customer=None, action='Add New', duplicate=duplicate, form_data=request.form)

        try:
            new_c = Customer(name=name, phone=phone, email=email or None, address=address or None)
            db.session.add(new_c)
            db.session.commit()
            flash(f'Customer "{new_c.name}" registered successfully!', 'success')
            return redirect(url_for('customers.view_customer', customer_id=new_c.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Database error: {str(e)}', 'danger')

    return render_template('customers/form.html', customer=None, action='Add New')

@customers_bp.route('/<int:customer_id>')
def view_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    # Complete service history timeline
    bookings = ServiceBooking.query.filter_by(customer_id=customer_id).order_by(ServiceBooking.booking_date.desc()).all()
    bills = Bill.query.filter_by(customer_id=customer_id).order_by(Bill.issued_at.desc()).all()
    total_spent = sum(float(b.grand_total) for b in bills if b.payment_status == 'Paid')
    
    return render_template(
        'customers/view.html',
        customer=customer,
        bookings=bookings,
        bills=bills,
        total_spent=total_spent
    )

@customers_bp.route('/<int:customer_id>/edit', methods=['GET', 'POST'])
def edit_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()
        address = request.form.get('address', '').strip()

        if not name or not phone:
            flash('Customer name and phone are required.', 'danger')
            return render_template('customers/form.html', customer=customer, action='Edit')

        duplicate = Customer.check_duplicate(phone, email, exclude_id=customer_id)
        if duplicate:
            flash(f'Duplicate detected! Another customer ({duplicate.name}, #{duplicate.id}) already uses phone "{phone}" or email "{email}".', 'warning')
            return render_template('customers/form.html', customer=customer, action='Edit', duplicate=duplicate)

        try:
            customer.name = name
            customer.phone = phone
            customer.email = email or None
            customer.address = address or None
            db.session.commit()
            flash('Customer updated successfully!', 'success')
            return redirect(url_for('customers.view_customer', customer_id=customer.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating customer: {str(e)}', 'danger')

    return render_template('customers/form.html', customer=customer, action='Edit')

@customers_bp.route('/<int:customer_id>/delete', methods=['POST'])
def delete_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)

    # Protect customers with historical bills or invoices
    if customer.bills:
        flash(f'Cannot delete customer "{customer.name}" because they have {len(customer.bills)} historical invoices/bills. Records must be preserved for accounting audits.', 'danger')
        return redirect(url_for('customers.view_customer', customer_id=customer.id))

    # Protect customers with active bookings
    active_bookings = [b for b in customer.bookings if b.status in ['Pending', 'Confirmed', 'In Progress']]
    if active_bookings:
        flash(f'Cannot delete customer "{customer.name}" because they have {len(active_bookings)} active service booking(s).', 'danger')
        return redirect(url_for('customers.view_customer', customer_id=customer.id))

    # Protect customers with vehicles having service history
    vehicles_with_history = [v for v in customer.vehicles if v.bookings]
    if vehicles_with_history:
        flash(f'Cannot delete customer "{customer.name}" because their vehicles have recorded service history.', 'danger')
        return redirect(url_for('customers.view_customer', customer_id=customer.id))

    try:
        db.session.delete(customer)
        db.session.commit()
        flash(f'Customer {customer.name} and unreferenced records deleted.', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'Cannot delete customer: {str(e)}', 'danger')
    return redirect(url_for('customers.index'))
