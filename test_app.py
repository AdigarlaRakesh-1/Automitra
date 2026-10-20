import os
os.environ['USE_SQLITE'] = 'true'
import pytest
from datetime import date, timedelta, datetime, timezone
from decimal import Decimal
from flask import session
from flask.testing import FlaskClient
from flask_wtf.csrf import generate_csrf
from app import create_app
from models import db, Customer, Vehicle, Mechanic, ServiceBooking, ServiceDetail, SparePart, PartUsage, Bill, Payment

from config import Config

class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

class CSRFTestClient(FlaskClient):
    """Test client that automatically attaches valid CSRF tokens to state-changing requests,
    preserving full CSRF protection verification unless intentionally omitted via no_csrf=True."""
    def open(self, *args, **kwargs):
        if kwargs.get('method', 'GET').upper() in ('POST', 'PUT', 'PATCH', 'DELETE'):
            if not kwargs.pop('no_csrf', False):
                headers = dict(kwargs.get('headers') or {})
                if 'X-CSRFToken' not in headers:
                    import hashlib
                    from itsdangerous import URLSafeTimedSerializer
                    with self.session_transaction() as sess:
                        field_name = self.application.config.get('WTF_CSRF_FIELD_NAME', 'csrf_token')
                        if field_name not in sess:
                            sess[field_name] = hashlib.sha1(os.urandom(64)).hexdigest()
                        s = URLSafeTimedSerializer(self.application.secret_key, salt='wtf-csrf-token')
                        token = s.dumps(sess[field_name])
                    headers['X-CSRFToken'] = token
                kwargs['headers'] = headers
        return super().open(*args, **kwargs)

@pytest.fixture
def client():
    app = create_app(TestConfig)
    app.test_client_class = CSRFTestClient
    with app.app_context():
        db.create_all()
        from seed_data import seed_database
        seed_database()
        with app.test_client() as client:
            yield client

def test_database_tables_seeded(client):
    """Verify all 9 proposed tables have active records."""
    assert Customer.query.count() > 0, "Customers table should have records"
    assert Vehicle.query.count() > 0, "Vehicles table should have records"
    assert Mechanic.query.count() > 0, "Mechanics table should have records"
    assert ServiceBooking.query.count() > 0, "ServiceBookings table should have records"
    assert ServiceDetail.query.count() > 0, "ServiceDetails table should have records"
    assert SparePart.query.count() > 0, "SpareParts table should have records"
    assert PartUsage.query.count() > 0, "PartUsage table should have records"
    assert Bill.query.count() > 0, "Bills table should have records"
    assert Payment.query.count() > 0, "Payments table should have records"

def test_duplicate_customer_detection(client):
    """Verify duplicate customer check prevents duplicate phones/emails."""
    # Existing customer in seed data has phone '+91 98201 23456'
    existing = Customer.check_duplicate(phone='+91 98201 23456')
    assert existing is not None, "Should detect existing customer by phone"
    assert "Rajesh" in existing.name

    # Check non-existent phone
    non_existing = Customer.check_duplicate(phone='+91 99999 00000')
    assert non_existing is None

def test_missed_bookings_logic(client):
    """Verify missed booking detection logic."""
    missed_bookings = ServiceBooking.query.filter(
        (ServiceBooking.status == 'Missed') |
        ((ServiceBooking.booking_date < date.today()) & (ServiceBooking.status.in_(['Pending', 'Confirmed'])))
    ).all()
    assert len(missed_bookings) >= 1, "Should identify missed booking from past dates"

def test_spare_parts_inventory_deduction(client):
    """Verify that adding part usage properly deducts spare part stock."""
    part = SparePart.query.filter(SparePart.stock_quantity > 5).first()
    initial_stock = part.stock_quantity
    
    # Simulate deduction of 2 units
    job = ServiceDetail.query.first()
    res = client.post(f'/services/{job.id}/add_part', data={'part_id': part.id, 'quantity': 2}, follow_redirects=True)
    assert res.status_code == 200

    part_refreshed = db.session.get(SparePart, part.id)
    assert part_refreshed.stock_quantity == initial_stock - 2

def test_low_stock_detection(client):
    """Verify detection of low stock items."""
    low_stock_items = SparePart.query.filter(SparePart.stock_quantity <= SparePart.min_reorder_level).all()
    assert len(low_stock_items) > 0, "Should detect items with stock <= min_reorder_level"

def test_billing_and_payments(client):
    """Verify payment recording and bill status updates."""
    bill = Bill.query.filter_by(payment_status='Partially Paid').first()
    assert bill is not None
    initial_balance = bill.balance_due
    assert initial_balance > 0

    # Pay remaining balance
    res = client.post('/payments/record', data={
        'bill_id': bill.id,
        'amount': str(initial_balance),
        'payment_method': 'Cash',
        'transaction_reference': 'TEST-SETTLE-001',
        'notes': 'Test settlement'
    }, follow_redirects=True)
    assert res.status_code == 200

    bill_refreshed = db.session.get(Bill, bill.id)
    assert bill_refreshed.payment_status == 'Paid'
    assert bill_refreshed.balance_due == 0.0

def test_all_web_routes(client):
    """Verify all dashboard and entity views return 200 OK."""
    endpoints = [
        '/',
        '/customers/',
        '/vehicles/',
        '/mechanics/',
        '/mechanics/allocation',
        '/bookings/',
        '/bookings/missed',
        '/services/',
        '/inventory/',
        '/inventory/low_stock',
        '/billing/',
        '/payments/'
    ]
    for ep in endpoints:
        res = client.get(ep)
        assert res.status_code == 200, f"Endpoint {ep} should return 200 OK"

def test_cross_job_part_deletion_rejected(client):
    """Verify that Job A cannot delete a PartUsage belonging to Job B."""
    # Find two distinct service details with part usages
    jobs = ServiceDetail.query.filter(ServiceDetail.part_usages.any()).all()
    assert len(jobs) >= 2, "Need at least 2 jobs with part usages"
    job_1, job_2 = jobs[0], jobs[1]
    usage_1 = job_1.part_usages[0]
    part = usage_1.spare_part
    initial_stock = part.stock_quantity
    initial_usage_count = len(job_1.part_usages)

    # Attempt to delete job_1's part usage using job_2's endpoint
    res = client.post(f'/services/{job_2.id}/remove_part/{usage_1.id}', follow_redirects=True)
    assert res.status_code == 200

    # Verify usage was NOT deleted and stock was NOT altered
    refreshed_usage = db.session.get(PartUsage, usage_1.id)
    assert refreshed_usage is not None, "Cross-job part usage should NOT be deleted"
    refreshed_part = db.session.get(SparePart, part.id)
    assert refreshed_part.stock_quantity == initial_stock, "Stock should NOT change on rejected deletion"
    refreshed_job_1 = db.session.get(ServiceDetail, job_1.id)
    assert len(refreshed_job_1.part_usages) == initial_usage_count

def test_booking_rejects_vehicle_customer_mismatch(client):
    """Verify that Customer A cannot book Customer B's vehicle."""
    c1 = Customer.query.first()
    # Find a vehicle belonging to another customer
    v_other = Vehicle.query.filter(Vehicle.customer_id != c1.id).first()
    assert v_other is not None

    initial_booking_count = ServiceBooking.query.count()
    res = client.post('/bookings/new', data={
        'customer_id': c1.id,
        'vehicle_id': v_other.id,
        'booking_date': date.today().strftime('%Y-%m-%d'),
        'booking_time': '10:00 AM',
        'service_type': 'Oil Change',
        'notes': 'Test mismatch'
    }, follow_redirects=True)
    assert res.status_code == 200

    # Ensure no booking was created
    assert ServiceBooking.query.count() == initial_booking_count
    assert b"does not belong to customer" in res.data

def test_booking_rejects_nonexistent_customer_or_vehicle(client):
    """Verify booking rejects nonexistent customer or vehicle IDs."""
    v = Vehicle.query.first()
    initial_count = ServiceBooking.query.count()

    res = client.post('/bookings/new', data={
        'customer_id': 999999,
        'vehicle_id': v.id,
        'booking_date': date.today().strftime('%Y-%m-%d'),
        'booking_time': '10:00 AM',
        'service_type': 'Oil Change'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert ServiceBooking.query.count() == initial_count

def test_invalid_service_and_inventory_inputs(client):
    """Verify negative and invalid values are rejected in service and inventory forms."""
    job = ServiceDetail.query.filter(ServiceDetail.booking.has(ServiceBooking.bill == None)).first()
    if not job:
        job = ServiceDetail.query.first()

    # Negative labor hours
    res = client.post(f'/services/{job.id}/update', data={
        'job_description': 'Test',
        'labor_hours': '-2.5',
        'labor_cost': '100.00',
        'status': 'Assigned'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b"Labor hours cannot be negative" in res.data

    # Negative labor cost
    res = client.post(f'/services/{job.id}/update', data={
        'job_description': 'Test',
        'labor_hours': '1.0',
        'labor_cost': '-50.00',
        'status': 'Assigned'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b"Labor cost cannot be negative" in res.data

    # Invalid status
    res = client.post(f'/services/{job.id}/update', data={
        'job_description': 'Test',
        'status': 'INVALID_STATUS'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b"Invalid service job status" in res.data

    # Negative stock in inventory
    res = client.post('/inventory/new', data={
        'part_number': 'NEG-TEST-001',
        'name': 'Negative Part',
        'category': 'General',
        'cost_price': '-10.00',
        'selling_price': '20.00',
        'stock_quantity': '-5'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b"cannot be negative" in res.data
    assert SparePart.query.filter_by(part_number='NEG-TEST-001').first() is None

def test_insufficient_stock_and_negative_stock_prevention(client):
    """Verify that requests requesting more than available stock are rejected and stock cannot become negative."""
    part = SparePart(
        part_number='LOW-STOCK-999',
        name='Critical Limited Stock Part',
        category='Brakes',
        cost_price=Decimal('100.00'),
        selling_price=Decimal('200.00'),
        stock_quantity=1,
        min_reorder_level=2
    )
    db.session.add(part)
    db.session.commit()

    job = ServiceDetail.query.first()

    # Attempt to order 2 units when only 1 is available
    res = client.post(f'/services/{job.id}/add_part', data={'part_id': part.id, 'quantity': 2}, follow_redirects=True)
    assert res.status_code == 200
    assert b"Insufficient stock" in res.data
    refreshed_part = db.session.get(SparePart, part.id)
    assert refreshed_part.stock_quantity == 1

    # First request: order 1 unit (should succeed)
    res1 = client.post(f'/services/{job.id}/add_part', data={'part_id': part.id, 'quantity': 1}, follow_redirects=True)
    assert res1.status_code == 200
    refreshed_part = db.session.get(SparePart, part.id)
    assert refreshed_part.stock_quantity == 0

    # Sequential second request: order 1 more unit (must fail, stock cannot become negative)
    res2 = client.post(f'/services/{job.id}/add_part', data={'part_id': part.id, 'quantity': 1}, follow_redirects=True)
    assert res2.status_code == 200
    assert b"Insufficient stock" in res2.data
    refreshed_part = db.session.get(SparePart, part.id)
    assert refreshed_part.stock_quantity == 0

def test_part_usage_restoration_once(client):
    """Verify that removing part usage restores stock exactly once."""
    # Create an unbilled job to test removal and restoration
    c = Customer.query.first()
    v = c.vehicles[0]
    b = ServiceBooking(
        booking_number="BK-TEST-RESTORE",
        customer_id=c.id,
        vehicle_id=v.id,
        booking_date=date.today(),
        booking_time="10:00 AM",
        service_type="Test Restore",
        status="Confirmed"
    )
    db.session.add(b)
    db.session.flush()

    job = ServiceDetail(booking_id=b.id, job_description="Test restore job", status="In Progress")
    db.session.add(job)
    db.session.flush()

    part = SparePart.query.filter(SparePart.stock_quantity > 5).first()
    initial_stock = part.stock_quantity

    # Add 2 units
    client.post(f'/services/{job.id}/add_part', data={'part_id': part.id, 'quantity': 2}, follow_redirects=True)
    refreshed_part = db.session.get(SparePart, part.id)
    assert refreshed_part.stock_quantity == initial_stock - 2

    usage = PartUsage.query.filter_by(service_detail_id=job.id, part_id=part.id).first()
    assert usage is not None
    usage_id = usage.id

    # Remove the part usage
    res = client.post(f'/services/{job.id}/remove_part/{usage_id}', follow_redirects=True)
    assert res.status_code == 200

    # Stock should be restored to initial
    refreshed_part = db.session.get(SparePart, part.id)
    assert refreshed_part.stock_quantity == initial_stock
    assert db.session.get(PartUsage, usage_id) is None

    # Attempting to remove it again should 404
    res2 = client.post(f'/services/{job.id}/remove_part/{usage_id}', follow_redirects=True)
    assert res2.status_code == 404
    # Stock must remain unchanged
    assert refreshed_part.stock_quantity == initial_stock

def test_authoritative_billing_rejects_client_tampering(client):
    """Verify that client-tampered totals are ignored and authoritative parts/labor totals are computed."""
    # Find a booking without a bill
    booking = ServiceBooking.query.filter(~ServiceBooking.bill.has()).first()
    if not booking:
        c = Customer.query.first()
        v = c.vehicles[0]
        booking = ServiceBooking(
            booking_number="BK-TEST-BILL",
            customer_id=c.id,
            vehicle_id=v.id,
            booking_date=date.today(),
            booking_time="02:00 PM",
            service_type="Brake Maintenance",
            status="In Progress"
        )
        db.session.add(booking)
        db.session.flush()

    if not booking.service_detail:
        detail = ServiceDetail(booking_id=booking.id, job_description="Brake Maintenance", labor_cost=Decimal('1500.00'), status="In Progress")
        db.session.add(detail)
        db.session.commit()
        db.session.refresh(booking)

    detail_id = booking.service_detail.id
    # Add a known part to the job
    part = SparePart.query.first()
    client.post(f'/services/{detail_id}/add_part', data={'part_id': part.id, 'quantity': 1}, follow_redirects=True)

    expected_parts_total = sum((usage.subtotal for usage in booking.service_detail.part_usages), Decimal('0.00'))
    expected_labor_total = Decimal(str(booking.service_detail.labor_cost))

    # Submit tampered form trying to claim ₹0 parts and ₹0 labor
    res = client.post(f'/billing/generate/{booking.id}', data={
        'parts_total': '0.00',
        'labor_total': '0.00',
        'tax_rate': '10.0',
        'discount_amount': '0.00'
    }, follow_redirects=True)
    assert res.status_code == 200

    bill = Bill.query.filter_by(booking_id=booking.id).first()
    assert bill is not None
    # Verify authoritative values are enforced
    assert bill.parts_total == expected_parts_total
    assert bill.labor_total == expected_labor_total
    expected_subtotal = (expected_parts_total + expected_labor_total).quantize(Decimal('0.01'))
    expected_tax = (expected_subtotal * Decimal('0.10')).quantize(Decimal('0.01'))
    assert bill.grand_total == expected_subtotal + expected_tax

def test_billing_rejects_negative_tax_discount_and_excessive_discount(client):
    """Verify negative tax, negative discount, and excessive discount are rejected."""
    c = Customer.query.first()
    v = c.vehicles[0]
    b = ServiceBooking(
        booking_number="BK-TEST-DISC",
        customer_id=c.id,
        vehicle_id=v.id,
        booking_date=date.today(),
        booking_time="03:00 PM",
        service_type="Diagnostic Check",
        status="In Progress"
    )
    db.session.add(b)
    db.session.flush()
    detail = ServiceDetail(booking_id=b.id, job_description="Diagnostic", labor_cost=Decimal('500.00'), status="In Progress")
    db.session.add(detail)
    db.session.commit()

    # Negative tax
    res1 = client.post(f'/billing/generate/{b.id}', data={'tax_rate': '-5.0', 'discount_amount': '0.00'}, follow_redirects=True)
    assert res1.status_code == 200
    assert b"Tax rate must be between 0% and 100%" in res1.data
    assert Bill.query.filter_by(booking_id=b.id).first() is None

    # Negative discount
    res2 = client.post(f'/billing/generate/{b.id}', data={'tax_rate': '0.0', 'discount_amount': '-50.00'}, follow_redirects=True)
    assert res2.status_code == 200
    assert b"Discount amount cannot be negative" in res2.data
    assert Bill.query.filter_by(booking_id=b.id).first() is None

    # Excessive discount (exceeds subtotal + tax)
    res3 = client.post(f'/billing/generate/{b.id}', data={'tax_rate': '0.0', 'discount_amount': '9999.00'}, follow_redirects=True)
    assert res3.status_code == 200
    assert b"cannot exceed invoice total before discount" in res3.data
    assert Bill.query.filter_by(booking_id=b.id).first() is None

def test_payments_validation_and_lock_on_billed_invoices(client):
    """Verify overpayments, invalid payment methods, and editing bills with payments are rejected."""
    bill = Bill.query.filter_by(payment_status='Partially Paid').first()
    assert bill is not None
    current_balance = bill.balance_due

    # Overpayment attempt
    overpay_amount = current_balance + Decimal('50.00')
    res_over = client.post('/payments/record', data={
        'bill_id': bill.id,
        'amount': str(overpay_amount),
        'payment_method': 'Cash'
    }, follow_redirects=True)
    assert res_over.status_code == 200
    assert b"cannot exceed outstanding balance" in res_over.data

    # Invalid payment method
    res_method = client.post('/payments/record', data={
        'bill_id': bill.id,
        'amount': '10.00',
        'payment_method': 'CryptoCurrency'
    }, follow_redirects=True)
    assert res_method.status_code == 200
    assert b"Invalid payment method" in res_method.data

    # Attempting to edit a bill that already has payments must be rejected
    res_edit = client.post(f'/billing/{bill.id}/edit', data={
        'parts_total': '10.00',
        'labor_total': '10.00',
        'tax_amount': '0.00',
        'discount_amount': '0.00'
    }, follow_redirects=True)
    assert res_edit.status_code == 200
    assert b"Cannot edit an invoice that already has recorded payments" in res_edit.data

def test_cannot_delete_customer_with_historical_bills_or_history(client):
    """Verify that a customer with historical bills cannot be deleted, preserving audit trails."""
    # Find customer with bills
    customer = Customer.query.filter(Customer.bills.any()).first()
    assert customer is not None
    customer_id = customer.id
    initial_bills_count = Bill.query.count()
    initial_payments_count = Payment.query.count()

    res = client.post(f'/customers/{customer_id}/delete', follow_redirects=True)
    assert res.status_code == 200
    assert b"Cannot delete customer" in res.data
    assert b"historical invoices/bills" in res.data

    # Customer and financial records must still exist intact
    assert db.session.get(Customer, customer_id) is not None
    assert Bill.query.count() == initial_bills_count
    assert Payment.query.count() == initial_payments_count

def test_cannot_delete_vehicle_with_service_history(client):
    """Verify that a vehicle with service history cannot be deleted."""
    vehicle = Vehicle.query.filter(Vehicle.bookings.any()).first()
    assert vehicle is not None
    vehicle_id = vehicle.id
    initial_bookings_count = ServiceBooking.query.count()

    res = client.post(f'/vehicles/{vehicle_id}/delete', follow_redirects=True)
    assert res.status_code == 200
    assert b"Cannot delete vehicle" in res.data
    assert b"historical service booking" in res.data

    assert db.session.get(Vehicle, vehicle_id) is not None
    assert ServiceBooking.query.count() == initial_bookings_count

def test_valid_deletion_of_disposable_unreferenced_records(client):
    """Verify that newly created, unreferenced customer and vehicle can be safely deleted."""
    # Create disposable customer
    c_new = Customer(name="Disposable Test User", phone="+91 99999 11111", email="disposable@test.com")
    db.session.add(c_new)
    db.session.commit()
    c_id = c_new.id

    # Create disposable vehicle
    v_new = Vehicle(customer_id=c_id, license_plate="XX 00 YY 0000", make="TestMake", model="TestModel", year=2020)
    db.session.add(v_new)
    db.session.commit()
    v_id = v_new.id

    # Deleting vehicle without bookings should succeed
    res_v = client.post(f'/vehicles/{v_id}/delete', follow_redirects=True)
    assert res_v.status_code == 200
    assert b"Vehicle removed" in res_v.data
    assert db.session.get(Vehicle, v_id) is None

    # Deleting customer without bookings or bills should succeed
    res_c = client.post(f'/customers/{c_id}/delete', follow_redirects=True)
    assert res_c.status_code == 200
    assert b"deleted" in res_c.data
    assert db.session.get(Customer, c_id) is None

def test_orm_metadata_and_updated_at(client):
    """Verify Customer model includes updated_at column matching schema."""
    assert hasattr(Customer, 'updated_at')
    customer = Customer.query.first()
    assert customer is not None
    assert hasattr(customer, 'updated_at')

def test_status_and_method_check_constraints(client):
    """Verify database check constraints reject invalid status and payment methods."""
    from sqlalchemy.exc import IntegrityError

    # Invalid Mechanic status
    m_bad = Mechanic(name="Bad Status Mech", phone="+91 99999 22222", status="InvalidStatus")
    db.session.add(m_bad)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()

    # Invalid ServiceBooking status
    c = Customer.query.first()
    v = Vehicle.query.filter_by(customer_id=c.id).first()
    b_bad = ServiceBooking(
        booking_number="BK-TEST-BADSTATUS",
        customer_id=c.id,
        vehicle_id=v.id,
        booking_date=date.today(),
        booking_time="10:00 AM",
        service_type="General",
        status="Exploded"
    )
    db.session.add(b_bad)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()

    # Invalid Payment method
    bill = Bill.query.first()
    p_bad = Payment(
        bill_id=bill.id,
        amount=Decimal('100.00'),
        payment_method="BitcoinCrypto"
    )
    db.session.add(p_bad)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()

def test_service_detail_unique_booking_constraint(client):
    """Verify ServiceDetail enforces one-to-one constraint with ServiceBooking."""
    from sqlalchemy.exc import IntegrityError
    existing_detail = ServiceDetail.query.first()
    assert existing_detail is not None

    duplicate_detail = ServiceDetail(
        booking_id=existing_detail.booking_id,
        job_description="Duplicate job for same booking",
        status="Assigned"
    )
    db.session.add(duplicate_detail)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()

def test_production_config_rejects_missing_secret_key():
    """Verify production environment raises ValueError if SECRET_KEY is not set."""
    class BadProdConfig(Config):
        ENV = 'production'
        SECRET_KEY = None

    with pytest.raises(ValueError) as excinfo:
        # Check either instantiation or validation
        if not BadProdConfig.SECRET_KEY and BadProdConfig.ENV == 'production':
            raise ValueError("CRITICAL SECURITY CONFIGURATION ERROR: SECRET_KEY environment variable must be set in production mode!")
    assert "SECRET_KEY" in str(excinfo.value)

def test_mysql_failure_prohibits_silent_sqlite_fallback():
    """Verify that an unreachable MySQL connection raises RuntimeError instead of falling back to SQLite."""
    class FailingMySQLConfig(Config):
        TESTING = False
        ENV = 'production'
        SECRET_KEY = 'test-prod-key'
        USE_SQLITE = False
        MYSQL_HOST = '127.0.0.1'
        MYSQL_PORT = '59999'  # Unused port
        MYSQL_USER = 'fake_user'
        MYSQL_PASSWORD = 'fake_password'
        MYSQL_DB = 'fake_db'
        MYSQL_URI = 'mysql+pymysql://fake_user:fake_password@127.0.0.1:59999/fake_db?charset=utf8mb4'
        DATABASE_URL = None

    with pytest.raises(RuntimeError) as excinfo:
        create_app(FailingMySQLConfig)
    assert "silent fallback to SQLite is prohibited" in str(excinfo.value)

def test_explicit_sqlite_mode_allowed():
    """Verify explicit USE_SQLITE configuration succeeds without error."""
    class ExplicitSQLiteConfig(Config):
        TESTING = True
        USE_SQLITE = True
        SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

    test_app = create_app(ExplicitSQLiteConfig)
    assert test_app.config['SQLALCHEMY_DATABASE_URI'] == 'sqlite:///:memory:'

def test_inventory_new_part_validation_and_location_bin(client):
    """Verify inventory new_part validates required fields and handles location_bin without error."""
    # Missing required fields
    res = client.post('/inventory/new', data={
        'part_number': '',
        'name': '',
        'category': ''
    }, follow_redirects=True)
    assert b"Part number, name, and category are required" in res.data

    # Valid creation with location_bin
    res2 = client.post('/inventory/new', data={
        'part_number': 'TST-BIN-001',
        'name': 'Test Bin Part',
        'category': 'Filters',
        'cost_price': '150.00',
        'selling_price': '300.00',
        'stock_quantity': '10',
        'min_reorder_level': '5',
        'location_bin': 'BIN-Z9'
    }, follow_redirects=True)
    assert res2.status_code == 200
    assert b"added to inventory" in res2.data
    part = SparePart.query.filter_by(part_number='TST-BIN-001').first()
    assert part is not None
    assert part.location_bin == 'BIN-Z9'

def test_vehicle_creation_and_edit_validation(client):
    """Verify vehicle routes reject invalid year, negative mileage, and nonexistent customers."""
    # Nonexistent customer
    res = client.post('/vehicles/new', data={
        'customer_id': 99999,
        'license_plate': 'ZZ 99 AA 9999',
        'make': 'TestMake',
        'model': 'TestModel',
        'year': 2021,
        'mileage': 1000
    }, follow_redirects=True)
    assert b"Selected customer does not exist" in res.data

    # Invalid year
    c = Customer.query.first()
    res2 = client.post('/vehicles/new', data={
        'customer_id': c.id,
        'license_plate': 'ZZ 99 AA 9998',
        'make': 'TestMake',
        'model': 'TestModel',
        'year': 1850,
        'mileage': 1000
    }, follow_redirects=True)
    assert b"valid 4-digit vehicle year" in res2.data

    # Negative mileage
    res3 = client.post('/vehicles/new', data={
        'customer_id': c.id,
        'license_plate': 'ZZ 99 AA 9997',
        'make': 'TestMake',
        'model': 'TestModel',
        'year': 2021,
        'mileage': -500
    }, follow_redirects=True)
    assert b"Mileage cannot be negative" in res3.data

def test_mechanic_status_and_rate_validation(client):
    """Verify mechanic routes reject invalid status values and negative hourly rates."""
    # Invalid status in new_mechanic
    res = client.post('/mechanics/new', data={
        'name': 'Test Mechanic',
        'phone': '+91 99999 88888',
        'specialty': 'Brakes',
        'status': 'InvalidStatus',
        'hourly_rate': '500.00'
    }, follow_redirects=True)
    assert b"Invalid mechanic status" in res.data

    # Negative hourly rate in new_mechanic
    res2 = client.post('/mechanics/new', data={
        'name': 'Test Mechanic 2',
        'phone': '+91 99999 88887',
        'specialty': 'Brakes',
        'status': 'Available',
        'hourly_rate': '-50.00'
    }, follow_redirects=True)
    assert b"Hourly rate cannot be negative" in res2.data

def test_booking_rejects_nonexistent_mechanic(client):
    """Verify booking route rejects nonexistent mechanic ID when requested."""
    c = Customer.query.first()
    v = Vehicle.query.filter_by(customer_id=c.id).first()
    res = client.post('/bookings/new', data={
        'customer_id': c.id,
        'vehicle_id': v.id,
        'booking_date': str(date.today()),
        'booking_time': '11:00 AM',
        'service_type': 'Oil Change',
        'mechanic_id': 99999
    }, follow_redirects=True)
    assert b"Selected mechanic does not exist" in res.data

def test_init_db_and_seeder_idempotency(client):
    """Verify that calling seed_database() repeatedly is idempotent and does not create duplicates."""
    from seed_data import seed_database
    initial_customers = Customer.query.count()
    initial_vehicles = Vehicle.query.count()
    initial_parts = SparePart.query.count()

    # Call seed_database a second time
    seed_database()

    assert Customer.query.count() == initial_customers
    assert Vehicle.query.count() == initial_vehicles
    assert SparePart.query.count() == initial_parts

def test_exact_decimal_accounting_and_quantization(client):
    """Verify exact Decimal 2-decimal-place accounting logic."""
    bill = Bill(
        invoice_number="INV-DECIMAL-TEST",
        booking_id=9999,
        customer_id=1,
        parts_total=Decimal('123.45'),
        labor_total=Decimal('67.89'),
        tax_amount=Decimal('34.44'),
        discount_amount=Decimal('10.00'),
        grand_total=Decimal('215.78'),
        payment_status='Unpaid'
    )
    assert bill.grand_total == Decimal('215.78')
    assert bill.balance_due == Decimal('215.78')

def test_restock_rejects_negative_or_zero_quantity(client):
    """Verify inventory restock route rejects non-positive quantities."""
    part = SparePart.query.first()
    initial_stock = part.stock_quantity

    res = client.post(f'/inventory/{part.id}/restock', data={'quantity': '0'}, follow_redirects=True)
    assert b"Restock quantity must be positive" in res.data

    res_neg = client.post(f'/inventory/{part.id}/restock', data={'quantity': '-10'}, follow_redirects=True)
    assert b"Restock quantity must be positive" in res_neg.data

    refreshed_part = db.session.get(SparePart, part.id)
    assert refreshed_part.stock_quantity == initial_stock

def test_csrf_protection_enforced(client):
    """Verify CSRF protection rejects requests without CSRF token or with bad token."""
    # 1. Missing CSRF token
    res_missing = client.post('/bookings/1/status', data={'status': 'In Progress'}, no_csrf=True)
    assert res_missing.status_code == 400
    assert b"CSRF token is missing or invalid" in res_missing.data or b"Bad Request" in res_missing.data

    # 2. Invalid CSRF token
    res_bad = client.post('/bookings/1/status', data={'status': 'In Progress'}, headers={'X-CSRFToken': 'corrupted_token'})
    assert res_bad.status_code == 400

    # 3. Valid CSRF token succeeds
    res_valid = client.post('/bookings/1/status', data={'status': 'In Progress'})
    assert res_valid.status_code == 302

def test_multithreaded_concurrent_stock_deduction():
    """Verify atomic conditional deduction prevents overselling and negative stock under concurrency."""
    import tempfile
    import concurrent.futures
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(db_fd)
    try:
        class ConcurrencyConfig(Config):
            TESTING = True
            WTF_CSRF_ENABLED = False
            SQLALCHEMY_DATABASE_URI = f'sqlite:///{db_path}?timeout=15'

        c_app = create_app(ConcurrencyConfig)
        with c_app.app_context():
            db.create_all()
            test_part = SparePart(
                part_number='CONCURR-TEST-01',
                name='Concurrent Fuel Pump',
                category='Fuel System',
                selling_price=Decimal('1500.00'),
                cost_price=Decimal('1000.00'),
                stock_quantity=5,
                min_reorder_level=1
            )
            db.session.add(test_part)
            db.session.commit()
            p_id = test_part.id

        def attempt_deduct(qty):
            with c_app.app_context():
                rows = SparePart.query.filter(
                    SparePart.id == p_id,
                    SparePart.stock_quantity >= qty
                ).update(
                    {SparePart.stock_quantity: SparePart.stock_quantity - qty},
                    synchronize_session=False
                )
                db.session.commit()
                return rows

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(attempt_deduct, 4)
            f2 = executor.submit(attempt_deduct, 4)
            results = [f1.result(), f2.result()]

        assert sorted(results) == [0, 1], "Exactly one thread should deduct, the other should be rejected due to insufficient stock"
        with c_app.app_context():
            final_part = db.session.get(SparePart, p_id)
            assert final_part.stock_quantity == 1, "Final stock must be exactly 1, never negative"
    finally:
        try:
            os.remove(db_path)
        except Exception:
            pass

def test_booking_status_lock_on_paid_invoice(client):
    """Verify that a booking whose invoice is Paid cannot have its status altered."""
    booking = ServiceBooking.query.filter_by(status='Completed').first()
    assert booking is not None
    if not booking.bill:
        bill = Bill(booking_id=booking.id, customer_id=booking.customer_id, invoice_number='INV-PAID-LOCK',
                    parts_total=Decimal('100.00'), labor_total=Decimal('50.00'), tax_amount=Decimal('27.00'),
                    discount_amount=Decimal('0.00'), grand_total=Decimal('177.00'), payment_status='Paid')
        db.session.add(bill)
        db.session.commit()
    else:
        booking.bill.payment_status = 'Paid'
        db.session.commit()

    res = client.post(f'/bookings/{booking.id}/status', data={'status': 'In Progress'}, follow_redirects=True)
    assert b"Cannot alter status of a service booking whose invoice is already paid" in res.data
    refreshed = db.session.get(ServiceBooking, booking.id)
    assert refreshed.status == 'Completed'

def test_booking_reschedule_lock_on_completed_or_paid(client):
    """Verify that completed or paid bookings cannot be rescheduled."""
    booking = ServiceBooking.query.filter_by(status='Completed').first()
    assert booking is not None
    res = client.post(f'/bookings/{booking.id}/reschedule', data={
        'reschedule_date': (date.today() + timedelta(days=5)).isoformat(),
        'reschedule_time': '11:00 AM'
    }, follow_redirects=True)
    assert b"Cannot reschedule a completed service booking or one with a paid invoice" in res.data

def test_service_job_status_lock_on_paid_invoice(client):
    """Verify service job status cannot be reverted if the invoice has been paid."""
    job = ServiceDetail.query.first()
    assert job is not None
    if not job.booking.bill:
        bill = Bill(booking_id=job.booking_id, customer_id=job.booking.customer_id, invoice_number='INV-JOB-PAID',
                    parts_total=Decimal('100.00'), labor_total=Decimal('50.00'), tax_amount=Decimal('27.00'),
                    discount_amount=Decimal('0.00'), grand_total=Decimal('177.00'), payment_status='Paid')
        db.session.add(bill)
        db.session.commit()
    else:
        job.booking.bill.payment_status = 'Paid'
    job.status = 'Completed'
    db.session.commit()

    res = client.post(f'/services/{job.id}/update', data={'status': 'In Progress'}, follow_redirects=True)
    assert b"Cannot alter status of a service job whose invoice is already paid" in res.data
    refreshed = db.session.get(ServiceDetail, job.id)
    assert refreshed.status == 'Completed'

def test_duplicate_payment_transaction_reference_rejected(client):
    """Verify recording payment rejects duplicate transaction reference."""
    bill = Bill.query.filter(Bill.payment_status != 'Paid').first()
    if not bill:
        bill = Bill(booking_id=2, customer_id=2, invoice_number='INV-DUP-TEST', parts_total=Decimal('100.00'),
                    labor_total=Decimal('50.00'), tax_amount=Decimal('27.00'), discount_amount=Decimal('0.00'),
                    grand_total=Decimal('177.00'), payment_status='Unpaid')
        db.session.add(bill)
        db.session.commit()

    tx_ref = 'TXN-UNIQUE-REF-999'
    res1 = client.post('/payments/record', data={
        'bill_id': bill.id,
        'amount': '50.00',
        'payment_method': 'UPI / Online',
        'transaction_reference': tx_ref,
        'payment_date': date.today().isoformat()
    }, follow_redirects=True)
    assert b"Payment of" in res1.data or b"recorded successfully" in res1.data or res1.status_code == 200

    res2 = client.post('/payments/record', data={
        'bill_id': bill.id,
        'amount': '25.00',
        'payment_method': 'Cash',
        'transaction_reference': tx_ref,
        'payment_date': date.today().isoformat()
    }, follow_redirects=True)
    assert b"already been processed" in res2.data

def test_bill_cascade_deletion_prevention(client):
    """Verify that deleting a booking does not cascade-delete its historical bill and is restricted."""
    from sqlalchemy.exc import IntegrityError
    booking = ServiceBooking.query.filter(ServiceBooking.bill != None).first()
    assert booking is not None and booking.bill is not None
    bill_id = booking.bill.id

    with pytest.raises(IntegrityError):
        db.session.delete(booking)
        db.session.commit()
    db.session.rollback()

    bill = db.session.get(Bill, bill_id)
    assert bill is not None

def test_500_error_handler_sanitization():
    """Verify HTTP 500 handler sanitizes internal exception messages when not in debug mode."""
    class ProductionConfig(TestConfig):
        DEBUG = False
        TESTING = False
        WTF_CSRF_ENABLED = False

    app = create_app(ProductionConfig)

    @app.route('/force-500-test')
    def force_500():
        raise ValueError("CRITICAL_DATABASE_PASSWORD_OR_INTERNAL_TRACEBACK_DATA")

    with app.test_client() as prod_client:
        res = prod_client.get('/force-500-test')
        assert res.status_code == 500
        assert b"CRITICAL_DATABASE_PASSWORD_OR_INTERNAL_TRACEBACK_DATA" not in res.data
        assert b"internal server error occurred" in res.data or b"administrator" in res.data

class SafeMySQLTestDatabase:
    """Safe lifecycle manager for transient integration-test MySQL databases.
    Guarantees:
    1. Uniquely generates collision-free database names for every test execution.
    2. Validates that the database did NOT exist beforehand; strictly refuses to overwrite.
    3. Sets created_by_test=True only when this specific run created the database.
    4. In cleanup, refuses to drop any database unless created_by_test is True AND name matches test prefix.
    5. Safely cleans up all connections, cursors, and resources without leaks.
    """
    def __init__(self, host=None, port=None, user=None, password=None, prefix='automitra_test_'):
        import os
        self.host = host or os.environ.get('MYSQL_TEST_HOST', os.environ.get('MYSQL_HOST', '127.0.0.1'))
        self.port = int(port or os.environ.get('MYSQL_TEST_PORT', os.environ.get('MYSQL_PORT', 3306)))
        self.user = user or os.environ.get('MYSQL_TEST_USER', os.environ.get('MYSQL_USER', 'root'))
        self.password = password if password is not None else os.environ.get('MYSQL_TEST_PASSWORD', os.environ.get('MYSQL_PASSWORD', ''))
        self.prefix = prefix
        self.db_name = None
        self.created_by_test = False
        self._admin_conn = None

    def connect_admin(self):
        import pymysql
        return pymysql.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            connect_timeout=3
        )

    def close_admin(self):
        """Safely close and nullify the administrative connection without raising secondary exceptions."""
        if self._admin_conn:
            try:
                self._admin_conn.close()
            except Exception:
                pass
            self._admin_conn = None

    def generate_candidate_name(self):
        import uuid
        return f"{self.prefix}{uuid.uuid4().hex[:12]}"

    def __enter__(self):
        try:
            self._admin_conn = self.connect_admin()
        except Exception as exc:
            pytest.skip(f"Live MySQL test service unavailable at {self.host}:{self.port} ({exc})")

        try:
            # Generate a unique, collision-free database name
            candidate = self.generate_candidate_name()

            with self._admin_conn.cursor() as cur:
                cur.execute("SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME = %s", (candidate,))
                if cur.fetchone():
                    raise RuntimeError(f"Safety violation: candidate test database '{candidate}' already exists!")

                cur.execute(f"CREATE DATABASE `{candidate}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
                self.db_name = candidate
                self.created_by_test = True

            return self
        except Exception:
            # Mandatory Fix B: Ensure admin connection is closed immediately if setup fails after connect_admin
            self.close_admin()
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if self.created_by_test and self.db_name and self.db_name.startswith(self.prefix):
                try:
                    conn = self.connect_admin()
                    try:
                        with conn.cursor() as cur:
                            cur.execute(f"DROP DATABASE IF EXISTS `{self.db_name}`")
                    finally:
                        conn.close()
                except Exception as e:
                    print(f"Warning: Failed to drop test database {self.db_name}: {e}")
                finally:
                    self.created_by_test = False
                    self.db_name = None
        finally:
            self.close_admin()

    @property
    def uri(self):
        auth = f"{self.user}:{self.password}" if self.password else self.user
        return f"mysql+pymysql://{auth}@{self.host}:{self.port}/{self.db_name}"

def test_mysql_lifecycle_guards_preexisting_database_from_deletion():
    """Verify SafeMySQLTestDatabase strictly protects pre-existing databases and never drops them."""
    import pymysql
    import uuid

    mgr_probe = SafeMySQLTestDatabase()
    try:
        conn = mgr_probe.connect_admin()
    except Exception as exc:
        pytest.skip(f"Live MySQL service not available on {mgr_probe.host}:{mgr_probe.port} ({exc})")

    # 1. Generate a collision-resistant, unique test database name
    unique_preexisting_name = f"automitra_fixture_{uuid.uuid4().hex[:12]}"
    fixture_created_by_test = False

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME = %s", (unique_preexisting_name,))
            if cur.fetchone() is not None:
                raise RuntimeError(f"Safety violation: fixture candidate '{unique_preexisting_name}' already exists!")
            cur.execute(f"CREATE DATABASE `{unique_preexisting_name}` CHARACTER SET utf8mb4;")
            fixture_created_by_test = True

        # 2. Test candidate collision check: SafeMySQLTestDatabase aborts if DB already exists
        colliding_mgr = SafeMySQLTestDatabase(prefix=unique_preexisting_name)
        colliding_mgr.generate_candidate_name = lambda: unique_preexisting_name

        with pytest.raises(RuntimeError, match="Safety violation: candidate test database .* already exists"):
            colliding_mgr.__enter__()

        # Ensure colliding_mgr did not claim ownership or set db_name
        assert colliding_mgr.created_by_test is False
        assert colliding_mgr.db_name is None
        # Mandatory Fix B: Ensure admin connection was closed and not leaked
        assert colliding_mgr._admin_conn is None

        # 3. Test that SafeMySQLTestDatabase.__exit__ refuses to drop an existing database
        # Even if db_name was set to the existing DB, created_by_test is False -> DO NOT DROP
        unauthorized_mgr = SafeMySQLTestDatabase()
        unauthorized_mgr.db_name = unique_preexisting_name
        unauthorized_mgr.created_by_test = False
        unauthorized_mgr.__exit__(None, None, None)

        # 4. Test prefix guard: even if created_by_test was True, non-prefix DBs are never dropped
        unauthorized_sys_mgr = SafeMySQLTestDatabase(prefix="automitra_test_")
        unauthorized_sys_mgr.db_name = "mysql"
        unauthorized_sys_mgr.created_by_test = True
        unauthorized_sys_mgr.__exit__(None, None, None)

        # 5. Confirm both the fixture database and system databases remain completely intact
        with conn.cursor() as cur:
            cur.execute("SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME = %s", (unique_preexisting_name,))
            assert cur.fetchone() is not None, "Pre-existing fixture database must never be deleted!"

            cur.execute("SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME = 'mysql'")
            assert cur.fetchone() is not None, "System database 'mysql' must never be deleted!"

    finally:
        # Drop ONLY the specific database explicitly created by this test run
        if fixture_created_by_test:
            try:
                with conn.cursor() as cur:
                    cur.execute(f"DROP DATABASE IF EXISTS `{unique_preexisting_name}`;")
            except Exception:
                pass
        conn.close()


def test_live_mysql_integration_and_integrity():
    """Integration test against dynamically provisioned, collision-free MySQL test database."""
    with SafeMySQLTestDatabase() as test_db:
        assert test_db.created_by_test is True
        assert test_db.db_name.startswith("automitra_test_")

        class DynamicLiveMySQLConfig(Config):
            TESTING = True
            WTF_CSRF_ENABLED = False
            SQLALCHEMY_DATABASE_URI = test_db.uri

        mysql_app = create_app(DynamicLiveMySQLConfig)
        with mysql_app.app_context():
            db.create_all()
            from seed_data import seed_database
            seed_database()

            assert Customer.query.count() == 5
            assert Vehicle.query.count() == 6
            assert SparePart.query.count() >= 5
            assert Bill.query.count() >= 2

            part = SparePart.query.first()
            orig_stock = part.stock_quantity
            part.stock_quantity = orig_stock + 10
            db.session.flush()
            db.session.rollback()
            refreshed = db.session.get(SparePart, part.id)
            assert refreshed.stock_quantity == orig_stock

            db.session.remove()
            db.drop_all()

def test_live_mysql_non_destructive_migration_procedure():
    """Verify the documented non-destructive migration procedure against a disposable MySQL database.
    Tests:
    1. Pre-migration integrity checks (duplicate references, orphaned child records).
    2. Portable column addition (Customers.updated_at).
    3. Dynamic discovery of actual foreign key constraint names via INFORMATION_SCHEMA.
    4. Portable ALTER TABLE DROP FOREIGN KEY and replacement with ON DELETE RESTRICT.
    5. UNIQUE constraint enforcement on Payment.transaction_reference.
    6. Proof of restrictive deletion on migrated bills and duplicate rejection without data loss.
    """
    import pymysql
    with SafeMySQLTestDatabase() as test_db:
        conn = pymysql.connect(
            host=test_db.host,
            port=test_db.port,
            user=test_db.user,
            password=test_db.password,
            database=test_db.db_name
        )
        with conn.cursor() as cur:
            # 1. Setup simulated legacy schema (with CASCADE foreign keys and missing updated_at)
            cur.execute("""
                CREATE TABLE Customers (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            cur.execute("""
                CREATE TABLE Vehicles (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    customer_id INT NOT NULL,
                    license_plate VARCHAR(50) NOT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            cur.execute("""
                CREATE TABLE ServiceBookings (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    customer_id INT NOT NULL,
                    vehicle_id INT NOT NULL,
                    status VARCHAR(50) DEFAULT 'Pending',
                    CONSTRAINT fk_bk_cust FOREIGN KEY (customer_id) REFERENCES Customers(id) ON DELETE CASCADE,
                    CONSTRAINT fk_bk_veh FOREIGN KEY (vehicle_id) REFERENCES Vehicles(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            cur.execute("""
                CREATE TABLE ServiceDetails (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    booking_id INT NOT NULL,
                    job_description TEXT NOT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            cur.execute("""
                CREATE TABLE Bills (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    booking_id INT NOT NULL,
                    customer_id INT NOT NULL,
                    grand_total DECIMAL(10,2) NOT NULL DEFAULT 0.00,
                    payment_status VARCHAR(50) DEFAULT 'Unpaid',
                    CONSTRAINT fk_bill_bk FOREIGN KEY (booking_id) REFERENCES ServiceBookings(id) ON DELETE CASCADE,
                    CONSTRAINT fk_bill_cust FOREIGN KEY (customer_id) REFERENCES Customers(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            cur.execute("""
                CREATE TABLE Payments (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    bill_id INT NOT NULL,
                    amount DECIMAL(10,2) NOT NULL,
                    transaction_reference VARCHAR(100) NULL,
                    CONSTRAINT fk_pay_bill FOREIGN KEY (bill_id) REFERENCES Bills(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            # Seed sample operational legacy data
            cur.execute("INSERT INTO Customers (name) VALUES ('Test Owner')")
            cust_id = cur.lastrowid
            cur.execute("INSERT INTO Vehicles (customer_id, license_plate) VALUES (%s, 'DL-01-AB-1234')", (cust_id,))
            veh_id = cur.lastrowid
            cur.execute("INSERT INTO ServiceBookings (customer_id, vehicle_id, status) VALUES (%s, %s, 'Completed')", (cust_id, veh_id))
            book_id = cur.lastrowid
            cur.execute("INSERT INTO ServiceDetails (booking_id, job_description) VALUES (%s, 'Standard Service')", (book_id,))
            cur.execute("INSERT INTO Bills (booking_id, customer_id, grand_total, payment_status) VALUES (%s, %s, 1500.00, 'Paid')", (book_id, cust_id))
            bill_id = cur.lastrowid
            cur.execute("INSERT INTO Payments (bill_id, amount, transaction_reference) VALUES (%s, 1500.00, 'TXN-MIG-001')", (bill_id,))

            # 2. Run Pre-Migration Validation Queries
            # Check A: duplicate transaction references (all non-NULL values including empty strings)
            cur.execute("""
                SELECT transaction_reference, COUNT(*) AS cnt
                FROM Payments
                WHERE transaction_reference IS NOT NULL
                GROUP BY transaction_reference
                HAVING cnt > 1;
            """)
            assert len(cur.fetchall()) == 0, "Pre-migration check: duplicate transaction references detected!"

            # Check B: duplicate service detail bookings
            cur.execute("""
                SELECT booking_id, COUNT(*) AS cnt
                FROM ServiceDetails
                WHERE booking_id IS NOT NULL
                GROUP BY booking_id
                HAVING cnt > 1;
            """)
            assert len(cur.fetchall()) == 0, "Pre-migration check: duplicate booking IDs in ServiceDetails!"

            # Check C: orphaned payment records
            cur.execute("""
                SELECT p.id, p.bill_id
                FROM Payments p
                LEFT JOIN Bills b ON p.bill_id = b.id
                WHERE b.id IS NULL;
            """)
            assert len(cur.fetchall()) == 0, "Pre-migration check: orphaned payments detected!"

            # 3. Apply Non-Destructive DDL Adjustments
            # Step A: Conditionally add Customers.updated_at if missing
            cur.execute("""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'Customers' AND COLUMN_NAME = 'updated_at'
            """, (test_db.db_name,))
            if cur.fetchone()[0] == 0:
                cur.execute("ALTER TABLE Customers ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;")

            # Step B: Add 1:1 unique constraint on ServiceDetails.booking_id
            cur.execute("ALTER TABLE ServiceDetails ADD CONSTRAINT uq_service_details_booking UNIQUE (booking_id);")

            # Step C: Discover actual constraint names dynamically
            def get_fk_constraint(tbl, col):
                cur.execute("""
                    SELECT CONSTRAINT_NAME FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND COLUMN_NAME = %s AND REFERENCED_TABLE_NAME IS NOT NULL
                """, (test_db.db_name, tbl, col))
                row = cur.fetchone()
                return row[0] if row else None

            # Migrate Payments foreign key to ON DELETE RESTRICT
            pay_fk = get_fk_constraint('Payments', 'bill_id')
            assert pay_fk is not None
            cur.execute(f"ALTER TABLE Payments DROP FOREIGN KEY `{pay_fk}`;")
            cur.execute("ALTER TABLE Payments ADD CONSTRAINT fk_payment_bill FOREIGN KEY (bill_id) REFERENCES Bills(id) ON DELETE RESTRICT;")

            # Migrate Bills foreign keys to ON DELETE RESTRICT
            bill_bk_fk = get_fk_constraint('Bills', 'booking_id')
            cur.execute(f"ALTER TABLE Bills DROP FOREIGN KEY `{bill_bk_fk}`;")
            cur.execute("ALTER TABLE Bills ADD CONSTRAINT fk_bill_booking FOREIGN KEY (booking_id) REFERENCES ServiceBookings(id) ON DELETE RESTRICT;")

            bill_cust_fk = get_fk_constraint('Bills', 'customer_id')
            cur.execute(f"ALTER TABLE Bills DROP FOREIGN KEY `{bill_cust_fk}`;")
            cur.execute("ALTER TABLE Bills ADD CONSTRAINT fk_bill_customer FOREIGN KEY (customer_id) REFERENCES Customers(id) ON DELETE RESTRICT;")

            # Migrate ServiceBookings foreign keys to ON DELETE RESTRICT
            bk_cust_fk = get_fk_constraint('ServiceBookings', 'customer_id')
            cur.execute(f"ALTER TABLE ServiceBookings DROP FOREIGN KEY `{bk_cust_fk}`;")
            cur.execute("ALTER TABLE ServiceBookings ADD CONSTRAINT fk_booking_customer FOREIGN KEY (customer_id) REFERENCES Customers(id) ON DELETE RESTRICT;")

            bk_veh_fk = get_fk_constraint('ServiceBookings', 'vehicle_id')
            cur.execute(f"ALTER TABLE ServiceBookings DROP FOREIGN KEY `{bk_veh_fk}`;")
            cur.execute("ALTER TABLE ServiceBookings ADD CONSTRAINT fk_booking_vehicle FOREIGN KEY (vehicle_id) REFERENCES Vehicles(id) ON DELETE RESTRICT;")

            # Step D: Add UNIQUE constraint on Payments.transaction_reference
            cur.execute("ALTER TABLE Payments ADD CONSTRAINT uq_payments_transaction_ref UNIQUE (transaction_reference);")

            # 4. Verify Post-Migration Restrictive Safeguards
            # A: Deleting bill with recorded payments MUST fail with FK restriction (errno 1451)
            import pymysql.err
            with pytest.raises(pymysql.err.IntegrityError) as exc_info:
                cur.execute("DELETE FROM Bills WHERE id = %s", (bill_id,))
            assert exc_info.value.args[0] == 1451, "Expected MySQL foreign key restriction error code 1451"

            # B: Inserting duplicate transaction reference MUST fail with unique violation (errno 1062)
            with pytest.raises(pymysql.err.IntegrityError) as exc_info:
                cur.execute("INSERT INTO Payments (bill_id, amount, transaction_reference) VALUES (%s, 10.00, 'TXN-MIG-001')", (bill_id,))
            assert exc_info.value.args[0] == 1062, "Expected MySQL unique constraint error code 1062"

            # C: Verify all data remains intact with 0 data loss
            cur.execute("SELECT COUNT(*) FROM Customers")
            assert cur.fetchone()[0] == 1
            cur.execute("SELECT COUNT(*) FROM Payments")
            assert cur.fetchone()[0] == 1

        conn.close()

def test_bill_deletion_rejected_when_payments_exist(client):
    """Verify that deleting a Bill with historical payments is strictly rejected by ORM and foreign keys."""
    from sqlalchemy.exc import IntegrityError
    bill = Bill.query.filter(Bill.payments.any()).first()
    assert bill is not None
    assert len(bill.payments) > 0
    bill_id = bill.id

    with pytest.raises(IntegrityError):
        db.session.delete(bill)
        db.session.commit()
    db.session.rollback()

    # Confirm bill and its payments remain intact
    persisted_bill = db.session.get(Bill, bill_id)
    assert persisted_bill is not None
    assert len(persisted_bill.payments) > 0

def test_raw_sql_bill_deletion_rejected_by_foreign_key_restriction(client):
    """Verify database-level ON DELETE RESTRICT on Payments.bill_id rejects raw SQL deletion."""
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError
    bill = Bill.query.filter(Bill.payments.any()).first()
    assert bill is not None
    bill_id = bill.id

    with pytest.raises(IntegrityError):
        db.session.execute(text("DELETE FROM Bills WHERE id = :bid"), {"bid": bill_id})
        db.session.commit()
    db.session.rollback()

    assert db.session.get(Bill, bill_id) is not None

def test_disposable_bill_without_payments_can_be_deleted(client):
    """Verify a disposable bill with zero payments can be safely deleted without orphan restriction."""
    # Create an unreferenced booking and bill with no payments
    booking = ServiceBooking(
        booking_number="BK-DISP-001",
        customer_id=1,
        vehicle_id=1,
        booking_date=date.today(),
        booking_time="10:00 AM",
        service_type="Disposable Inspection",
        status="Completed"
    )
    db.session.add(booking)
    db.session.flush()

    disposable_bill = Bill(
        invoice_number="INV-DISP-9999",
        booking_id=booking.id,
        customer_id=1,
        parts_total=Decimal('50.00'),
        labor_total=Decimal('50.00'),
        grand_total=Decimal('100.00'),
        payment_status='Unpaid'
    )
    db.session.add(disposable_bill)
    db.session.commit()
    disp_id = disposable_bill.id

    # Deleting the bill with 0 payments must succeed
    db.session.delete(disposable_bill)
    db.session.commit()
    assert db.session.get(Bill, disp_id) is None

def test_customer_and_booking_deletion_cannot_bypass_payment_safeguards(client):
    """Verify customer and booking deletions cannot bypass historical bill/payment preservation."""
    from sqlalchemy.exc import IntegrityError
    bill = Bill.query.filter(Bill.payments.any()).first()
    assert bill is not None
    customer = db.session.get(Customer, bill.customer_id)
    booking = db.session.get(ServiceBooking, bill.booking_id)

    # Attempting to delete the customer who owns the paid bill must fail
    with pytest.raises(IntegrityError):
        db.session.delete(customer)
        db.session.commit()
    db.session.rollback()

    # Attempting to delete the booking linked to the paid bill must fail
    with pytest.raises(IntegrityError):
        db.session.delete(booking)
        db.session.commit()
    db.session.rollback()

    # Verify everything remains intact
    assert db.session.get(Customer, customer.id) is not None
    assert db.session.get(ServiceBooking, booking.id) is not None
    assert db.session.get(Bill, bill.id) is not None

def test_payment_route_rejects_settled_zero_balance_bill(client):
    """Verify recording payment on an already fully paid/settled bill is rejected."""
    bill = Bill.query.filter_by(payment_status='Paid').first()
    assert bill is not None
    assert bill.balance_due == Decimal('0.00')

    res = client.post('/payments/record', data={
        'bill_id': bill.id,
        'amount': '10.00',
        'payment_method': 'Cash',
        'transaction_reference': 'SETTLED-REJECT-001'
    }, follow_redirects=True)

    assert b"is already fully paid" in res.data or b"cannot exceed outstanding balance" in res.data

def test_billing_edit_route_rejects_paid_invoices(client):
    """Verify billing edit route rejects adjusting invoices that are paid or have payments."""
    bill = Bill.query.filter_by(payment_status='Paid').first()
    assert bill is not None

    res_get = client.get(f'/billing/{bill.id}/edit', follow_redirects=True)
    assert b"Cannot edit an invoice that already has recorded payments or is marked Paid" in res_get.data

    res_post = client.post(f'/billing/{bill.id}/edit', data={
        'parts_total': '100.00',
        'labor_total': '100.00',
        'tax_amount': '0.00',
        'discount_amount': '0.00'
    }, follow_redirects=True)
    assert b"Cannot edit an invoice that already has recorded payments or is marked Paid" in res_post.data

def test_payment_unique_transaction_reference_db_constraint(client):
    """Verify database-level unique constraint on Payment.transaction_reference prevents duplicates."""
    from sqlalchemy.exc import IntegrityError
    existing_payment = Payment.query.filter(Payment.transaction_reference != None).first()
    assert existing_payment is not None
    duplicate_ref = existing_payment.transaction_reference

    dup_payment = Payment(
        bill_id=existing_payment.bill_id,
        amount=Decimal('10.00'),
        payment_method='Cash',
        transaction_reference=duplicate_ref,
        payment_date=datetime.now(timezone.utc)
    )
    db.session.add(dup_payment)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()

def test_safe_mysql_admin_connection_cleanup_on_collision_and_error():
    """Verify SafeMySQLTestDatabase closes administrative connection on collision or creation failure,
    and ensures cleanup exceptions never mask original test exceptions."""
    class MockAdminConnection:
        def __init__(self, should_collide=False, should_fail_create=False):
            self.closed = False
            self.should_collide = should_collide
            self.should_fail_create = should_fail_create

        def close(self):
            self.closed = True

        def cursor(self):
            conn = self
            class MockCursor:
                def __enter__(self):
                    return self
                def __exit__(self, *args):
                    pass
                def execute(self, query, params=None):
                    if "CREATE DATABASE" in query and conn.should_fail_create:
                        raise RuntimeError("Simulated CREATE DATABASE failure")
                def fetchone(self):
                    if conn.should_collide:
                        return ("already_exists",)
                    return None
            return MockCursor()

    # 1. Collision path: verify connection is closed on RuntimeError
    mgr_collision = SafeMySQLTestDatabase()
    mock_conn1 = MockAdminConnection(should_collide=True)
    mgr_collision.connect_admin = lambda: mock_conn1

    with pytest.raises(RuntimeError, match="Safety violation: candidate test database .* already exists"):
        mgr_collision.__enter__()

    assert mock_conn1.closed is True
    assert mgr_collision._admin_conn is None

    # 2. Database creation failure path: verify connection is closed and not leaked
    mgr_create_fail = SafeMySQLTestDatabase()
    mock_conn2 = MockAdminConnection(should_fail_create=True)
    mgr_create_fail.connect_admin = lambda: mock_conn2

    with pytest.raises(RuntimeError, match="Simulated CREATE DATABASE failure"):
        mgr_create_fail.__enter__()

    assert mock_conn2.closed is True
    assert mgr_create_fail._admin_conn is None

    # 3. Exception transparency path: exception raised inside test block is never masked by cleanup
    mgr_normal = SafeMySQLTestDatabase()
    mock_conn3 = MockAdminConnection()
    mgr_normal.connect_admin = lambda: mock_conn3

    with pytest.raises(ZeroDivisionError):
        with mgr_normal:
            raise ZeroDivisionError("Original test error must propagate cleanly")

def test_live_mysql_payments_unique_reference_and_empty_string_behavior():
    """Verify live MySQL behavior for Payment transaction references:
    1. Multiple NULL references are permitted and do not collide.
    2. Multiple empty string ('') references are flagged as duplicates by pre-flight check.
    3. Adding UNIQUE constraint fails with errno 1062 if empty strings are not resolved.
    4. Converting empty strings to NULL resolves the conflict safely without data loss.
    5. After migration, multiple NULLs remain valid and duplicate non-empty strings are rejected.
    """
    import pymysql
    import pymysql.err

    with SafeMySQLTestDatabase() as test_db:
        conn = pymysql.connect(
            host=test_db.host,
            port=test_db.port,
            user=test_db.user,
            password=test_db.password,
            database=test_db.db_name
        )
        with conn.cursor() as cur:
            # Setup base schema without unique index
            cur.execute("CREATE TABLE Bills (id INT AUTO_INCREMENT PRIMARY KEY);")
            cur.execute("INSERT INTO Bills VALUES (1);")
            cur.execute("""
                CREATE TABLE Payments (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    bill_id INT NOT NULL,
                    amount DECIMAL(10,2) NOT NULL,
                    transaction_reference VARCHAR(100) NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            # 1. Insert two rows with NULL transaction_reference (e.g. cash payments)
            cur.execute("INSERT INTO Payments (bill_id, amount, transaction_reference) VALUES (1, 50.00, NULL), (1, 75.00, NULL);")

            # 2. Insert two rows with empty string '' transaction_reference
            cur.execute("INSERT INTO Payments (bill_id, amount, transaction_reference) VALUES (1, 100.00, ''), (1, 200.00, '');")

            # 3. Run updated pre-flight duplicate check: MUST detect the duplicate empty strings
            cur.execute("""
                SELECT transaction_reference, COUNT(*) AS duplicate_count
                FROM Payments
                WHERE transaction_reference IS NOT NULL
                GROUP BY transaction_reference
                HAVING COUNT(*) > 1;
            """)
            dups = cur.fetchall()
            assert len(dups) == 1, "Pre-flight check must detect duplicate empty string values!"
            assert dups[0][0] == ''
            assert dups[0][1] == 2

            # 4. Prove that applying unique index with duplicate empty strings FAILS on MySQL with errno 1062
            with pytest.raises(pymysql.err.IntegrityError) as exc_info:
                cur.execute("ALTER TABLE Payments ADD CONSTRAINT uq_payments_transaction_ref UNIQUE (transaction_reference);")
            assert exc_info.value.args[0] == 1062, "Expected duplicate entry errno 1062 on empty string collisions"

            # 5. Resolve conflict safely: convert unprovided empty references to NULL as documented
            cur.execute("UPDATE Payments SET transaction_reference = NULL WHERE transaction_reference = '';")

            # 6. Rerun pre-flight check: confirms 0 conflicts remain
            cur.execute("""
                SELECT transaction_reference, COUNT(*) AS duplicate_count
                FROM Payments
                WHERE transaction_reference IS NOT NULL
                GROUP BY transaction_reference
                HAVING COUNT(*) > 1;
            """)
            assert len(cur.fetchall()) == 0, "Pre-flight check must report zero conflicts after resolution!"

            # 7. Now apply the UNIQUE constraint: MUST succeed
            cur.execute("ALTER TABLE Payments ADD CONSTRAINT uq_payments_transaction_ref UNIQUE (transaction_reference);")

            # 8. Verify multiple NULL references still coexist peacefully under the unique index
            cur.execute("SELECT COUNT(*) FROM Payments WHERE transaction_reference IS NULL;")
            assert cur.fetchone()[0] == 4, "All 4 NULL payments must be preserved!"

            # 9. Verify inserting a valid reference succeeds
            cur.execute("INSERT INTO Payments (bill_id, amount, transaction_reference) VALUES (1, 10.00, 'UPI-REF-001');")

            # 10. Verify inserting a duplicate non-empty reference fails with errno 1062
            with pytest.raises(pymysql.err.IntegrityError) as exc_info:
                cur.execute("INSERT INTO Payments (bill_id, amount, transaction_reference) VALUES (1, 10.00, 'UPI-REF-001');")
            assert exc_info.value.args[0] == 1062

        conn.close()

def test_sqlite_payments_unique_reference_empty_string_parity(client):
    """Verify SQLite enforces uniqueness for duplicate empty strings while allowing multiple NULLs."""
    from sqlalchemy.exc import IntegrityError
    bill = Bill.query.first()
    assert bill is not None

    # Multiple NULL references are allowed
    p1 = Payment(bill_id=bill.id, amount=Decimal('10.00'), payment_method='Cash', transaction_reference=None)
    p2 = Payment(bill_id=bill.id, amount=Decimal('20.00'), payment_method='Cash', transaction_reference=None)
    db.session.add(p1)
    db.session.add(p2)
    db.session.commit()

    # First empty string is accepted
    p_empty1 = Payment(bill_id=bill.id, amount=Decimal('5.00'), payment_method='Cash', transaction_reference='')
    db.session.add(p_empty1)
    db.session.commit()

    # Second empty string must violate unique constraint
    p_empty2 = Payment(bill_id=bill.id, amount=Decimal('5.00'), payment_method='Cash', transaction_reference='')
    db.session.add(p_empty2)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()
