from datetime import date, datetime
from flask import Blueprint, render_template
from sqlalchemy import func
from models import db, Customer, Vehicle, Mechanic, ServiceBooking, ServiceDetail, SparePart, Bill, Payment

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def dashboard():
    today = date.today()
    
    # 1. High-level KPIs
    total_customers = Customer.query.count()
    total_vehicles = Vehicle.query.count()
    total_mechanics = Mechanic.query.count()
    available_mechanics = Mechanic.query.filter_by(status='Available').count()
    
    # Active jobs in workshop floor
    active_jobs = ServiceDetail.query.filter(ServiceDetail.status.in_(['Assigned', 'In Progress', 'Awaiting Parts'])).count()
    
    # Bookings today & pending
    bookings_today = ServiceBooking.query.filter_by(booking_date=today).count()
    pending_bookings = ServiceBooking.query.filter_by(status='Pending').count()
    
    # Missed bookings detection
    # Either explicitly marked 'Missed' or date < today and status still 'Pending' / 'Confirmed'
    missed_bookings_count = ServiceBooking.query.filter(
        (ServiceBooking.status == 'Missed') | 
        ((ServiceBooking.booking_date < today) & (ServiceBooking.status.in_(['Pending', 'Confirmed'])))
    ).count()
    
    # Low-stock spare parts
    low_stock_parts = SparePart.query.filter(SparePart.stock_quantity <= SparePart.min_reorder_level).all()
    low_stock_count = len(low_stock_parts)
    
    # Financial metrics
    total_revenue = db.session.query(func.sum(Payment.amount)).scalar() or 0.0
    pending_bills_amount = db.session.query(
        func.sum(Bill.grand_total)
    ).filter(Bill.payment_status.in_(['Unpaid', 'Partially Paid'])).scalar() or 0.0
    
    # Recent bookings
    recent_bookings = ServiceBooking.query.order_by(ServiceBooking.booking_date.desc(), ServiceBooking.id.desc()).limit(6).all()
    
    # Mechanics summary
    mechanics = Mechanic.query.all()
    
    # Recent payments
    recent_payments = Payment.query.order_by(Payment.payment_date.desc()).limit(5).all()

    return render_template(
        'dashboard.html',
        total_customers=total_customers,
        total_vehicles=total_vehicles,
        total_mechanics=total_mechanics,
        available_mechanics=available_mechanics,
        active_jobs=active_jobs,
        bookings_today=bookings_today,
        pending_bookings=pending_bookings,
        missed_bookings_count=missed_bookings_count,
        low_stock_count=low_stock_count,
        low_stock_parts=low_stock_parts[:5],
        total_revenue=float(total_revenue),
        pending_bills_amount=float(pending_bills_amount),
        recent_bookings=recent_bookings,
        mechanics=mechanics,
        recent_payments=recent_payments,
        today=today
    )
