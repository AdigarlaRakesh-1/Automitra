from datetime import datetime
from decimal import Decimal
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, ServiceDetail, ServiceBooking, Mechanic, SparePart, PartUsage, Bill

services_bp = Blueprint('services', __name__, url_prefix='/services')

@services_bp.route('/')
def index():
    status_filter = request.args.get('status', '').strip()
    query = ServiceDetail.query.join(ServiceBooking)
    if status_filter:
        query = query.filter(ServiceDetail.status == status_filter)
    
    jobs = query.order_by(ServiceDetail.id.desc()).all()
    return render_template('services/index.html', jobs=jobs, status_filter=status_filter)

@services_bp.route('/<int:detail_id>')
def view_job(detail_id):
    job = ServiceDetail.query.get_or_404(detail_id)
    mechanics = Mechanic.query.all()
    spare_parts = SparePart.query.filter(SparePart.stock_quantity > 0).order_by(SparePart.name.asc()).all()
    
    return render_template('services/detail.html', job=job, mechanics=mechanics, spare_parts=spare_parts)

@services_bp.route('/<int:detail_id>/update', methods=['POST'])
def update_job(detail_id):
    job = ServiceDetail.query.get_or_404(detail_id)
    mechanic_id = request.form.get('mechanic_id', type=int)
    job_description = request.form.get('job_description', '').strip()
    diagnosis = request.form.get('diagnosis', '').strip()
    labor_hours = request.form.get('labor_hours', type=float) or 1.0
    labor_cost = request.form.get('labor_cost', type=float) or 50.0
    status = request.form.get('status', job.status)

    try:
        # Check if mechanic changed
        if mechanic_id != job.mechanic_id:
            job.mechanic_id = mechanic_id or None
            if mechanic_id:
                m = db.session.get(Mechanic, mechanic_id)
                if m and m.status == 'Available':
                    m.status = 'Busy'

        job.job_description = job_description
        job.diagnosis = diagnosis or None
        job.labor_hours = Decimal(str(labor_hours))
        job.labor_cost = Decimal(str(labor_cost))
        job.status = status

        if status == 'In Progress' and not job.started_at:
            job.started_at = datetime.utcnow()
            job.booking.status = 'In Progress'
        elif status == 'Completed':
            if not job.completed_at:
                job.completed_at = datetime.utcnow()
            job.booking.status = 'Completed'

        db.session.commit()
        flash('Job details and labor updated successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating job details: {str(e)}', 'danger')

    return redirect(url_for('services.view_job', detail_id=job.id))

@services_bp.route('/<int:detail_id>/add_part', methods=['POST'])
def add_part_usage(detail_id):
    job = ServiceDetail.query.get_or_404(detail_id)
    part_id = request.form.get('part_id', type=int)
    quantity = request.form.get('quantity', type=int) or 1

    if not part_id or quantity <= 0:
        flash('Please select a valid part and quantity greater than zero.', 'warning')
        return redirect(url_for('services.view_job', detail_id=job.id))

    part = db.session.get(SparePart, part_id)
    if not part:
        flash('Selected part not found.', 'danger')
        return redirect(url_for('services.view_job', detail_id=job.id))

    # Validate stock quantity
    if part.stock_quantity < quantity:
        flash(f'Insufficient stock for {part.name}! Available: {part.stock_quantity}, Requested: {quantity}.', 'danger')
        return redirect(url_for('services.view_job', detail_id=job.id))

    try:
        # Calculate subtotal
        unit_price = part.selling_price
        subtotal = unit_price * quantity

        # Deduct stock
        part.stock_quantity -= quantity

        usage = PartUsage(
            service_detail_id=job.id,
            part_id=part.id,
            quantity=quantity,
            unit_price=unit_price,
            subtotal=subtotal
        )
        db.session.add(usage)
        db.session.commit()
        flash(f'Added {quantity}x {part.name} to job. Inventory updated (Remaining: {part.stock_quantity}).', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding part: {str(e)}', 'danger')

    return redirect(url_for('services.view_job', detail_id=job.id))

@services_bp.route('/<int:detail_id>/remove_part/<int:usage_id>', methods=['POST'])
def remove_part_usage(detail_id, usage_id):
    job = ServiceDetail.query.get_or_404(detail_id)
    usage = PartUsage.query.get_or_404(usage_id)

    try:
        # Restore stock in inventory
        part = usage.spare_part
        if part:
            part.stock_quantity += usage.quantity

        db.session.delete(usage)
        db.session.commit()
        flash(f'Removed part usage. Restored {usage.quantity} units to {part.name} stock.', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'Error removing part: {str(e)}', 'danger')

    return redirect(url_for('services.view_job', detail_id=job.id))
