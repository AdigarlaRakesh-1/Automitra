from datetime import datetime, date
from decimal import Decimal
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func

db = SQLAlchemy()

# ---------------------------------------------------------------------
# 1. Customers Table
# ---------------------------------------------------------------------
class Customer(db.Model):
    __tablename__ = 'Customers'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), nullable=False, unique=True, index=True)
    email = db.Column(db.String(120), nullable=True)
    address = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    vehicles = db.relationship('Vehicle', backref='customer', cascade='all, delete-orphan', lazy=True)
    bookings = db.relationship('ServiceBooking', backref='customer', cascade='all, delete-orphan', lazy=True)
    bills = db.relationship('Bill', backref='customer', cascade='all, delete-orphan', lazy=True)
    
    @classmethod
    def check_duplicate(cls, phone, email=None, exclude_id=None):
        """Checks for existing customer by phone or email to prevent duplicates."""
        query = cls.query.filter(cls.phone == phone)
        if exclude_id:
            query = query.filter(cls.id != exclude_id)
        existing_phone = query.first()
        if existing_phone:
            return existing_phone
        
        if email and email.strip():
            query_email = cls.query.filter(cls.email == email.strip())
            if exclude_id:
                query_email = query_email.filter(cls.id != exclude_id)
            return query_email.first()
        return None

    def __repr__(self):
        return f"<Customer {self.name} - {self.phone}>"


# ---------------------------------------------------------------------
# 2. Vehicles Table
# ---------------------------------------------------------------------
class Vehicle(db.Model):
    __tablename__ = 'Vehicles'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('Customers.id', ondelete='CASCADE'), nullable=False)
    license_plate = db.Column(db.String(30), nullable=False, unique=True, index=True)
    make = db.Column(db.String(60), nullable=False)
    model = db.Column(db.String(60), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    vin = db.Column(db.String(60), nullable=True)
    mileage = db.Column(db.Integer, default=0)
    fuel_type = db.Column(db.String(30), default='Petrol')
    color = db.Column(db.String(40), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    bookings = db.relationship('ServiceBooking', backref='vehicle', cascade='all, delete-orphan', lazy=True)

    @property
    def display_name(self):
        return f"{self.year} {self.make} {self.model} ({self.license_plate})"

    def __repr__(self):
        return f"<Vehicle {self.license_plate} - {self.make} {self.model}>"


# ---------------------------------------------------------------------
# 3. Mechanics Table
# ---------------------------------------------------------------------
class Mechanic(db.Model):
    __tablename__ = 'Mechanics'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    specialty = db.Column(db.String(100), nullable=False, default='General Service')
    status = db.Column(db.String(30), default='Available', index=True) # 'Available', 'Busy', 'On Leave'
    hourly_rate = db.Column(db.Numeric(10, 2), default=45.00)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    service_details = db.relationship('ServiceDetail', backref='mechanic', lazy=True)

    @property
    def active_jobs_count(self):
        return sum(1 for job in self.service_details if job.status in ['Assigned', 'In Progress', 'Awaiting Parts'])

    def __repr__(self):
        return f"<Mechanic {self.name} - {self.specialty}>"


# ---------------------------------------------------------------------
# 4. ServiceBookings Table
# ---------------------------------------------------------------------
class ServiceBooking(db.Model):
    __tablename__ = 'ServiceBookings'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    booking_number = db.Column(db.String(40), nullable=False, unique=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('Customers.id', ondelete='CASCADE'), nullable=False)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('Vehicles.id', ondelete='CASCADE'), nullable=False)
    booking_date = db.Column(db.Date, nullable=False, index=True)
    booking_time = db.Column(db.String(20), nullable=False)
    service_type = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(40), default='Pending', index=True) # 'Pending', 'Confirmed', 'In Progress', 'Completed', 'Cancelled', 'Missed'
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    service_detail = db.relationship('ServiceDetail', backref='booking', uselist=False, cascade='all, delete-orphan')
    bill = db.relationship('Bill', backref='booking', uselist=False, cascade='all, delete-orphan')

    @property
    def is_missed(self):
        """Calculates if booking was missed (date passed and still pending/confirmed)."""
        today = date.today()
        if self.status in ['Pending', 'Confirmed'] and self.booking_date < today:
            return True
        return False

    def __repr__(self):
        return f"<ServiceBooking {self.booking_number} - {self.status}>"


# ---------------------------------------------------------------------
# 5. ServiceDetails Table
# ---------------------------------------------------------------------
class ServiceDetail(db.Model):
    __tablename__ = 'ServiceDetails'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('ServiceBookings.id', ondelete='CASCADE'), nullable=False)
    mechanic_id = db.Column(db.Integer, db.ForeignKey('Mechanics.id', ondelete='SET NULL'), nullable=True)
    job_description = db.Column(db.Text, nullable=False)
    diagnosis = db.Column(db.Text, nullable=True)
    labor_hours = db.Column(db.Numeric(5, 2), default=1.00)
    labor_cost = db.Column(db.Numeric(10, 2), default=50.00)
    status = db.Column(db.String(40), default='Assigned', index=True) # 'Assigned', 'In Progress', 'Awaiting Parts', 'Completed'
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    part_usages = db.relationship('PartUsage', backref='service_detail', cascade='all, delete-orphan', lazy=True)

    @property
    def parts_total(self):
        return sum(float(usage.subtotal) for usage in self.part_usages)

    @property
    def total_cost(self):
        return float(self.labor_cost) + self.parts_total

    def __repr__(self):
        return f"<ServiceDetail #{self.id} for Booking #{self.booking_id}>"


# ---------------------------------------------------------------------
# 6. SpareParts Table
# ---------------------------------------------------------------------
class SparePart(db.Model):
    __tablename__ = 'SpareParts'
    __table_args__ = (
        db.CheckConstraint('stock_quantity >= 0', name='check_spare_parts_stock_non_negative'),
        db.CheckConstraint('cost_price >= 0', name='check_spare_parts_cost_non_negative'),
        db.CheckConstraint('selling_price >= 0', name='check_spare_parts_price_non_negative'),
    )
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    part_number = db.Column(db.String(50), nullable=False, unique=True, index=True)
    name = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(80), nullable=False)
    cost_price = db.Column(db.Numeric(10, 2), default=0.00)
    selling_price = db.Column(db.Numeric(10, 2), default=0.00)
    stock_quantity = db.Column(db.Integer, default=0, index=True)
    min_reorder_level = db.Column(db.Integer, default=5)
    location_bin = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    usages = db.relationship('PartUsage', backref='spare_part', lazy=True)

    @property
    def is_low_stock(self):
        return self.stock_quantity <= self.min_reorder_level

    def __repr__(self):
        return f"<SparePart {self.part_number} - {self.name} (Qty: {self.stock_quantity})>"


# ---------------------------------------------------------------------
# 7. PartUsage Table
# ---------------------------------------------------------------------
class PartUsage(db.Model):
    __tablename__ = 'PartUsage'
    __table_args__ = (
        db.CheckConstraint('quantity > 0', name='check_part_usage_qty_positive'),
        db.CheckConstraint('unit_price >= 0', name='check_part_usage_price_non_negative'),
        db.CheckConstraint('subtotal >= 0', name='check_part_usage_subtotal_non_negative'),
    )
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    service_detail_id = db.Column(db.Integer, db.ForeignKey('ServiceDetails.id', ondelete='CASCADE'), nullable=False)
    part_id = db.Column(db.Integer, db.ForeignKey('SpareParts.id', ondelete='RESTRICT'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    unit_price = db.Column(db.Numeric(10, 2), default=0.00)
    subtotal = db.Column(db.Numeric(10, 2), default=0.00)
    used_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<PartUsage Part #{self.part_id} x{self.quantity}>"


# ---------------------------------------------------------------------
# 8. Bills Table
# ---------------------------------------------------------------------
class Bill(db.Model):
    __tablename__ = 'Bills'
    __table_args__ = (
        db.CheckConstraint('grand_total >= 0', name='check_bill_grand_total_non_negative'),
        db.CheckConstraint('parts_total >= 0', name='check_bill_parts_total_non_negative'),
        db.CheckConstraint('labor_total >= 0', name='check_bill_labor_total_non_negative'),
        db.CheckConstraint('tax_amount >= 0', name='check_bill_tax_amount_non_negative'),
        db.CheckConstraint('discount_amount >= 0', name='check_bill_discount_amount_non_negative'),
    )
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    invoice_number = db.Column(db.String(50), nullable=False, unique=True, index=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('ServiceBookings.id', ondelete='CASCADE'), nullable=False, unique=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('Customers.id', ondelete='CASCADE'), nullable=False)
    parts_total = db.Column(db.Numeric(10, 2), default=0.00)
    labor_total = db.Column(db.Numeric(10, 2), default=0.00)
    tax_amount = db.Column(db.Numeric(10, 2), default=0.00)
    discount_amount = db.Column(db.Numeric(10, 2), default=0.00)
    grand_total = db.Column(db.Numeric(10, 2), default=0.00)
    payment_status = db.Column(db.String(30), default='Unpaid', index=True) # 'Unpaid', 'Partially Paid', 'Paid'
    issued_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    payments = db.relationship('Payment', backref='bill', cascade='all, delete-orphan', lazy=True)

    @property
    def total_paid(self):
        return sum((Decimal(str(payment.amount)) for payment in self.payments), Decimal('0.00'))

    @property
    def balance_due(self):
        total = Decimal(str(self.grand_total or '0.00'))
        bal = total - self.total_paid
        return max(Decimal('0.00'), bal.quantize(Decimal('0.01')))

    def update_payment_status(self):
        paid = self.total_paid
        total = Decimal(str(self.grand_total or '0.00'))
        if paid >= total and total > Decimal('0.00'):
            self.payment_status = 'Paid'
        elif paid > Decimal('0.00'):
            self.payment_status = 'Partially Paid'
        else:
            self.payment_status = 'Unpaid'

    def __repr__(self):
        return f"<Bill {self.invoice_number} - {self.payment_status} (₹{self.grand_total})>"


# ---------------------------------------------------------------------
# 9. Payments Table
# ---------------------------------------------------------------------
class Payment(db.Model):
    __tablename__ = 'Payments'
    __table_args__ = (
        db.CheckConstraint('amount > 0', name='check_payment_amount_positive'),
    )
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    bill_id = db.Column(db.Integer, db.ForeignKey('Bills.id', ondelete='CASCADE'), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_method = db.Column(db.String(40), nullable=False, default='Cash') # 'Cash', 'Credit Card', 'Debit Card', 'UPI / Online', 'Bank Transfer'
    transaction_reference = db.Column(db.String(100), nullable=True)
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f"<Payment ₹{self.amount} for Bill #{self.bill_id} via {self.payment_method}>"
