import random
from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, ServiceBooking, ServiceDetail, Customer, Vehicle, Mechanic

bookings_bp = Blueprint('bookings', __name__, url_prefix='/bookings')

def generate_booking_number():
    year = datetime.utcnow().year
    rand_num = random.randint(10000, 99999)
    return f"BK-{year}-{rand_num}"

@bookings_bp.route('/')
def index():
    status_filter = request.args.get('status', '').strip()
    date_filter = request.args.get('date', '').strip()
    
    query = ServiceBooking.query.join(Customer).join(Vehicle)
    
    if status_filter:
        query = query.filter(ServiceBooking.status == status_filter)
    if date_filter:
        try:
            d = datetime.strptime(date_filter, '%Y-%m-%d').date()
            query = query.filter(ServiceBooking.booking_date == d)
        except ValueError:
            pass
            
    bookings = query.order_by(ServiceBooking.booking_date.desc(), ServiceBooking.booking_time.asc()).all()
    today = date.today()
    
    return render_template('bookings/index.html', bookings=bookings, status_filter=status_filter, date_filter=date_filter, today=today)

@bookings_bp.route('/missed')
def missed():
    """Dedicated Missed Bookings management center to prevent missed revenue and follow up."""
    today = date.today()
    missed_bookings = ServiceBooking.query.filter(
        (ServiceBooking.status == 'Missed') |
        ((ServiceBooking.booking_date < today) & (ServiceBooking.status.in_(['Pending', 'Confirmed'])))
    ).order_by(ServiceBooking.booking_date.desc()).all()
    
    return render_template('bookings/missed.html', missed_bookings=missed_bookings, today=today)

@bookings_bp.route('/new', methods=['GET', 'POST'])
def new_booking():
    customers = Customer.query.order_by(Customer.name.asc()).all()
    preselected_customer_id = request.args.get('customer_id', type=int)
    preselected_vehicle_id = request.args.get('vehicle_id', type=int)
    
    # Mechanics for immediate allocation if desired
    mechanics = Mechanic.query.filter_by(status='Available').all()

    if request.method == 'POST':
        c_id = request.form.get('customer_id', type=int)
        v_id = request.form.get('vehicle_id', type=int)
        booking_date_str = request.form.get('booking_date', '').strip()
        booking_time = request.form.get('booking_time', '').strip()
        service_type = request.form.get('service_type', '').strip()
        notes = request.form.get('notes', '').strip()
        initial_mechanic_id = request.form.get('mechanic_id', type=int)

        if not c_id or not v_id or not booking_date_str or not booking_time or not service_type:
            flash('Customer, vehicle, booking date, time, and service type are all required.', 'danger')
            return render_template('bookings/form.html', customers=customers, mechanics=mechanics, preselected_customer_id=c_id, preselected_vehicle_id=v_id)

        try:
            b_date = datetime.strptime(booking_date_str, '%Y-%m-%d').date()
            booking_number = generate_booking_number()

            # Ensure unique booking number
            while ServiceBooking.query.filter_by(booking_number=booking_number).first():
                booking_number = generate_booking_number()

            booking = ServiceBooking(
                booking_number=booking_number,
                customer_id=c_id,
                vehicle_id=v_id,
                booking_date=b_date,
                booking_time=booking_time,
                service_type=service_type,
                status='Confirmed',
                notes=notes or None
            )
            db.session.add(booking)
            db.session.flush()

            # Pre-create ServiceDetail job slot if mechanic or job description provided
            service_detail = ServiceDetail(
                booking_id=booking.id,
                mechanic_id=initial_mechanic_id or None,
                job_description=f"Initial booking for: {service_type}. {notes}".strip(),
                status='Assigned' if initial_mechanic_id else 'Assigned'
            )
            db.session.add(service_detail)

            # If mechanic assigned, update mechanic status to Busy
            if initial_mechanic_id:
                m = db.session.get(Mechanic, initial_mechanic_id)
                if m:
                    m.status = 'Busy'

            db.session.commit()
            flash(f'Service Booking #{booking.booking_number} successfully scheduled!', 'success')
            return redirect(url_for('bookings.view_booking', booking_id=booking.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating booking: {str(e)}', 'danger')

    return render_template('bookings/form.html', customers=customers, mechanics=mechanics, preselected_customer_id=preselected_customer_id, preselected_vehicle_id=preselected_vehicle_id)

@bookings_bp.route('/<int:booking_id>')
def view_booking(booking_id):
    booking = ServiceBooking.query.get_or_404(booking_id)
    mechanics = Mechanic.query.all()
    return render_template('bookings/view.html', booking=booking, mechanics=mechanics)

@bookings_bp.route('/<int:booking_id>/status', methods=['POST'])
def update_status(booking_id):
    booking = ServiceBooking.query.get_or_404(booking_id)
    new_status = request.form.get('status')
    
    if new_status in ['Pending', 'Confirmed', 'In Progress', 'Completed', 'Cancelled', 'Missed']:
        booking.status = new_status
        # Ensure service detail exists if moving to In Progress
        if new_status == 'In Progress' and not booking.service_detail:
            detail = ServiceDetail(
                booking_id=booking.id,
                job_description=booking.service_type,
                status='In Progress',
                started_at=datetime.utcnow()
            )
            db.session.add(detail)
        elif new_status == 'In Progress' and booking.service_detail:
            booking.service_detail.status = 'In Progress'
            if not booking.service_detail.started_at:
                booking.service_detail.started_at = datetime.utcnow()
        elif new_status == 'Completed' and booking.service_detail:
            booking.service_detail.status = 'Completed'
            booking.service_detail.completed_at = datetime.utcnow()

        db.session.commit()
        flash(f'Booking #{booking.booking_number} status updated to "{new_status}".', 'info')
    
    return redirect(request.referrer or url_for('bookings.view_booking', booking_id=booking.id))

@bookings_bp.route('/<int:booking_id>/reschedule', methods=['POST'])
def reschedule(booking_id):
    booking = ServiceBooking.query.get_or_404(booking_id)
    new_date_str = request.form.get('reschedule_date')
    new_time = request.form.get('reschedule_time')

    if not new_date_str or not new_time:
        flash('New date and time are required to reschedule.', 'warning')
        return redirect(request.referrer or url_for('bookings.view_booking', booking_id=booking.id))

    try:
        new_date = datetime.strptime(new_date_str, '%Y-%m-%d').date()
        booking.booking_date = new_date
        booking.booking_time = new_time
        booking.status = 'Confirmed'
        db.session.commit()
        flash(f'Booking #{booking.booking_number} rescheduled to {new_date.strftime("%b %d, %Y")} at {new_time}!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error rescheduling: {str(e)}', 'danger')

    return redirect(url_for('bookings.view_booking', booking_id=booking.id))
