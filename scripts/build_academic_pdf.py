#!/usr/bin/env python3
"""Build Academic Project Report PDF for AutoMitra using ReportLab."""

import os
import sys
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    """Canvas that performs a two-pass calculation for total page counts."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        if self._pageNumber > 1:
            self.saveState()
            self.setFont("Helvetica", 9)
            self.setFillColor(colors.HexColor("#718096"))
            # Header
            self.drawString(54, letter[1] - 36, "AutoMitra — Vehicle Service Center Management System | Academic Project Report")
            self.setStrokeColor(colors.HexColor("#CBD5E0"))
            self.setLineWidth(0.5)
            self.line(54, letter[1] - 42, letter[0] - 54, letter[1] - 42)

            # Footer
            self.line(54, 45, letter[0] - 54, 45)
            self.drawString(54, 32, "Confidential & Academic Release — v1.0.0")
            page_text = f"Page {self._pageNumber} of {page_count}"
            self.drawRightString(letter[0] - 54, 32, page_text)
            self.restoreState()

def generate_pdf(output_path):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()
    
    # Custom styles
    primary_color = colors.HexColor("#1A365D")
    secondary_color = colors.HexColor("#2B6CB0")
    dark_text = colors.HexColor("#2D3748")
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=primary_color,
        alignment=1, # Center
        spaceAfter=10
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=12,
        leading=16,
        textColor=secondary_color,
        alignment=1,
        spaceAfter=20
    )
    
    h1_style = ParagraphStyle(
        'ReportH1',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=20,
        textColor=primary_color,
        spaceBefore=14,
        spaceAfter=8,
        keepWithNext=True
    )
    
    h2_style = ParagraphStyle(
        'ReportH2',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=secondary_color,
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'ReportBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=dark_text,
        spaceAfter=6
    )

    body_bold = ParagraphStyle(
        'ReportBodyBold',
        parent=body_style,
        fontName='Helvetica-Bold'
    )

    bullet_style = ParagraphStyle(
        'ReportBullet',
        parent=body_style,
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=3
    )

    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.white,
        alignment=1
    )

    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10.5,
        textColor=dark_text
    )

    table_cell_bold = ParagraphStyle(
        'TableCellBold',
        parent=table_cell_style,
        fontName='Helvetica-Bold'
    )

    story = []

    # --- Title Page Header ---
    story.append(Spacer(1, 20))
    story.append(Paragraph("AutoMitra — Vehicle Service Center Management System", title_style))
    story.append(Paragraph("A Centralized Relational Web Application with Authoritative Billing, Atomic Inventory Deductions, Restrictive Historical Data Preservation, and Automated Test Verification", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=2, color=primary_color, spaceBefore=5, spaceAfter=15))

    # Project Metadata Table
    metadata_data = [
        [Paragraph("Project Title", table_cell_bold), Paragraph("AutoMitra — Vehicle Service Center Management System", table_cell_style)],
        [Paragraph("Author / Contributor", table_cell_bold), Paragraph("Krrish Prajapati (@krrishprajapati1111) — Mechatronics Engineering", table_cell_style)],
        [Paragraph("Target Currency", table_cell_bold), Paragraph("Indian Rupees (₹ INR) Localization", table_cell_style)],
        [Paragraph("Software Architecture", table_cell_bold), Paragraph("3-Tier MVC Web Application (Flask 3.1, SQLAlchemy 2.0, Flask-WTF)", table_cell_style)],
        [Paragraph("Database Engines", table_cell_bold), Paragraph("MySQL 8.0+ / MariaDB 10.4+ (InnoDB Engine) & Embedded SQLite", table_cell_style)],
        [Paragraph("Verified Test Suite", table_cell_bold), Paragraph("53 Tests Passed (0 Failed, 0 Skipped, 0 Warnings, 100% CI Green)", table_cell_style)],
        [Paragraph("GitHub Repository", table_cell_bold), Paragraph("https://github.com/AdigarlaRakesh-1/Automitra (v1.0.0 Release)", table_cell_style)],
    ]
    meta_table = Table(metadata_data, colWidths=[1.8 * inch, 5.0 * inch])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F7FAFC")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 15))

    # --- 1. Abstract ---
    story.append(Paragraph("1. Abstract", h1_style))
    story.append(Paragraph(
        "Small and medium-sized automotive service centers operate in high-turnaround, margin-sensitive environments where administrative inaccuracies directly degrade profitability and customer trust. Common operational bottlenecks include fragmented customer visit histories, unmonitored appointment cancellations, uneven technician bay allocation, unexpected spare parts stockouts during active jobs, client-tamperable invoice calculations, and accidental cascade deletion of financial and service records.",
        body_style
    ))
    story.append(Paragraph(
        "<b>AutoMitra</b> is an open-source, centralized garage management web application engineered specifically to solve these challenges within Indian workshop workflows (localized in Indian Rupees, ₹ INR). The system is implemented in Python and Flask using SQLAlchemy ORM, backed natively by MySQL 8.0/MariaDB and embedded SQLite. Key innovations include server-authoritative financial calculation with exact two-decimal <code>Decimal('0.01')</code> quantization, atomic SQL conditional stock deductions preventing concurrent race conditions, restrictive foreign key deletion rules (<code>ON DELETE RESTRICT</code>) protecting historical bills and payment records, full cryptographic CSRF protection, and a 53-item automated regression suite verified across SQLite, live MariaDB/MySQL, and GitHub Actions CI containers.",
        body_style
    ))

    # --- 2. Problem Statement ---
    story.append(Paragraph("2. Problem Statement & Core Workshop Bottlenecks", h1_style))
    bottlenecks = [
        ("1. Duplicate Customer Profiles", "Fragmented records across visits cause conflicting contact details, communication breakdown, and distorted service histories."),
        ("2. Missed Service Bookings", "Unmonitored appointments lead to vacant bays, unutilized technician hours, and customer churn when follow-ups are omitted."),
        ("3. Technician Bay Allocation Imbalance", "Lack of real-time visibility into mechanic statuses (Available, Busy, On Leave) and hourly rates causes bay bottlenecks."),
        ("4. Spare Part Stock Outages & Race Conditions", "Inventory depletion during active repairs stalls workshop turnaround. Python-level non-atomic stock checks permit concurrent requests to drive inventory below zero."),
        ("5. Billing Inaccuracies & Client Tampering", "Discrepancies between parts installed and items billed, compounded by client-side POST total manipulation and floating-point precision loss."),
        ("6. Historical Data Loss via Cascade Deletion", "Standard cascading foreign key configurations (ON DELETE CASCADE) silently erase accounting records and payment histories when customer or vehicle records are purged.")
    ]
    for title, desc in bottlenecks:
        story.append(Paragraph(f"• <b>{title}</b>: {desc}", bullet_style))

    story.append(PageBreak())

    # --- 3. Existing vs Proposed System ---
    story.append(Paragraph("3. Existing System vs. Proposed AutoMitra System", h1_style))
    comp_data = [
        [Paragraph("Operational Dimension", table_header_style), Paragraph("Legacy Manual / Spreadsheet System", table_header_style), Paragraph("Proposed AutoMitra System", table_header_style)],
        [Paragraph("Customer Tracking", table_cell_bold), Paragraph("Fragmented paper records; phone variations duplicate entries.", table_cell_style), Paragraph("Live debounced AJAX duplicate detection on unique phone/email.", table_cell_style)],
        [Paragraph("Booking Management", table_cell_bold), Paragraph("Physical registers; missed bookings are forgotten.", table_cell_style), Paragraph("Proactive missed booking dashboard with 1-click rescheduling.", table_cell_style)],
        [Paragraph("Inventory Control", table_cell_bold), Paragraph("Manual counts; stockouts discovered mid-repair.", table_cell_style), Paragraph("Atomic conditional decrement (WHERE stock_quantity >= :qty).", table_cell_style)],
        [Paragraph("Billing Calculations", table_cell_bold), Paragraph("Handwritten bills; vulnerable to client-side total manipulation.", table_cell_style), Paragraph("Server-authoritative calculations from database labor & parts records.", table_cell_style)],
        [Paragraph("Currency & Math", table_cell_bold), Paragraph("Inconsistent rounding; IEEE 754 float drift.", table_cell_style), Paragraph("Exact Decimal('0.01') precision localized in Indian Rupees (₹).", table_cell_style)],
        [Paragraph("Historical Preservation", table_cell_bold), Paragraph("Accidental disposal or cascade deletion of records.", table_cell_style), Paragraph("Strict ON DELETE RESTRICT on bills, payments, and bookings.", table_cell_style)],
        [Paragraph("Security & CSRF", table_cell_bold), Paragraph("No anti-CSRF protection; raw SQL/stack traces leaked.", table_cell_style), Paragraph("Cryptographic CSRF on all 18 forms; sanitized HTTP 500 error pages.", table_cell_style)],
        [Paragraph("Testing & Verification", table_cell_bold), Paragraph("Manual spot checking; zero regression safety.", table_cell_style), Paragraph("53 automated tests passing on SQLite, live MySQL, and CI.", table_cell_style)],
    ]
    comp_table = Table(comp_data, colWidths=[1.5 * inch, 2.6 * inch, 2.7 * inch])
    comp_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), primary_color),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E0")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#FFFFFF"), colors.HexColor("#F7FAFC")]),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(comp_table)
    story.append(Spacer(1, 12))

    # --- 4. Database Architecture & Schema ---
    story.append(Paragraph("4. Database Architecture & Relational Schema (9 Tables)", h1_style))
    story.append(Paragraph(
        "AutoMitra is structured around a centralized relational schema comprising 9 interconnected tables designed to represent workshop operations with strict referential integrity and zero redundancy:",
        body_style
    ))

    schema_data = [
        [Paragraph("Table Name", table_header_style), Paragraph("Primary / Foreign Keys", table_header_style), Paragraph("Integrity Constraints & Deletion Rules", table_header_style), Paragraph("Key Operational Fields", table_header_style)],
        [Paragraph("Customers", table_cell_bold), Paragraph("PK: id", table_cell_style), Paragraph("phone (UNIQUE), email (Indexed)", table_cell_style), Paragraph("name, phone, email, address, created_at, updated_at", table_cell_style)],
        [Paragraph("Vehicles", table_cell_bold), Paragraph("PK: id\nFK: customer_id", table_cell_style), Paragraph("license_plate (UNIQUE), vin (UNIQUE, NULLable)\nFK: ON DELETE CASCADE (clean orphan deletion)", table_cell_style), Paragraph("license_plate, make, model, year, vin, mileage, fuel_type", table_cell_style)],
        [Paragraph("Mechanics", table_cell_bold), Paragraph("PK: id", table_cell_style), Paragraph("status IN (Available, Busy, On Leave)\nhourly_rate >= 0.00", table_cell_style), Paragraph("name, phone, specialty, status, hourly_rate (₹/hr)", table_cell_style)],
        [Paragraph("ServiceBookings", table_cell_bold), Paragraph("PK: id\nFK: customer_id, vehicle_id", table_cell_style), Paragraph("booking_number (UNIQUE)\nFKs: ON DELETE RESTRICT (preserves history)", table_cell_style), Paragraph("booking_number, booking_date, time, service_type, status", table_cell_style)],
        [Paragraph("ServiceDetails", table_cell_bold), Paragraph("PK: id\nFK: booking_id, mechanic_id", table_cell_style), Paragraph("booking_id (UNIQUE 1:1 constraint)\nFK booking: CASCADE; FK mechanic: SET NULL", table_cell_style), Paragraph("job_description, diagnosis, labor_hours, labor_cost (₹)", table_cell_style)],
        [Paragraph("SpareParts", table_cell_bold), Paragraph("PK: id", table_cell_style), Paragraph("part_number (UNIQUE SKU)\nstock_quantity >= 0, prices >= 0.00", table_cell_style), Paragraph("part_number, name, category, cost_price, selling_price, stock", table_cell_style)],
        [Paragraph("PartUsage", table_cell_bold), Paragraph("PK: id\nFK: service_detail_id, part_id", table_cell_style), Paragraph("quantity > 0, unit_price >= 0.00\nFK detail: CASCADE; FK part: RESTRICT", table_cell_style), Paragraph("quantity, unit_price (₹), subtotal (₹), used_at", table_cell_style)],
        [Paragraph("Bills", table_cell_bold), Paragraph("PK: id\nFK: booking_id, customer_id", table_cell_style), Paragraph("invoice_number (UNIQUE)\nFKs: ON DELETE RESTRICT (audit locked)", table_cell_style), Paragraph("parts_total, labor_total, tax_amount, discount, grand_total", table_cell_style)],
        [Paragraph("Payments", table_cell_bold), Paragraph("PK: id\nFK: bill_id", table_cell_style), Paragraph("transaction_reference (UNIQUE, NULLable)\nFK bill: ON DELETE RESTRICT", table_cell_style), Paragraph("amount (₹), payment_method, transaction_reference, notes", table_cell_style)],
    ]
    schema_table = Table(schema_data, colWidths=[1.1 * inch, 1.8 * inch, 2.1 * inch, 1.8 * inch])
    schema_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), primary_color),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E0")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#FFFFFF"), colors.HexColor("#F7FAFC")]),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    story.append(schema_table)

    story.append(PageBreak())

    # --- 5. Normalization Analysis ---
    story.append(Paragraph("5. Database Normalization Proof (1NF to BCNF)", h1_style))
    story.append(Paragraph(
        "AutoMitra's schema was subjected to rigorous database normalization analysis from First Normal Form (1NF) through Boyce-Codd Normal Form (BCNF) to establish mathematical proof of data redundancy elimination:",
        body_style
    ))
    story.append(Paragraph("• <b>First Normal Form (1NF)</b>: All domain values are atomic scalars. Repeating collections (e.g. multiple parts consumed on a job card or multiple partial payments recorded on an invoice) are normalized into independent child entities (<code>PartUsage</code> and <code>Payments</code>).", bullet_style))
    story.append(Paragraph("• <b>Second Normal Form (2NF)</b>: Every table utilizes a single-attribute surrogate primary key <code>id</code> (|PK| = 1). Since no composite keys exist, proper subsets of candidate keys are empty sets, eliminating the mathematical possibility of partial key dependencies.", bullet_style))
    story.append(Paragraph("• <b>Third Normal Form (3NF)</b>: Non-prime attributes depend solely and directly on primary keys without transitive dependencies (X → Y → Z). Customer profiles are isolated from vehicle entities; job cards capture point-in-time unit prices without replicating catalog metadata; invoices record immutable historical financial totals.", bullet_style))
    story.append(Paragraph("• <b>Boyce-Codd Normal Form (BCNF)</b>: For every non-trivial functional dependency X → Y, determinant X is a superkey. Attributes possessing unique functional determination (e.g. <code>Customers.phone</code>, <code>Vehicles.license_plate</code>, <code>SpareParts.part_number</code>, <code>ServiceBookings.booking_number</code>, <code>Bills.invoice_number</code>) are defined with database UNIQUE constraints.", bullet_style))

    # --- 6. Core Engineering Implementations ---
    story.append(Paragraph("6. Key Engineering Implementations & Vulnerability Remediation", h1_style))
    
    story.append(Paragraph("6.1 Concurrency-Safe Atomic Stock Decrement", h2_style))
    story.append(Paragraph(
        "To prevent race conditions where concurrent requests cause negative stock quantities, AutoMitra replaces Python-level validation with atomic conditional SQL updates: <code>UPDATE SparePart SET stock_quantity = stock_quantity - :qty WHERE id = :id AND stock_quantity >= :qty</code>. If another thread consumes available stock, zero rows are updated, triggering an immediate database rollback and user alert.",
        body_style
    ))

    story.append(Paragraph("6.2 Authoritative Billing & Exact Decimal Quantization", h2_style))
    story.append(Paragraph(
        "Client browser POST payloads cannot be trusted with monetary values. AutoMitra calculates all invoices authoritatively on the server from raw database labor hours and part usages. Calculations utilize Python's <code>Decimal('0.01')</code> with <code>ROUND_HALF_UP</code>, eliminating binary floating-point rounding errors and strictly bounding taxes (0–100%) and discounts.",
        body_style
    ))

    story.append(Paragraph("6.3 Restrictive Historical Deletion Rules (ON DELETE RESTRICT)", h2_style))
    story.append(Paragraph(
        "Financial auditability requires that paid invoices and service histories are never deleted. Foreign keys on <code>Payments.bill_id</code>, <code>Bills.booking_id</code>, and <code>ServiceBookings.customer_id</code> enforce <code>ON DELETE RESTRICT</code>. In SQLite development environments, SQLAlchemy engine listeners explicitly enforce this via <code>PRAGMA foreign_keys=ON</code>.",
        body_style
    ))

    story.append(Paragraph("6.4 Empty-String Unique Constraint & Safe Migration Protocol", h2_style))
    story.append(Paragraph(
        "In MySQL InnoDB unique indexes, multiple NULLs are permitted, but empty strings (<code>''</code>) are treated as duplicate values, resulting in error 1062 during unique constraint creation. AutoMitra's migration pre-flight checks inspect all non-NULL references (<code>WHERE transaction_reference IS NOT NULL GROUP BY transaction_reference HAVING COUNT(*) > 1</code>) and provide auditable procedures to safely convert unprovided references to NULL prior to schema alteration.",
        body_style
    ))

    story.append(Paragraph("6.5 Safe MySQL Test Database Lifecycle", h2_style))
    story.append(Paragraph(
        "To prevent automated tests from ever destroying or colliding with pre-existing development databases, <code>SafeMySQLTestDatabase</code> generates UUID-isolated database names, queries <code>INFORMATION_SCHEMA.SCHEMATA</code> before DDL execution, tracks test ownership, and guarantees administrative connection closure under all error and collision paths.",
        body_style
    ))

    story.append(PageBreak())

    # --- 7. Automated Test Verification Results ---
    story.append(Paragraph("7. Comprehensive Automated Test Verification Results", h1_style))
    story.append(Paragraph(
        "The AutoMitra test suite consists of <b>53 automated regression and integration tests</b> implemented in <code>test_app.py</code>. The entire suite executes in ~8.0 seconds locally and 43 seconds on GitHub Actions CI with a MySQL 8.0 service container, achieving a <b>100% pass rate with zero warnings</b>:",
        body_style
    ))

    test_summary_data = [
        [Paragraph("Subsystem Category", table_header_style), Paragraph("Tests Run", table_header_style), Paragraph("Key Test Cases Verified", table_header_style), Paragraph("Status", table_header_style)],
        [Paragraph("Seeding & Core Logic", table_cell_bold), Paragraph("3", table_cell_style), Paragraph("Table creation, duplicate customer detection, missed booking detection", table_cell_style), Paragraph("PASSED", table_cell_bold)],
        [Paragraph("Inventory & Concurrency", table_cell_bold), Paragraph("6", table_cell_style), Paragraph("Atomic stock decrements, low stock alerts, multithreaded concurrency, restock bounds", table_cell_style), Paragraph("PASSED", table_cell_bold)],
        [Paragraph("Authorization & Bounds", table_cell_bold), Paragraph("8", table_cell_style), Paragraph("Cross-job IDOR rejection, vehicle-customer ownership, boundary validations", table_cell_style), Paragraph("PASSED", table_cell_bold)],
        [Paragraph("Financial & Billing", table_cell_bold), Paragraph("9", table_cell_style), Paragraph("Authoritative calculations, Decimal math, bill editing lock, overpayment rejection", table_cell_style), Paragraph("PASSED", table_cell_bold)],
        [Paragraph("Historical Preservation", table_cell_bold), Paragraph("11", table_cell_style), Paragraph("ON DELETE RESTRICT on bills & payments, booking status locks on paid bills", table_cell_style), Paragraph("PASSED", table_cell_bold)],
        [Paragraph("Security & Infrastructure", table_cell_bold), Paragraph("10", table_cell_style), Paragraph("CSRF token enforcement across 18 forms, production 500 error sanitization, SQLite mode", table_cell_style), Paragraph("PASSED", table_cell_bold)],
        [Paragraph("MySQL Integration & Lifecycle", table_cell_bold), Paragraph("6", table_cell_style), Paragraph("SafeMySQLTestDatabase lifecycle, live MySQL DDL, non-destructive migration verification", table_cell_style), Paragraph("PASSED", table_cell_bold)],
        [Paragraph("Total Verified Suite", table_cell_bold), Paragraph("53", table_cell_bold), Paragraph("All functional, security, financial, and integration criteria met", table_cell_bold), Paragraph("100% PASS", table_cell_bold)],
    ]
    test_table = Table(test_summary_data, colWidths=[1.8 * inch, 0.8 * inch, 3.4 * inch, 0.8 * inch])
    test_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), primary_color),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E0")),
        ('ROWBACKGROUNDS', (0,1), (-1,-2), [colors.HexColor("#FFFFFF"), colors.HexColor("#F7FAFC")]),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#EBF8FF")),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(test_table)
    story.append(Spacer(1, 15))

    # --- 8. Limitations & Future Enhancements ---
    story.append(Paragraph("8. Operational Boundaries, Limitations & Future Work", h1_style))
    story.append(Paragraph(
        "<b>Current Architectural Limitations</b>:<br/>"
        "1. <b>Single-Operator Design</b>: AutoMitra is currently engineered as an internal service desk console without multi-user role-based authentication (RBAC).<br/>"
        "2. <b>Network Deployment Constraint</b>: The system must not be exposed directly to the public internet without an authenticating reverse proxy (Cloudflare Access, Nginx HTTP Auth, or Tailscale VPN).<br/>"
        "3. <b>Diagnostic Hardware</b>: Vehicle diagnostic data is entered manually; direct physical OBD-II scanning interfaces are not currently embedded.",
        body_style
    ))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "<b>Proposed Future Enhancements</b>:<br/>"
        "1. <b>Role-Based Authentication</b>: Integration of <code>Flask-Login</code> and <code>bcrypt</code> password hashing to distinguish Mechanic, Cashier, and Administrator views.<br/>"
        "2. <b>Automated Customer Messaging</b>: WhatsApp Business and SMS gateways for appointment confirmations, status alerts, and invoice delivery.<br/>"
        "3. <b>Digital Payment Gateway Integration</b>: Razorpay / UPI Intent deep-linking for seamless mobile customer payments.<br/>"
        "4. <b>Predictive Maintenance Analytics</b>: Mileage-interval algorithms to proactively notify customers of scheduled component replacements.",
        body_style
    ))
    story.append(Spacer(1, 15))

    # --- 9. Conclusion ---
    story.append(Paragraph("9. Conclusion", h1_style))
    story.append(Paragraph(
        "The AutoMitra Vehicle Service Center Management System demonstrates how disciplined relational database engineering, authoritative financial math, and atomic concurrency controls successfully eliminate operational inefficiencies in automotive workshops. By enforcing structural data preservation and comprehensive test-driven quality assurance, AutoMitra establishes a resilient, production-ready foundation for modern garage management.",
        body_style
    ))

    # Build document
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Academic Report PDF successfully compiled at: {output_path}")

if __name__ == "__main__":
    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")
    pdf_path = os.path.join(out_dir, "AutoMitra_Academic_Project_Report.pdf")
    generate_pdf(pdf_path)
