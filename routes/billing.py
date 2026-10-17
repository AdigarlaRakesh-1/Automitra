import random
from datetime import datetime
from decimal import Decimal
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, Bill, ServiceBooking, ServiceDetail, Customer, Payment

billing_bp = Blueprint('billing', __name__, url_prefix='/billing')

def generate_invoice_number():
    year = datetime.utcnow().year
    rand_num = random.randint(10000, 99999)
    return f"INV-{year}-{rand_num}"

@billing_bp.route('/')
def index():
    status_filter = request.args.get('status', '').strip()
    query = Bill.query.join(Customer).join(ServiceBooking)

    if status_filter:
        query = query.filter(Bill.payment_status == status_filter)

    bills = query.order_by(Bill.issued_at.desc()).all()
    
    total_invoiced = sum(float(b.grand_total) for b in bills)
    total_unpaid = sum(float(b.balance_due) for b in bills if b.payment_status in ['Unpaid', 'Partially Paid'])

    return render_template('billing/index.html', bills=bills, status_filter=status_filter, total_invoiced=total_invoiced, total_unpaid=total_unpaid)

@billing_bp.route('/generate/<int:booking_id>', methods=['GET', 'POST'])
def generate_bill(booking_id):
    booking = ServiceBooking.query.get_or_404(booking_id)

    # If bill already exists, redirect to it
    if booking.bill:
        flash(f'Invoice already exists for this booking: {booking.bill.invoice_number}', 'info')
        return redirect(url_for('billing.view_invoice', bill_id=booking.bill.id))

    # Auto compute parts and labor from service detail
    parts_total = Decimal('0.00')
    labor_total = Decimal('0.00')

    if booking.service_detail:
        labor_total = booking.service_detail.labor_cost or Decimal('50.00')
        parts_total = Decimal(str(booking.service_detail.parts_total))

    if request.method == 'POST':
        tax_rate = request.form.get('tax_rate', type=float) or 0.0
        discount_amount = request.form.get('discount_amount', type=float) or 0.0

        p_total = Decimal(request.form.get('parts_total', str(parts_total)))
        l_total = Decimal(request.form.get('labor_total', str(labor_total)))
        d_amount = Decimal(str(discount_amount))

        subtotal = p_total + l_total
        tax_amount = round(subtotal * (Decimal(str(tax_rate)) / Decimal('100.0')), 2)
        grand_total = max(Decimal('0.00'), subtotal + tax_amount - d_amount)

        invoice_number = generate_invoice_number()
        while Bill.query.filter_by(invoice_number=invoice_number).first():
            invoice_number = generate_invoice_number()

        try:
            bill = Bill(
                invoice_number=invoice_number,
                booking_id=booking.id,
                customer_id=booking.customer_id,
                parts_total=p_total,
                labor_total=l_total,
                tax_amount=tax_amount,
                discount_amount=d_amount,
                grand_total=grand_total,
                payment_status='Unpaid',
                issued_at=datetime.utcnow()
            )
            # Mark booking as completed if not already
            if booking.status != 'Completed':
                booking.status = 'Completed'

            db.session.add(bill)
            db.session.commit()
            flash(f'Invoice #{bill.invoice_number} successfully generated!', 'success')
            return redirect(url_for('billing.view_invoice', bill_id=bill.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error generating bill: {str(e)}', 'danger')

    return render_template('billing/generate.html', booking=booking, parts_total=parts_total, labor_total=labor_total)

@billing_bp.route('/<int:bill_id>')
def view_invoice(bill_id):
    bill = Bill.query.get_or_404(bill_id)
    return render_template('billing/invoice.html', bill=bill)

@billing_bp.route('/<int:bill_id>/edit', methods=['GET', 'POST'])
def edit_bill(bill_id):
    bill = Bill.query.get_or_404(bill_id)
    if request.method == 'POST':
        parts_total = request.form.get('parts_total', type=float) or 0.0
        labor_total = request.form.get('labor_total', type=float) or 0.0
        tax_amount = request.form.get('tax_amount', type=float) or 0.0
        discount_amount = request.form.get('discount_amount', type=float) or 0.0

        p_tot = Decimal(str(parts_total))
        l_tot = Decimal(str(labor_total))
        t_amt = Decimal(str(tax_amount))
        d_amt = Decimal(str(discount_amount))

        bill.parts_total = p_tot
        bill.labor_total = l_tot
        bill.tax_amount = t_amt
        bill.discount_amount = d_amt
        bill.grand_total = max(Decimal('0.00'), p_tot + l_tot + t_amt - d_amt)
        bill.update_payment_status()

        db.session.commit()
        flash('Invoice adjusted successfully.', 'success')
        return redirect(url_for('billing.view_invoice', bill_id=bill.id))

    return render_template('billing/edit.html', bill=bill)
