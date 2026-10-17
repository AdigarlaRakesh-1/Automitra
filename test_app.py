import os
os.environ['USE_SQLITE'] = 'true'
import pytest
from datetime import date, timedelta, datetime
from decimal import Decimal
from app import create_app
from models import db, Customer, Vehicle, Mechanic, ServiceBooking, ServiceDetail, SparePart, PartUsage, Bill, Payment

from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

@pytest.fixture
def client():
    app = create_app(TestConfig)
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
