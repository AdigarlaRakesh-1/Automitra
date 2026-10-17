from datetime import datetime
from decimal import Decimal
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, Payment, Bill

payments_bp = Blueprint('payments', __name__, url_prefix='/payments')

@payments_bp.route('/')
def index():
    method_filter = request.args.get('method', '').strip()
    query = Payment.query.join(Bill)
    if method_filter:
        query = query.filter(Payment.payment_method == method_filter)

    payments = query.order_by(Payment.payment_date.desc()).all()
    total_received = sum(float(p.amount) for p in payments)

    return render_template('payments/index.html', payments=payments, method_filter=method_filter, total_received=total_received)

@payments_bp.route('/record', methods=['POST'])
def record_payment():
    bill_id = request.form.get('bill_id', type=int)
    amount = request.form.get('amount', type=float)
    payment_method = request.form.get('payment_method', 'Cash')
    transaction_reference = request.form.get('transaction_reference', '').strip()
    notes = request.form.get('notes', '').strip()

    if not bill_id or not amount or amount <= 0:
        flash('Valid bill ID and positive payment amount are required.', 'danger')
        return redirect(request.referrer or url_for('billing.index'))

    bill = Bill.query.get_or_404(bill_id)

    # Check if amount exceeds balance due
    balance = bill.balance_due
    if amount > (balance + 0.01):
        flash(f'Payment amount (${amount:.2f}) cannot exceed outstanding balance (${balance:.2f}).', 'warning')
        return redirect(url_for('billing.view_invoice', bill_id=bill.id))

    try:
        payment = Payment(
            amount=Decimal(str(amount)),
            payment_method=payment_method,
            transaction_reference=transaction_reference or None,
            payment_date=datetime.utcnow(),
            notes=notes or None
        )
        bill.payments.append(payment)
        bill.update_payment_status()
        db.session.commit()

        flash(f'Payment of ${amount:.2f} via {payment_method} successfully recorded for Invoice #{bill.invoice_number}!', 'success')
        return redirect(url_for('billing.view_invoice', bill_id=bill.id))
    except Exception as e:
        db.session.rollback()
        flash(f'Error recording payment: {str(e)}', 'danger')
        return redirect(url_for('billing.view_invoice', bill_id=bill.id))

@payments_bp.route('/receipt/<int:payment_id>')
def view_receipt(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    return render_template('payments/receipt.html', payment=payment)
