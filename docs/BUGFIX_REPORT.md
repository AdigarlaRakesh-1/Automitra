# AutoMitra — Bug Fixing, Security Hardening, Database Integrity, and Testing Report

**Repository**: `AdigarlaRakesh-1/Automitra`  
**Working Branch**: `fix/critical-validation-and-integrity`  
**Target / Base Branch**: `main`  
**Execution Environment**: Python 3.14.6, Flask 3.1.0, SQLAlchemy 2.0.38, Flask-SQLAlchemy 3.1.1, PyMySQL 1.1.1, pytest 9.1.1  

---

## 1. Executive Summary

This engineering effort conducted a complete audit and incremental repair of the **AutoMitra** Vehicle Service Center Management System. Across 10 methodical phases, every confirmed vulnerability, concurrency flaw, financial calculation loophole, database inconsistency, and deprecation warning was resolved, verified through regression tests, and cleanly committed to `fix/critical-validation-and-integrity`.

### Key Metrics
- **Baseline Test Suite**: 7 tests passed (with 1,307 deprecation/legacy warnings).
- **Final Test Suite**: 32 tests passed (0 failures, 0 warnings, execution time ~7.6s).
- **Commits Created**: 10 incremental, reviewable Git commits on `fix/critical-validation-and-integrity`.
- **Destructive Database Actions**: 0 (No production or real database was altered, reset, or overwritten; `schema.sql` was never run against live data).
- **Base Branch `main`**: Untouched.

---

## 2. Issues Fixed, Severity, and Root Cause

| Phase | Issue Description | Severity | Root Cause |
|---|---|---|---|
| **Phase 0** | Global Python environment contamination & missing dev test dependencies | Low | No project-local virtual environment was isolated; test runner was unpinned. |
| **Phase 1** | IDOR Cross-Job Part Usage Deletion (`/services/<id>/remove_part/<usage_id>`) | **Critical** | Missing entity ownership check between `PartUsage.service_detail_id` and `ServiceDetail.id`. An attacker could delete parts from any job. |
| **Phase 1** | Cross-Customer Vehicle Hijacking in Bookings (`/bookings/new`) | **High** | Missing ownership validation between `Vehicle.customer_id` and `Customer.id`. Customer A could book Customer B's vehicle. |
| **Phase 1** | Negative/Malformed Service Labor Inputs | Medium | Absence of server-side numeric bounds validation on labor hours, rates, and service statuses. |
| **Phase 2** | Negative Inventory Stock & Concurrency Race Conditions | **Critical** | Part usage additions checked stock in Python before issuing separate update without row locking or atomic bounds checking. Concurrent requests could drive stock below zero. |
| **Phase 3** | Authoritative Billing Tampering via Browser Form Values | **Critical** | `/billing/generate/<id>` trusted client-supplied POST totals instead of calculating authoritatively from database job parts and labor records. |
| **Phase 3** | Unbounded Discounts & Negative Taxes | High | Missing server-side boundary checks on tax rate (0-100%) and discount amounts, allowing invoices with negative balances. |
| **Phase 3** | Floating-point Inaccuracy in Financial Balances & Payment Processing | High | Billing balance calculations used Python `float`, risking binary IEEE 754 precision errors on rupee values. Missing balance checks permitted overpayments. |
| **Phase 4** | Cascade Deletion of Invoices, Audit Logs, and Service Records | **Critical** | `models.py` had `cascade='all, delete-orphan'` on `Customer.bills`, `Customer.bookings`, and `Vehicle.bookings`. Deleting a customer or vehicle deleted accounting audit records. |
| **Phase 5** | Database Schema vs ORM Mismatches | High | `Customer.updated_at` was missing from ORM model; MySQL ENUM constraints existed in `schema.sql` but were unconstrained in ORM strings; `ServiceDetail.booking_id` lacked uniqueness constraint. |
| **Phase 5** | Uncontrolled Database Auto-Seeding on Module Import | Medium | `create_app()` unconditionally invoked `db.create_all()` and `seed_database()` during import, risking mutating development or testing databases simply by importing the app. |
| **Phase 6** | Hardcoded Credentials & Insecure Production Secrets | **Critical** | `config.py` fell back to hardcoded production keys; `DEBUG=True` was hardcoded in `app.run()`; `.env.example` had default `root` credentials. |
| **Phase 6** | Silent Fallback from MySQL to SQLite | **Critical** | If a configured MySQL connection failed, `app.py` silently redirected writes to a local SQLite file (`automitra.db`), causing silent production data divergence. |
| **Phase 7** | `UnboundLocalError` on `location_bin` in `inventory.py` | High | Variable `location_bin` was referenced when instantiating `SparePart` without being extracted from `request.form`. |
| **Phase 7** | Missing Vehicle & Mechanic Entity Existence & Range Checks | Medium | Adding vehicle permitted non-existent customer IDs, invalid year numbers, and negative mileage. Adding bookings permitted non-existent mechanic IDs. |
| **Phase 8** | 1,300+ Deprecation & Legacy API Warnings | Low / Quality | Python 3.14 deprecated naive `datetime.utcnow()`; SQLAlchemy 2.0 deprecated legacy `Query.get()` / `Model.query.get_or_404()`. |

---

## 3. Detailed Phase Breakdown and Verification

### Phase 0: Repository & Environment Isolation
- Created local `.venv` via `C:\Python314\python.exe -m venv .venv`.
- Created `requirements-dev.txt` (`pytest>=8.0.0`).
- Updated `.gitignore` to ensure `.venv/` and `venv/` are excluded.
- **Commit**: `d65c692` — *test: establish isolated test environment and developer dependencies*

### Phase 1: Cross-Entity Validation & Service Integrity
- **Files Modified**: `routes/services.py`, `routes/bookings.py`, `routes/inventory.py`.
- **Changes**: Enforced `usage.service_detail_id == job.id`; prevented removing parts from paid bills; verified customer-vehicle ownership (`vehicle.customer_id == customer.id`); bounded booking dates (2000–2100) and labor values.
- **Tests Added**: 4 regression tests.
- **Commit**: `725dec4` — *fix: validate booking ownership and enforce service part usage authorization*

### Phase 2: Inventory Consistency & Concurrency Protection
- **Files Modified**: `models.py`, `routes/services.py`, `routes/inventory.py`.
- **Changes**: Added SQL `CheckConstraint` on `SparePart` and `PartUsage`; implemented atomic conditional stock decrement queries:
  ```python
  db.session.query(SparePart).filter(
      SparePart.id == part.id,
      SparePart.stock_quantity >= quantity
  ).update({SparePart.stock_quantity: SparePart.stock_quantity - quantity}, synchronize_session='fetch')
  ```
- **Tests Added**: 2 concurrency and stock-check regression tests.
- **Commit**: `be107ab` — *fix: make inventory deductions transaction-safe and enforce stock constraints*

### Phase 3: Authoritative Billing & Decimal Precision
- **Files Modified**: `models.py`, `routes/billing.py`, `routes/payments.py`.
- **Changes**: Calculated parts and labor totals authoritatively from database records; bounded taxes (0–100%) and discounts (`<= subtotal + tax`); converted billing properties and payments to `Decimal('0.01')`; locked billed/paid invoices from unauthorized adjustments.
- **Tests Added**: 3 financial calculation regression tests.
- **Commit**: `430943b` — *fix: enforce authoritative billing calculations and decimal precision for payments*

### Phase 4: Historical Data Preservation & Cascade Deletion Safeguards
- **Files Modified**: `models.py`, `routes/customers.py`, `routes/vehicles.py`.
- **Changes**: Removed `cascade='all, delete-orphan'` from `Customer.bookings`, `Customer.bills`, and `Vehicle.bookings`; added pre-deletion checks blocking deletion of customers or vehicles with financial or service history; ensured unreferenced disposable records can still be deleted cleanly.
- **Tests Added**: 3 cascade deletion safeguard tests.
- **Commit**: `f8c630c` — *fix: preserve historical service and financial records against cascade deletions*

### Phase 5: Database Schema & ORM Alignment
- **Files Modified**: `models.py`, `app.py`.
- **Changes**: Added `Customer.updated_at` matching `schema.sql`; added SQL check constraints matching ENUM status values on `Mechanic`, `ServiceBooking`, `ServiceDetail`, `Bill`, and `Payment`; enforced 1:1 relationship on `ServiceDetail.booking_id` (`unique=True`); decoupled automatic seeding from module import.
- **Tests Added**: 3 metadata and constraint regression tests.
- **Commit**: `c26e018` — *fix: align ORM validation with database schema and isolate seeding*

### Phase 6: Configuration, Secrets & Startup Hardening
- **Files Modified**: `config.py`, `app.py`, `.env.example`.
- **Changes**: Required explicit `SECRET_KEY` in production; made `DEBUG` environment-driven (default `False` in production); prohibited silent fallback to SQLite when MySQL is configured; sanitized startup error reporting to avoid credential leaks.
- **Tests Added**: 3 configuration and startup failure tests.
- **Commit**: `26433d7` — *fix: harden application configuration, secrets, and startup*

### Phase 7: Route Validation & Input Security
- **Files Modified**: `routes/bookings.py`, `routes/inventory.py`, `routes/mechanics.py`, `routes/vehicles.py`.
- **Changes**: Fixed `UnboundLocalError` on `location_bin`; added required field validation on new parts; validated vehicle year (1900–2100) and non-negative mileage; validated mechanic status sets and non-negative hourly rates; checked mechanic existence on booking allocation.
- **Tests Added**: 4 route input validation tests.
- **Commit**: `e098d3a` — *fix: strengthen route validation, entity existence, and input security*

### Phase 8: Code Quality & Deprecation Cleanup
- **Files Modified**: `models.py`, `seed_data.py`, `routes/*.py`.
- **Changes**: Created `utc_now` helper returning `datetime.now(timezone.utc)`; replaced deprecated `datetime.utcnow()` across models, seed data, and routes; replaced legacy `Model.query.get_or_404()` with `db.get_or_404(Model, id)`.
- **Results**: Warnings dropped from 1,307 to 0.
- **Commit**: `e566649` — *refactor: eliminate deprecated datetime and legacy SQLAlchemy query APIs*

### Phase 9: Comprehensive Regression & Integration Testing
- **Files Modified**: `test_app.py`.
- **Changes**: Added tests for seeder idempotency, exact Decimal 2-decimal-place quantization, and restock input boundary validation.
- **Commit**: `d7f7148` — *test: add comprehensive regression coverage for integrity, idempotency, and decimal accounting*

### Phase 10: Final Code Review & Documentation
- **Files Modified**: `README.md`, `docs/BUGFIX_REPORT.md`.
- **Changes**: Updated setup instructions to reflect hardened database configuration; created comprehensive bugfix report.

---

## 4. Traceable Git Commit History

```text
d7f7148 test: add comprehensive regression coverage for integrity, idempotency, and decimal accounting
e566649 refactor: eliminate deprecated datetime and legacy SQLAlchemy query APIs
e098d3a fix: strengthen route validation, entity existence, and input security
26433d7 fix: harden application configuration, secrets, and startup
c26e018 fix: align ORM validation with database schema and isolate seeding
f8c630c fix: preserve historical service and financial records against cascade deletions
430943b fix: enforce authoritative billing calculations and decimal precision for payments
be107ab fix: make inventory deductions transaction-safe and enforce stock constraints
725dec4 fix: validate booking ownership and enforce service part usage authorization
d65c692 test: establish isolated test environment and developer dependencies
```

---

## 5. Verification Commands and Results

All tests were executed using the project-isolated virtual environment:

```bash
.\.venv\Scripts\python.exe -m pytest test_app.py -v
```

**Output**:
```text
============================= test session starts =============================
platform win32 -- Python 3.14.6, pytest-9.1.1, pluggy-1.7.0
rootdir: C:\Users\krris\OneDrive\Documents\Inventory Management System\Automitra
collected 32 items

test_app.py::test_database_tables_seeded PASSED                          [  3%]
test_app.py::test_duplicate_customer_detection PASSED                    [  6%]
test_app.py::test_missed_bookings_logic PASSED                           [  9%]
test_app.py::test_spare_parts_inventory_deduction PASSED                 [ 12%]
test_app.py::test_low_stock_detection PASSED                             [ 15%]
test_app.py::test_billing_and_payments PASSED                            [ 18%]
test_app.py::test_all_web_routes PASSED                                  [ 21%]
test_app.py::test_cross_job_part_deletion_rejected PASSED                [ 25%]
test_app.py::test_booking_rejects_vehicle_customer_mismatch PASSED       [ 28%]
test_app.py::test_booking_rejects_nonexistent_customer_or_vehicle PASSED [ 31%]
test_app.py::test_invalid_service_and_inventory_inputs PASSED            [ 34%]
test_app.py::test_insufficient_stock_and_negative_stock_prevention PASSED [ 37%]
test_app.py::test_part_usage_restoration_once PASSED                     [ 40%]
test_app.py::test_authoritative_billing_rejects_client_tampering PASSED  [ 43%]
test_app.py::test_billing_rejects_negative_tax_discount_and_excessive_discount PASSED [ 46%]
test_app.py::test_payments_validation_and_lock_on_billed_invoices PASSED [ 50%]
test_app.py::test_cannot_delete_customer_with_historical_bills_or_history PASSED [ 53%]
test_app.py::test_cannot_delete_vehicle_with_service_history PASSED      [ 56%]
test_app.py::test_valid_deletion_of_disposable_unreferenced_records PASSED [ 59%]
test_app.py::test_orm_metadata_and_updated_at PASSED                     [ 62%]
test_app.py::test_status_and_method_check_constraints PASSED             [ 65%]
test_app.py::test_service_detail_unique_booking_constraint PASSED        [ 68%]
test_app.py::test_production_config_rejects_missing_secret_key PASSED    [ 71%]
test_app.py::test_mysql_failure_prohibits_silent_sqlite_fallback PASSED  [ 75%]
test_app.py::test_explicit_sqlite_mode_allowed PASSED                    [ 78%]
test_app.py::test_inventory_new_part_validation_and_location_bin PASSED  [ 81%]
test_app.py::test_vehicle_creation_and_edit_validation PASSED            [ 84%]
test_app.py::test_mechanic_status_and_rate_validation PASSED             [ 87%]
test_app.py::test_booking_rejects_nonexistent_mechanic PASSED            [ 90%]
test_app.py::test_init_db_and_seeder_idempotency PASSED                  [ 93%]
test_app.py::test_exact_decimal_accounting_and_quantization PASSED       [ 96%]
test_app.py::test_restock_rejects_negative_or_zero_quantity PASSED       [100%]

============================= 32 passed in 7.62s ==============================
```

---

## 6. MySQL Integration Status & Migration Guidelines

### MySQL Verification Status
- **Status**: **Unverified in live MySQL** (No active or isolated MySQL test database was provided in the local execution environment).
- SQLite-based test passing is **not** claimed as proof of MySQL live correctness.
- Code compatibility was verified for SQLAlchemy dialects, MySQL ENUM definitions, and PyMySQL connection handling.

### Required Database Migration Steps (When Applying to Existing MySQL Databases)
1. **Safety Backup**: Create a full dump before applying changes:
   ```bash
   mysqldump -u <user> -p automitra > automitra_backup_$(date +%Y%m%d_%H%M%S).sql
   ```
2. **Do Not Run `schema.sql` Directly**: The existing `schema.sql` contains `DROP TABLE IF EXISTS` statements that will erase populated data.
3. **Non-Destructive Alterations**:
   ```sql
   -- 1. Add updated_at column to Customers if missing
   ALTER TABLE Customers ADD COLUMN IF NOT EXISTS updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;

   -- 2. Add Unique constraint on ServiceDetails.booking_id if not present
   -- (Verify no existing duplicate records exist before applying):
   ALTER TABLE ServiceDetails ADD CONSTRAINT uq_service_details_booking UNIQUE (booking_id);
   ```
4. **Verification**: Confirm indexes and constraints:
   ```sql
   SHOW INDEX FROM ServiceDetails;
   DESCRIBE Customers;
   ```

---

## 7. Remaining Risks and Recommendations

1. **CSRF Protection**: State-changing POST endpoints currently rely on form actions without Flask-WTF CSRF tokens. It is recommended to introduce `Flask-WTF` / `CSRFProtect` in a future feature sprint.
2. **User Authentication & Role-Based Access**: All routes are currently open to anyone with network access to the port. If multi-user access (Mechanic vs Manager vs Billing Cashier) is required, an explicit authentication model should be scoped and approved.
3. **Automated Live MySQL CI**: Add a GitHub Actions CI workflow provisioning a transient MySQL 8.0 service container to run `pytest` against live MySQL.
