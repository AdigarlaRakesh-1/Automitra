from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from models import db, Customer, Vehicle, Mechanic, ServiceBooking, ServiceDetail, SparePart, PartUsage, Bill, Payment

def seed_database():
    """Seeds rich, realistic data covering all 9 tables in Indian Rupees (INR)."""
    # Check if data already exists
    if Customer.query.first():
        print("Database already contains data. Skipping seeding.")
        return

    print("Seeding sample data for AutoMitra (INR Currency)...")

    # 1. Customers
    c1 = Customer(name="Rajesh Sharma", phone="+91 98201 23456", email="rajesh.sharma@gmail.com", address="Flat 402, Shivalik Heights, Andheri West, Mumbai")
    c2 = Customer(name="Priya Patel", phone="+91 98112 34567", email="priya.patel@techcorp.in", address="Tower B, Sector 62, Noida, NCR")
    c3 = Customer(name="Amit Verma", phone="+91 98450 45678", email="amit.verma@bangalore.org", address="45, 12th Main, Indiranagar, Bengaluru")
    c4 = Customer(name="Sunita Rao", phone="+91 98300 56789", email="sunita.rao@metro.co.in", address="Plot 89, Road No. 10, Banjara Hills, Hyderabad")
    c5 = Customer(name="Vikram Malhotra", phone="+91 98765 67890", email="vmalhotra@gmail.com", address="312 Model Town, Ludhiana, Punjab")
    
    db.session.add_all([c1, c2, c3, c4, c5])
    db.session.flush()

    # 2. Vehicles
    v1 = Vehicle(customer_id=c1.id, license_plate="MH 02 CL 4591", make="Maruti Suzuki", model="Dzire ZXi", year=2021, vin="MA3EJD12S00123456", mileage=42300, fuel_type="Petrol", color="Magma Grey")
    v2 = Vehicle(customer_id=c2.id, license_plate="DL 3C AB 1234", make="Hyundai", model="Creta SX (O)", year=2020, vin="MALC381CLKM654321", mileage=58900, fuel_type="Diesel", color="Polar White")
    v3 = Vehicle(customer_id=c3.id, license_plate="KA 05 MN 7890", make="Tata", model="Nexon EV Max", year=2022, vin="MAT613123NPA789012", mileage=29400, fuel_type="Electric", color="Intensi Teal")
    v4 = Vehicle(customer_id=c4.id, license_plate="TS 09 XY 4321", make="Honda", model="City ZX", year=2019, vin="MAKGM6680KAA12389", mileage=64100, fuel_type="Petrol", color="Golden Brown")
    v5 = Vehicle(customer_id=c5.id, license_plate="PB 10 ZQ 9988", make="Mahindra", model="XUV700 AX7L", year=2023, vin="MA1TA2PK4P6B98765", mileage=19200, fuel_type="Diesel", color="Midnight Black")
    v6 = Vehicle(customer_id=c1.id, license_plate="MH 04 ER 8765", make="Toyota", model="Innova Crysta 2.4 VX", year=2018, vin="MBJ11BA400112233", mileage=89500, fuel_type="Diesel", color="Silver Metallic")

    db.session.add_all([v1, v2, v3, v4, v5, v6])
    db.session.flush()

    # 3. Mechanics
    m1 = Mechanic(name="Suresh Jadhav", phone="+91 98920 11223", specialty="Engine & Transmission Diagnostics", status="Busy", hourly_rate=Decimal("550.00"))
    m2 = Mechanic(name="Rakesh Kumar", phone="+91 98101 22334", specialty="Brakes, Suspension & Wheel Alignment", status="Available", hourly_rate=Decimal("450.00"))
    m3 = Mechanic(name="Ananya Sengupta", phone="+91 98311 33445", specialty="Auto Electrical, Sensor & EV Systems", status="Available", hourly_rate=Decimal("600.00"))
    m4 = Mechanic(name="Deepak Chauhan", phone="+91 98290 44556", specialty="General Maintenance & AC Systems", status="Busy", hourly_rate=Decimal("400.00"))
    m5 = Mechanic(name="Manpreet Singh", phone="+91 98140 55667", specialty="Heavy Duty, Tires & Exhaust Systems", status="On Leave", hourly_rate=Decimal("420.00"))

    db.session.add_all([m1, m2, m3, m4, m5])
    db.session.flush()

    # 4. SpareParts (pricing in INR, with low-stock alerts)
    p1 = SparePart(part_number="FLT-OIL-001", name="Synthetic Engine Oil Filter PH7317", category="Filters", cost_price=Decimal("220.00"), selling_price=Decimal("450.00"), stock_quantity=28, min_reorder_level=10, location_bin="A1-04")
    p2 = SparePart(part_number="FLT-AIR-002", name="High Performance Engine Air Filter", category="Filters", cost_price=Decimal("380.00"), selling_price=Decimal("750.00"), stock_quantity=14, min_reorder_level=8, location_bin="A1-05")
    p3 = SparePart(part_number="BRK-PAD-101", name="Ceramic Front Brake Pad Set (D1322)", category="Brakes", cost_price=Decimal("1200.00"), selling_price=Decimal("2600.00"), stock_quantity=3, min_reorder_level=6, location_bin="B2-12") # LOW STOCK!
    p4 = SparePart(part_number="BRK-ROT-201", name="Vented Front Brake Rotor 280mm", category="Brakes", cost_price=Decimal("1800.00"), selling_price=Decimal("3800.00"), stock_quantity=2, min_reorder_level=4, location_bin="B2-15") # LOW STOCK!
    p5 = SparePart(part_number="FLUID-OIL-5W30", name="Full Synthetic 5W-30 Motor Oil (3.5L)", category="Fluids", cost_price=Decimal("1650.00"), selling_price=Decimal("2950.00"), stock_quantity=19, min_reorder_level=8, location_bin="C3-01")
    p6 = SparePart(part_number="FLUID-BRK-DOT4", name="DOT 4 Brake Fluid (500ml)", category="Fluids", cost_price=Decimal("180.00"), selling_price=Decimal("380.00"), stock_quantity=12, min_reorder_level=5, location_bin="C3-03")
    p7 = SparePart(part_number="IGN-SPK-NGK", name="NGK Laser Iridium Spark Plug Set (x4)", category="Ignition", cost_price=Decimal("1100.00"), selling_price=Decimal("2200.00"), stock_quantity=8, min_reorder_level=6, location_bin="D1-09")
    p8 = SparePart(part_number="BAT-AGM-12V", name="Exide / Amaron 12V 65Ah Heavy Duty Battery", category="Electrical", cost_price=Decimal("4200.00"), selling_price=Decimal("6800.00"), stock_quantity=1, min_reorder_level=3, location_bin="E4-01") # LOW STOCK!
    p9 = SparePart(part_number="SUSP-STRUT-F", name="Front Quick-Strut Shock Assembly", category="Suspension", cost_price=Decimal("2800.00"), selling_price=Decimal("5200.00"), stock_quantity=4, min_reorder_level=4, location_bin="F1-02")

    db.session.add_all([p1, p2, p3, p4, p5, p6, p7, p8, p9])
    db.session.flush()

    today = date.today()
    yesterday = today - timedelta(days=1)
    two_days_ago = today - timedelta(days=2)
    tomorrow = today + timedelta(days=1)
    next_week = today + timedelta(days=5)

    # 5. ServiceBookings
    b1 = ServiceBooking(
        booking_number="BK-2026-00101",
        customer_id=c1.id,
        vehicle_id=v1.id,
        booking_date=two_days_ago,
        booking_time="09:00 AM",
        service_type="Comprehensive 40,000-km Periodic Service",
        status="Completed",
        notes="Customer noticed slight squeaking during cold starts and brake squeal."
    )
    b2 = ServiceBooking(
        booking_number="BK-2026-00102",
        customer_id=c2.id,
        vehicle_id=v2.id,
        booking_date=today,
        booking_time="10:30 AM",
        service_type="Front Brake Overhaul & Disc Rotor Replacement",
        status="In Progress",
        notes="Vibration through steering wheel when braking from highway speed."
    )
    b3 = ServiceBooking(
        booking_number="BK-2026-00098",
        customer_id=c4.id,
        vehicle_id=v4.id,
        booking_date=yesterday,
        booking_time="02:00 PM",
        service_type="Check Engine Diagnostics & Spark Plug Refresh",
        status="Missed",
        notes="Customer booked online. No response to confirmation SMS."
    )
    b4 = ServiceBooking(
        booking_number="BK-2026-00104",
        customer_id=c3.id,
        vehicle_id=v3.id,
        booking_date=tomorrow,
        booking_time="11:00 AM",
        service_type="EV High Voltage System Health Check & Cabin Filter",
        status="Confirmed",
        notes="Scheduled annual health diagnostic for battery cooling loop."
    )
    b5 = ServiceBooking(
        booking_number="BK-2026-00105",
        customer_id=c5.id,
        vehicle_id=v5.id,
        booking_date=next_week,
        booking_time="08:30 AM",
        service_type="Heavy Duty Differential & Transmission Fluid Flush",
        status="Pending",
        notes="Requested fluid sample inspection before long road trip."
    )

    db.session.add_all([b1, b2, b3, b4, b5])
    db.session.flush()

    # 6. ServiceDetails (Job Details)
    sd1 = ServiceDetail(
        booking_id=b1.id,
        mechanic_id=m4.id,
        job_description="Performed 40k km periodic maintenance: replaced motor oil, oil filter, air filter, and rotated tires. Inspected brake pads at 6mm remaining.",
        diagnosis="Drive belt in good condition. Cold start squeak was due to minor belt tensioner dryness, lubricated and tension verified.",
        labor_hours=Decimal("2.50"),
        labor_cost=Decimal("1000.00"),
        status="Completed",
        started_at=datetime.now(timezone.utc) - timedelta(days=2, hours=6),
        completed_at=datetime.now(timezone.utc) - timedelta(days=2, hours=3)
    )
    sd2 = ServiceDetail(
        booking_id=b2.id,
        mechanic_id=m1.id,
        job_description="Disassemble front brake calipers, inspect slide pins, replace worn ceramic brake pads and install vented rotors.",
        diagnosis="Front brake pads severely worn down to 1.8mm. Rotors show uneven heat scoring causing brake shudder.",
        labor_hours=Decimal("2.00"),
        labor_cost=Decimal("1100.00"),
        status="In Progress",
        started_at=datetime.now(timezone.utc) - timedelta(hours=2),
        completed_at=None
    )

    db.session.add_all([sd1, sd2])
    db.session.flush()

    # 7. PartUsage
    u1 = PartUsage(service_detail_id=sd1.id, part_id=p1.id, quantity=1, unit_price=Decimal("450.00"), subtotal=Decimal("450.00"))
    u2 = PartUsage(service_detail_id=sd1.id, part_id=p2.id, quantity=1, unit_price=Decimal("750.00"), subtotal=Decimal("750.00"))
    u3 = PartUsage(service_detail_id=sd1.id, part_id=p5.id, quantity=1, unit_price=Decimal("2950.00"), subtotal=Decimal("2950.00"))

    u4 = PartUsage(service_detail_id=sd2.id, part_id=p3.id, quantity=1, unit_price=Decimal("2600.00"), subtotal=Decimal("2600.00"))
    u5 = PartUsage(service_detail_id=sd2.id, part_id=p4.id, quantity=2, unit_price=Decimal("3800.00"), subtotal=Decimal("7600.00"))
    u6 = PartUsage(service_detail_id=sd2.id, part_id=p6.id, quantity=1, unit_price=Decimal("380.00"), subtotal=Decimal("380.00"))

    db.session.add_all([u1, u2, u3, u4, u5, u6])
    db.session.flush()

    # 8. Bills (INR)
    parts_total_1 = Decimal("450.00") + Decimal("750.00") + Decimal("2950.00") # 4150.00
    labor_total_1 = Decimal("1000.00")
    tax_1 = Decimal("412.00") # 8% GST approx
    discount_1 = Decimal("200.00")
    grand_total_1 = parts_total_1 + labor_total_1 + tax_1 - discount_1 # 5362.00

    bill1 = Bill(
        invoice_number="INV-2026-00412",
        booking_id=b1.id,
        customer_id=c1.id,
        parts_total=parts_total_1,
        labor_total=labor_total_1,
        tax_amount=tax_1,
        discount_amount=discount_1,
        grand_total=grand_total_1,
        payment_status="Paid",
        issued_at=datetime.now(timezone.utc) - timedelta(days=2, hours=3)
    )

    parts_total_2 = Decimal("2600.00") + Decimal("7600.00") + Decimal("380.00") # 10580.00
    labor_total_2 = Decimal("1100.00")
    tax_2 = Decimal("934.40") # 8% GST approx
    discount_2 = Decimal("0.00")
    grand_total_2 = parts_total_2 + labor_total_2 + tax_2 - discount_2 # 12614.40

    bill2 = Bill(
        invoice_number="INV-2026-00413",
        booking_id=b2.id,
        customer_id=c2.id,
        parts_total=parts_total_2,
        labor_total=labor_total_2,
        tax_amount=tax_2,
        discount_amount=discount_2,
        grand_total=grand_total_2,
        payment_status="Partially Paid",
        issued_at=datetime.now(timezone.utc) - timedelta(hours=2)
    )

    db.session.add_all([bill1, bill2])
    db.session.flush()

    # 9. Payments (INR)
    pay1 = Payment(
        bill_id=bill1.id,
        amount=grand_total_1,
        payment_method="UPI / Online",
        transaction_reference="UPI-HDFC-982341",
        payment_date=datetime.now(timezone.utc) - timedelta(days=2, hours=2, minutes=45),
        notes="UPI transfer via GooglePay"
    )
    pay2 = Payment(
        bill_id=bill2.id,
        amount=Decimal("5000.00"),
        payment_method="Credit Card",
        transaction_reference="CC-ICICI-8819203",
        payment_date=datetime.now(timezone.utc) - timedelta(hours=1, minutes=30),
        notes="Advance token deposit paid via card swipe upon vehicle drop-off"
    )

    db.session.add_all([pay1, pay2])
    db.session.commit()
    print("AutoMitra sample data successfully seeded (INR)!")

if __name__ == '__main__':
    from app import create_app
    app = create_app()
    with app.app_context():
        seed_database()
