from datetime import datetime, timezone
from decimal import Decimal
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, Payment, Bill

payments_bp = Blueprint('payments', __name__, url_prefix='/payments')

ALLOWED_PAYMENT_METHODS = {'Cash', 'Credit Card', 'Debit Card', 'UPI / Online', 'Bank Transfer'}

@payments_bp.route('/')
def index():
    method_filter = request.args.get('method', '').strip()
    query = Payment.query.join(Bill)
    if method_filter:
        query = query.filter(Payment.payment_method == method_filter)

    payments = query.order_by(Payment.payment_date.desc()).all()
    total_received = sum((Decimal(str(p.amount)) for p in payments), Decimal('0.00'))

    return render_template('payments/index.html', payments=payments, method_filter=method_filter, total_received=total_received)

@payments_bp.route('/record', methods=['POST'])
def record_payment():
    bill_id = request.form.get('bill_id', type=int)
    raw_amount = request.form.get('amount', '').strip()
    payment_method = request.form.get('payment_method', 'Cash').strip()
    transaction_reference = request.form.get('transaction_reference', '').strip()
    notes = request.form.get('notes', '').strip()

    if not bill_id or not raw_amount:
        flash('Valid bill ID and positive payment amount are required.', 'danger')
        return redirect(request.referrer or url_for('billing.index'))

    if payment_method not in ALLOWED_PAYMENT_METHODS:
        flash(f'Invalid payment method "{payment_method}". Allowed methods: {", ".join(sorted(ALLOWED_PAYMENT_METHODS))}.', 'danger')
        return redirect(request.referrer or url_for('billing.index'))

    try:
        amount = Decimal(raw_amount).quantize(Decimal('0.01'))
        if amount <= Decimal('0.00'):
            raise ValueError()
    except Exception:
        flash('Payment amount must be a positive number.', 'danger')
        return redirect(request.referrer or url_for('billing.index'))

    if transaction_reference:
        existing_txn = Payment.query.filter_by(transaction_reference=transaction_reference).first()
        if existing_txn:
            flash(f'Duplicate payment rejected: Transaction reference "{transaction_reference}" has already been processed for Payment #{existing_txn.id}.', 'danger')
            return redirect(url_for('billing.view_invoice', bill_id=bill_id))

    try:
        bill = db.session.query(Bill).filter_by(id=bill_id).with_for_update().first()
    except Exception:
        bill = db.session.get(Bill, bill_id)

    if not bill:
        flash('Bill record not found.', 'danger')
        return redirect(url_for('billing.index'))

    # Check if bill is already fully settled or amount exceeds balance due
    balance = bill.balance_due
    if balance <= Decimal('0.00'):
        flash(f'Invoice #{bill.invoice_number} is already fully paid. No further payments can be recorded.', 'warning')
        return redirect(url_for('billing.view_invoice', bill_id=bill.id))

    if amount > balance:
        flash(f'Payment amount (₹{amount:,.2f}) cannot exceed outstanding balance (₹{balance:,.2f}).', 'warning')
        return redirect(url_for('billing.view_invoice', bill_id=bill.id))

    try:
        payment = Payment(
            amount=amount,
            payment_method=payment_method,
            transaction_reference=transaction_reference or None,
            payment_date=datetime.now(timezone.utc),
            notes=notes or None
        )
        bill.payments.append(payment)
        bill.update_payment_status()
        db.session.commit()

        flash(f'Payment of ₹{amount:,.2f} via {payment_method} successfully recorded for Invoice #{bill.invoice_number}!', 'success')
        return redirect(url_for('billing.view_invoice', bill_id=bill.id))
    except Exception as e:
        db.session.rollback()
        err_msg = str(e).lower()
        if 'unique' in err_msg or 'duplicate' in err_msg:
            flash(f'Payment rejected: Transaction reference "{transaction_reference}" has already been recorded.', 'danger')
        else:
            flash(f'Error recording payment: {str(e)}', 'danger')
        return redirect(url_for('billing.view_invoice', bill_id=bill.id))

@payments_bp.route('/receipt/<int:payment_id>')
def view_receipt(payment_id):
    payment = db.get_or_404(Payment, payment_id)
    return render_template('payments/receipt.html', payment=payment)
