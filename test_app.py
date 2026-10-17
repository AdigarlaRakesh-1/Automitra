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
