import random
from datetime import datetime, timezone
from decimal import Decimal
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, Bill, ServiceBooking, ServiceDetail, Customer, Payment

billing_bp = Blueprint('billing', __name__, url_prefix='/billing')

def generate_invoice_number():
    year = datetime.now(timezone.utc).year
    rand_num = random.randint(10000, 99999)
    return f"INV-{year}-{rand_num}"

@billing_bp.route('/')
def index():
    status_filter = request.args.get('status', '').strip()
    query = Bill.query.join(Customer).join(ServiceBooking)

    if status_filter:
        query = query.filter(Bill.payment_status == status_filter)

    bills = query.order_by(Bill.issued_at.desc()).all()
    
    total_invoiced = sum((Decimal(str(b.grand_total)) for b in bills), Decimal('0.00'))
    total_unpaid = sum((b.balance_due for b in bills if b.payment_status in ['Unpaid', 'Partially Paid']), Decimal('0.00'))

    return render_template('billing/index.html', bills=bills, status_filter=status_filter, total_invoiced=total_invoiced, total_unpaid=total_unpaid)

@billing_bp.route('/generate/<int:booking_id>', methods=['GET', 'POST'])
def generate_bill(booking_id):
    booking = db.get_or_404(ServiceBooking, booking_id)

    # If bill already exists, redirect to it
    if booking.bill:
        flash(f'Invoice already exists for this booking: {booking.bill.invoice_number}', 'info')
        return redirect(url_for('billing.view_invoice', bill_id=booking.bill.id))

    # Authoritative parts and labor totals computed strictly from database records
    if booking.service_detail:
        labor_total = Decimal(str(booking.service_detail.labor_cost or '50.00')).quantize(Decimal('0.01'))
        parts_total = sum(
            (Decimal(str(usage.subtotal)) for usage in booking.service_detail.part_usages),
            Decimal('0.00')
        ).quantize(Decimal('0.01'))
    else:
        labor_total = Decimal('50.00')
        parts_total = Decimal('0.00')

    if request.method == 'POST':
        try:
            raw_tax = request.form.get('tax_rate', '0')
            tax_rate = Decimal(str(raw_tax)) if str(raw_tax).strip() != '' else Decimal('0.00')
            if tax_rate < 0 or tax_rate > Decimal('100.00'):
                flash('Tax rate must be between 0% and 100%.', 'danger')
                return render_template('billing/generate.html', booking=booking, parts_total=parts_total, labor_total=labor_total)
        except Exception:
            flash('Tax rate must be a valid percentage between 0% and 100%.', 'danger')
            return render_template('billing/generate.html', booking=booking, parts_total=parts_total, labor_total=labor_total)

        try:
            raw_discount = request.form.get('discount_amount', '0')
            discount_amount = Decimal(str(raw_discount)) if str(raw_discount).strip() != '' else Decimal('0.00')
            if discount_amount < 0:
                flash('Discount amount cannot be negative.', 'danger')
                return render_template('billing/generate.html', booking=booking, parts_total=parts_total, labor_total=labor_total)
        except Exception:
            flash('Discount amount must be a valid non-negative number.', 'danger')
            return render_template('billing/generate.html', booking=booking, parts_total=parts_total, labor_total=labor_total)

        # Compute authoritative totals ignoring any client-tampered parts_total or labor_total
        subtotal = (parts_total + labor_total).quantize(Decimal('0.01'))
        tax_amount = (subtotal * (tax_rate / Decimal('100.00'))).quantize(Decimal('0.01'))
        max_allowed_discount = subtotal + tax_amount

        if discount_amount > max_allowed_discount:
            flash(f'Discount (₹{discount_amount:,.2f}) cannot exceed invoice total before discount (₹{max_allowed_discount:,.2f}).', 'danger')
            return render_template('billing/generate.html', booking=booking, parts_total=parts_total, labor_total=labor_total)

        grand_total = (subtotal + tax_amount - discount_amount).quantize(Decimal('0.01'))

        invoice_number = generate_invoice_number()
        while Bill.query.filter_by(invoice_number=invoice_number).first():
            invoice_number = generate_invoice_number()

        try:
            bill = Bill(
                invoice_number=invoice_number,
                booking_id=booking.id,
                customer_id=booking.customer_id,
                parts_total=parts_total,
                labor_total=labor_total,
                tax_amount=tax_amount,
                discount_amount=discount_amount,
                grand_total=grand_total,
                payment_status='Unpaid',
                issued_at=datetime.now(timezone.utc)
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
    bill = db.get_or_404(Bill, bill_id)
    return render_template('billing/invoice.html', bill=bill)

@billing_bp.route('/<int:bill_id>/edit', methods=['GET', 'POST'])
def edit_bill(bill_id):
    bill = db.get_or_404(Bill, bill_id)

    # Prevent editing bills that already have recorded payments
    if bill.total_paid > Decimal('0.00'):
        flash('Cannot edit an invoice that already has recorded payments.', 'danger')
        return redirect(url_for('billing.view_invoice', bill_id=bill.id))

    if request.method == 'POST':
        try:
            p_tot = Decimal(str(request.form.get('parts_total', '0'))).quantize(Decimal('0.01'))
            l_tot = Decimal(str(request.form.get('labor_total', '0'))).quantize(Decimal('0.01'))
            t_amt = Decimal(str(request.form.get('tax_amount', '0'))).quantize(Decimal('0.01'))
            d_amt = Decimal(str(request.form.get('discount_amount', '0'))).quantize(Decimal('0.01'))

            if p_tot < 0 or l_tot < 0 or t_amt < 0 or d_amt < 0:
                flash('Invoice component amounts cannot be negative.', 'danger')
                return render_template('billing/edit.html', bill=bill)

            if d_amt > (p_tot + l_tot + t_amt):
                flash('Discount amount cannot exceed invoice subtotal + tax.', 'danger')
                return render_template('billing/edit.html', bill=bill)

            bill.parts_total = p_tot
            bill.labor_total = l_tot
            bill.tax_amount = t_amt
            bill.discount_amount = d_amt
            bill.grand_total = (p_tot + l_tot + t_amt - d_amt).quantize(Decimal('0.01'))
            bill.update_payment_status()

            db.session.commit()
            flash('Invoice adjusted successfully.', 'success')
            return redirect(url_for('billing.view_invoice', bill_id=bill.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adjusting invoice: {str(e)}', 'danger')

    return render_template('billing/edit.html', bill=bill)
