from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, Vehicle, Customer, ServiceBooking

vehicles_bp = Blueprint('vehicles', __name__, url_prefix='/vehicles')

@vehicles_bp.route('/')
def index():
    search = request.args.get('search', '').strip()
    query = Vehicle.query.join(Customer)
    if search:
        query = query.filter(
            (Vehicle.license_plate.ilike(f'%{search}%')) |
            (Vehicle.make.ilike(f'%{search}%')) |
            (Vehicle.model.ilike(f'%{search}%')) |
            (Vehicle.vin.ilike(f'%{search}%')) |
            (Customer.name.ilike(f'%{search}%'))
        )
    vehicles = query.order_by(Vehicle.id.desc()).all()
    return render_template('vehicles/index.html', vehicles=vehicles, search=search)

@vehicles_bp.route('/new', methods=['GET', 'POST'])
def new_vehicle():
    customer_id = request.args.get('customer_id', type=int)
    customers = Customer.query.order_by(Customer.name.asc()).all()

    if request.method == 'POST':
        c_id = request.form.get('customer_id', type=int)
        license_plate = request.form.get('license_plate', '').strip().upper()
        make = request.form.get('make', '').strip()
        model = request.form.get('model', '').strip()
        year = request.form.get('year', type=int)
        vin = request.form.get('vin', '').strip()
        mileage = request.form.get('mileage', type=int) or 0
        fuel_type = request.form.get('fuel_type', 'Petrol')
        color = request.form.get('color', '').strip()

        if not c_id or not license_plate or not make or not model or not year:
            flash('Customer, license plate, make, model, and year are required.', 'danger')
            return render_template('vehicles/form.html', vehicle=None, customers=customers, selected_customer_id=c_id, action='Add')

        # Check existing license plate
        existing = Vehicle.query.filter_by(license_plate=license_plate).first()
        if existing:
            flash(f'Vehicle with license plate "{license_plate}" is already registered to {existing.customer.name} (ID #{existing.customer.id}).', 'danger')
            return render_template('vehicles/form.html', vehicle=None, customers=customers, selected_customer_id=c_id, action='Add')

        try:
            vehicle = Vehicle(
                customer_id=c_id,
                license_plate=license_plate,
                make=make,
                model=model,
                year=year,
                vin=vin or None,
                mileage=mileage,
                fuel_type=fuel_type,
                color=color or None
            )
            db.session.add(vehicle)
            db.session.commit()
            flash(f'Vehicle {vehicle.make} {vehicle.model} ({vehicle.license_plate}) added successfully!', 'success')
            return redirect(url_for('vehicles.view_vehicle', vehicle_id=vehicle.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error registering vehicle: {str(e)}', 'danger')

    return render_template('vehicles/form.html', vehicle=None, customers=customers, selected_customer_id=customer_id, action='Add')

@vehicles_bp.route('/<int:vehicle_id>')
def view_vehicle(vehicle_id):
    vehicle = Vehicle.query.get_or_404(vehicle_id)
    # Service history tracking: full log of services, mechanic notes, and parts replaced
    service_history = ServiceBooking.query.filter_by(vehicle_id=vehicle.id).order_by(ServiceBooking.booking_date.desc()).all()
    return render_template('vehicles/view.html', vehicle=vehicle, service_history=service_history)

@vehicles_bp.route('/<int:vehicle_id>/edit', methods=['GET', 'POST'])
def edit_vehicle(vehicle_id):
    vehicle = Vehicle.query.get_or_404(vehicle_id)
    customers = Customer.query.order_by(Customer.name.asc()).all()

    if request.method == 'POST':
        license_plate = request.form.get('license_plate', '').strip().upper()
        make = request.form.get('make', '').strip()
        model = request.form.get('model', '').strip()
        year = request.form.get('year', type=int)
        vin = request.form.get('vin', '').strip()
        mileage = request.form.get('mileage', type=int) or 0
        fuel_type = request.form.get('fuel_type', 'Petrol')
        color = request.form.get('color', '').strip()

        # Check license plate uniqueness
        existing = Vehicle.query.filter(Vehicle.license_plate == license_plate, Vehicle.id != vehicle.id).first()
        if existing:
            flash(f'License plate "{license_plate}" is already used by vehicle #{existing.id}.', 'danger')
            return render_template('vehicles/form.html', vehicle=vehicle, customers=customers, selected_customer_id=vehicle.customer_id, action='Edit')

        try:
            vehicle.license_plate = license_plate
            vehicle.make = make
            vehicle.model = model
            vehicle.year = year
            vehicle.vin = vin or None
            vehicle.mileage = mileage
            vehicle.fuel_type = fuel_type
            vehicle.color = color or None
            db.session.commit()
            flash('Vehicle information updated successfully!', 'success')
            return redirect(url_for('vehicles.view_vehicle', vehicle_id=vehicle.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating vehicle: {str(e)}', 'danger')

    return render_template('vehicles/form.html', vehicle=vehicle, customers=customers, selected_customer_id=vehicle.customer_id, action='Edit')

@vehicles_bp.route('/<int:vehicle_id>/delete', methods=['POST'])
def delete_vehicle(vehicle_id):
    vehicle = Vehicle.query.get_or_404(vehicle_id)
    c_id = vehicle.customer_id

    # Protect vehicles with historical bookings or service records
    if vehicle.bookings:
        flash(f'Cannot delete vehicle "{vehicle.license_plate}" because it has {len(vehicle.bookings)} historical service booking(s).', 'danger')
        return redirect(url_for('vehicles.view_vehicle', vehicle_id=vehicle.id))

    try:
        db.session.delete(vehicle)
        db.session.commit()
        flash('Vehicle removed.', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'Cannot delete vehicle: {str(e)}', 'danger')
    return redirect(url_for('customers.view_customer', customer_id=c_id))
