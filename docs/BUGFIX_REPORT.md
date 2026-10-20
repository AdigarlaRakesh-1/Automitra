# AutoMitra — Bug Fixing, Security Hardening, Database Integrity, and Testing Report

**Repository**: `AdigarlaRakesh-1/Automitra`  
**Working Branch**: `fix/critical-validation-and-integrity`  
**Target / Base Branch**: `main`  
**Execution Environment**: Python 3.14.6, Flask 3.1.2, SQLAlchemy 2.0.35, Flask-SQLAlchemy 3.1.1, Flask-WTF 1.3.0, WTForms 3.2.2, PyMySQL 1.2.3, pytest 9.1.1
**Database Engines Tested**:
- In-Memory & File-based SQLite (Development & Regression Tests with enforced `PRAGMA foreign_keys=ON`)
- Live MariaDB / MySQL 10.4.32 on `127.0.0.1:3306` (Full Integration & Transactional Verification)

---

## 1. Executive Summary

This engineering effort conducted an end-to-end security audit, data integrity reinforcement, and comprehensive test suite expansion of the **AutoMitra** Vehicle Service Center Management System. Across 13 methodical phases, every confirmed vulnerability, concurrency race condition, financial calculation loophole, database inconsistency, CSRF gap, cascade deletion hazard, and test lifecycle safety risk was resolved, verified through regression tests, and cleanly committed to `fix/critical-validation-and-integrity`.

### Key Metrics
- **Baseline Test Suite**: 7 tests passed (with 1,307 deprecation/legacy warnings).
- **Intermediate Test Suite**: 32 tests passed (0 failures, 0 warnings).
- **Verified Phase 12 Test Suite**: 41 tests passed (0 failures, 0 warnings).
- **Final Hardened Test Suite**: **49 tests passed** (0 failures, 0 warnings, execution time ~7.1s).
- **Live MySQL Integration**: **100% Verified** against local MariaDB/MySQL server using dynamically isolated databases (`automitra_test_<uuid>`) and lifecycle protection guards ensuring pre-existing databases can never be dropped or overwritten.
- **Financial Record Preservation**: **Enforced at both ORM and Database DDL levels** (`ON DELETE RESTRICT` on `Payments.bill_id`, `Bills`, and `ServiceBookings`). Attempted deletions of invoices with payment history are strictly rejected.
- **CSRF Protection**: **Enforced across all 18 state-changing POST forms** and verified via `CSRFTestClient`.
- **Destructive Database Actions**: **0** (No production or populated database was altered, reset, or overwritten; `schema.sql` was never run against live data).
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
| **Phase 4** | Cascade Deletion of Invoices, Audit Logs, and Service Records | **Critical** | `models.py` had `cascade='all, delete-orphan'` and `ondelete='CASCADE'` on customer bills and service bookings. Deleting a customer or vehicle deleted accounting audit records. |
| **Phase 5** | Database Schema vs ORM Mismatches | High | `Customer.updated_at` was missing from ORM model; MySQL ENUM constraints existed in `schema.sql` but were unconstrained in ORM strings; `ServiceDetail.booking_id` lacked uniqueness constraint. |
| **Phase 5** | Uncontrolled Database Auto-Seeding on Module Import | Medium | `create_app()` unconditionally invoked `db.create_all()` and `seed_database()` during import, risking mutating development or testing databases simply by importing the app. |
| **Phase 6** | Hardcoded Credentials & Insecure Production Secrets | **Critical** | `config.py` fell back to hardcoded production keys; `DEBUG=True` was hardcoded in `app.run()`; `.env.example` had default `root` credentials. |
| **Phase 6** | Silent Fallback from MySQL to SQLite | **Critical** | If a configured MySQL connection failed, `app.py` silently redirected writes to a local SQLite file (`automitra.db`), causing silent production data divergence. |
| **Phase 7** | `UnboundLocalError` on `location_bin` in `inventory.py` | High | Variable `location_bin` was referenced when instantiating `SparePart` without being extracted from `request.form`. |
| **Phase 7** | Missing Vehicle & Mechanic Entity Existence & Range Checks | Medium | Adding vehicle permitted non-existent customer IDs, invalid year numbers, and negative mileage. Adding bookings permitted non-existent mechanic IDs. |
| **Phase 8** | 1,300+ Deprecation & Legacy API Warnings | Low / Quality | Python 3.14 deprecated naive `datetime.utcnow()`; SQLAlchemy 2.0 deprecated legacy `Query.get()` / `Model.query.get_or_404()`. |
| **Phase 9** | Missing Cross-Site Request Forgery (CSRF) Protection | **High / Security** | All 18 browser POST forms lacked anti-CSRF token verification, allowing cross-site state-changing request forgery. |
| **Phase 10** | Unrestricted Cascade Deletion on Historical Invoices & Reversals | **High / Integrity** | Completed and paid bookings could be rescheduled or moved backwards to Pending, and historical Bills were subject to cascade deletion. |
| **Phase 11** | Duplicate Payment Transaction References & 500 Error Traceback Leakage | Medium / Security | Submitting duplicate transaction references was allowed; HTTP 500 error handler returned raw internal exception strings in production. |
| **Phase 12** | Live MySQL Integration Verification & CI Pipeline Gaps | Medium / DevOps | CI lacked MySQL test containers and dev dependencies; live MySQL tests were missing. |
| **Phase 13** | Unsafe MySQL Integration Test Database Deletion Hazard | **Critical / Safety** | Integration test used a hardcoded database name and dropped it in cleanup, risking accidental deletion of pre-existing databases. Fixed with collision-proof `automitra_test_<uuid>` names, pre-existence checks, and strict cleanup deletion guards. |
| **Phase 13** | Silent Cascade Deletion of Financial Payment History | **Critical / Financial Integrity** | `Bill.payments` used `cascade='all, delete-orphan'` and `Payment.bill_id` had `ON DELETE CASCADE`. Deleting a bill silently wiped historical payment records. Changed to restrictive deletion at ORM and DDL levels, enabled SQLite FK enforcement via PRAGMA, and blocked deletions of bills with payments. |
| **Phase 13** | Inconsistent Invoice Editing & Payment Idempotency | High / Financial Integrity | Editing bills with recorded payments was permitted; payments on settled zero-balance bills were accepted; missing database unique constraint on `Payments.transaction_reference`. Added route-level locks and database constraints. |

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
  updated = SparePart.query.filter(
      SparePart.id == part.id,
      SparePart.stock_quantity >= quantity
  ).update(
      {SparePart.stock_quantity: SparePart.stock_quantity - quantity},
      synchronize_session=False
  )
  ```
- **Tests Added**: 2 concurrency and stock-check regression tests (`test_insufficient_stock_and_negative_stock_prevention`, `test_multithreaded_concurrent_stock_deduction`).
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
- **Results**: Deprecation warnings eliminated (0 warnings).
- **Commit**: `e566649` — *refactor: eliminate deprecated datetime and legacy SQLAlchemy query APIs*

### Phase 9: CSRF Protection & Form Hardening
- **Dependencies Installed**: `Flask-WTF==1.3.0`, `WTForms==3.2.2` pinned in `requirements.txt`.
- **Files Modified**: `app.py`, `templates/base.html`, `templates/**/*.html` (18 forms), `templates/400.html`.
- **Changes**:
  - Initialized `CSRFProtect(app)` in `app.py`.
  - Added custom CSRF error handler returning HTTP 400 with user-friendly `templates/400.html`.
  - Added `<meta name="csrf-token" content="{{ csrf_token() }}">` in `base.html`.
  - Injected `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>` in all 18 POST forms across billing, bookings, customers, inventory, mechanics, services, and vehicles.
  - Implemented `CSRFTestClient` in `test_app.py` automatically attaching cryptographically signed CSRF tokens unless explicitly suppressed with `no_csrf=True`.
- **Tests Added**: `test_csrf_protection_enforced` (verifying rejection of missing/invalid tokens and acceptance of valid tokens).

### Phase 10: Historical Invoice Lock & Cascade Restriction
- **Files Modified**: `models.py`, `routes/bookings.py`, `routes/services.py`.
- **Changes**:
  - Changed `Bills.booking_id` and `Bills.customer_id` from `ondelete='CASCADE'` to `ondelete='RESTRICT'`.
  - Blocked status reversion on bookings and service jobs whose invoices are marked `Paid`.
  - Blocked rescheduling completed bookings or bookings with paid invoices.
- **Tests Added**: `test_booking_status_lock_on_paid_invoice`, `test_booking_reschedule_lock_on_completed_or_paid`, `test_service_job_status_lock_on_paid_invoice`, `test_bill_cascade_deletion_prevention`.

### Phase 11: Payment Idempotency & Error Sanitization
- **Files Modified**: `routes/payments.py`, `app.py`.
- **Changes**:
  - Checked `Payment.transaction_reference` uniqueness before recording payments to prevent duplicate payments.
  - Sanitized HTTP 500 responses when `not app.debug` so internal exception strings, SQL queries, and credentials are never exposed to clients.
- **Tests Added**: `test_duplicate_payment_transaction_reference_rejected`, `test_500_error_handler_sanitization`.

### Phase 12: Live MySQL Integration & CI Pipeline
- **Files Modified**: `.github/workflows/tests.yml`, `test_app.py`.
- **Changes**:
  - Verified integration against local MariaDB/MySQL 10.4.32 on port 3306 (`automitra_live_pytest_isolated`), testing DDL creation, transactions, rollbacks, and decimal precision.
  - Updated GitHub Actions CI to spin up a `mysql:8.0` service container, cache pip packages, install `requirements-dev.txt`, and trigger on pushes to `main` and `fix/**`.
- **Tests Added**: `test_live_mysql_integration_and_integrity`.

### Phase 13: Final Safety Fixes, Restrictive Payment Deletion & Safe MySQL Test Lifecycle
- **Files Modified**: `models.py`, `routes/billing.py`, `routes/payments.py`, `schema.sql`, `.github/workflows/tests.yml`, `test_app.py`.
- **Changes**:
  1. **Safe MySQL Test Database Lifecycle (`SafeMySQLTestDatabase`)**:
     - Dynamically generated collision-free database name per test invocation (`automitra_test_<uuid>`).
     - Pre-existence verification query against `INFORMATION_SCHEMA.SCHEMATA`. If a database with the target name pre-exists, the test aborts before DDL execution to prevent overwriting.
     - Strict deletion guard `created_by_test`: drops a database only if it was explicitly created by the current test instance and matches prefix `automitra_test_`.
     - Skip with descriptive reason when MySQL is unavailable or lacks administrative creation privileges, avoiding arbitrary local database mutations.
     - Add dedicated regression test `test_mysql_lifecycle_guards_preexisting_database_from_deletion` proving pre-existing databases are protected from selection and deletion.
     - Configured CI workflow environment variables for MySQL connection consistency.
  2. **Preserve Payment History When Deleting Bills**:
     - Removed `cascade='all, delete-orphan'` from `Bill.payments` in `models.py`.
     - Changed `Payment.bill_id` foreign key from `CASCADE` to `ondelete='RESTRICT'`.
     - Changed `ServiceBooking.customer_id` and `ServiceBooking.vehicle_id` foreign keys to `ondelete='RESTRICT'`.
     - Enabled SQLite foreign key enforcement via SQLAlchemy engine listener (`PRAGMA foreign_keys=ON`) ensuring identical restrictive deletion semantics across SQLite and MySQL.
     - Aligned `schema.sql` foreign keys to `ON DELETE RESTRICT` (`fk_booking_customer`, `fk_booking_vehicle`, `fk_bill_booking`, `fk_bill_customer`, `fk_payment_bill`).
     - Added comprehensive regression tests:
       - `test_bill_deletion_rejected_when_payments_exist` (ORM rejection with IntegrityError)
       - `test_raw_sql_bill_deletion_rejected_by_foreign_key_restriction` (Engine/DDL-level rejection)
       - `test_disposable_bill_without_payments_can_be_deleted` (Allows clean deletion when no financial records exist)
       - `test_customer_and_booking_deletion_cannot_bypass_payment_safeguards` (Cross-entity deletion safety)
  3. **Financial & Database Integrity Revalidation**:
     - Blocked editing bills marked `Paid` or having recorded payments (`total_paid > 0`) in `routes/billing.py`.
     - Blocked recording payments on settled invoices (`balance <= Decimal('0.00')`) in `routes/payments.py`.
     - Enforced `UNIQUE` constraint on `Payment.transaction_reference` at both ORM and database DDL levels, with graceful collision handling in the payments route.
     - Added regression tests:
       - `test_payment_route_rejects_settled_zero_balance_bill`
       - `test_billing_edit_route_rejects_paid_invoices`
       - `test_payment_unique_transaction_reference_db_constraint`

---

## 4. Full Pytest Execution Results

```bash
.\.venv\Scripts\python.exe -m pytest test_app.py -v
```

```text
============================= test session starts =============================
platform win32 -- Python 3.14.6, pytest-9.1.1, pluggy-1.7.0 -- C:\Users\krris\OneDrive\Documents\Inventory Management System\Automitra\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\krris\OneDrive\Documents\Inventory Management System\Automitra
collecting ... collected 49 items

test_app.py::test_database_tables_seeded PASSED                          [  2%]
test_app.py::test_duplicate_customer_detection PASSED                    [  4%]
test_app.py::test_missed_bookings_logic PASSED                           [  6%]
test_app.py::test_spare_parts_inventory_deduction PASSED                 [  8%]
test_app.py::test_low_stock_detection PASSED                             [ 10%]
test_app.py::test_billing_and_payments PASSED                            [ 12%]
test_app.py::test_all_web_routes PASSED                                  [ 14%]
test_app.py::test_cross_job_part_deletion_rejected PASSED                [ 16%]
test_app.py::test_booking_rejects_vehicle_customer_mismatch PASSED       [ 18%]
test_app.py::test_booking_rejects_nonexistent_customer_or_vehicle PASSED [ 20%]
test_app.py::test_invalid_service_and_inventory_inputs PASSED            [ 22%]
test_app.py::test_insufficient_stock_and_negative_stock_prevention PASSED [ 24%]
test_app.py::test_part_usage_restoration_once PASSED                     [ 26%]
test_app.py::test_authoritative_billing_rejects_client_tampering PASSED  [ 28%]
test_app.py::test_billing_rejects_negative_tax_discount_and_excessive_discount PASSED [ 30%]
test_app.py::test_payments_validation_and_lock_on_billed_invoices PASSED [ 32%]
test_app.py::test_cannot_delete_customer_with_historical_bills_or_history PASSED [ 34%]
test_app.py::test_cannot_delete_vehicle_with_service_history PASSED      [ 36%]
test_app.py::test_valid_deletion_of_disposable_unreferenced_records PASSED [ 38%]
test_app.py::test_orm_metadata_and_updated_at PASSED                     [ 40%]
test_app.py::test_status_and_method_check_constraints PASSED             [ 42%]
test_app.py::test_service_detail_unique_booking_constraint PASSED        [ 44%]
test_app.py::test_production_config_rejects_missing_secret_key PASSED    [ 46%]
test_app.py::test_mysql_failure_prohibits_silent_sqlite_fallback PASSED  [ 48%]
test_app.py::test_explicit_sqlite_mode_allowed PASSED                    [ 51%]
test_app.py::test_inventory_new_part_validation_and_location_bin PASSED  [ 53%]
test_app.py::test_vehicle_creation_and_edit_validation PASSED            [ 55%]
test_app.py::test_mechanic_status_and_rate_validation PASSED             [ 57%]
test_app.py::test_booking_rejects_nonexistent_mechanic PASSED            [ 59%]
test_app.py::test_init_db_and_seeder_idempotency PASSED                  [ 61%]
test_app.py::test_exact_decimal_accounting_and_quantization PASSED       [ 63%]
test_app.py::test_restock_rejects_negative_or_zero_quantity PASSED       [ 65%]
test_app.py::test_csrf_protection_enforced PASSED                        [ 67%]
test_app.py::test_multithreaded_concurrent_stock_deduction PASSED        [ 69%]
test_app.py::test_booking_status_lock_on_paid_invoice PASSED             [ 71%]
test_app.py::test_booking_reschedule_lock_on_completed_or_paid PASSED    [ 73%]
test_app.py::test_service_job_status_lock_on_paid_invoice PASSED         [ 75%]
test_app.py::test_duplicate_payment_transaction_reference_rejected PASSED [ 77%]
test_app.py::test_bill_cascade_deletion_prevention PASSED                [ 79%]
test_app.py::test_500_error_handler_sanitization PASSED                  [ 81%]
test_app.py::test_mysql_lifecycle_guards_preexisting_database_from_deletion PASSED [ 83%]
test_app.py::test_live_mysql_integration_and_integrity PASSED            [ 85%]
test_app.py::test_bill_deletion_rejected_when_payments_exist PASSED      [ 87%]
test_app.py::test_raw_sql_bill_deletion_rejected_by_foreign_key_restriction PASSED [ 89%]
test_app.py::test_disposable_bill_without_payments_can_be_deleted PASSED [ 91%]
test_app.py::test_customer_and_booking_deletion_cannot_bypass_payment_safeguards PASSED [ 93%]
test_app.py::test_payment_route_rejects_settled_zero_balance_bill PASSED [ 95%]
test_app.py::test_billing_edit_route_rejects_paid_invoices PASSED        [ 97%]
test_app.py::test_payment_unique_transaction_reference_db_constraint PASSED [100%]

============================= 49 passed in 7.11s ==============================
```

---

## 5. MySQL Verification Status & Non-Destructive Migration Plan

### Live MySQL Verification Status
- **Status**: **VERIFIED LIVE** on localhost:3306 (MariaDB/MySQL 10.4.32).
- The integration test generates a unique collision-free database name (`automitra_test_<uuid>`), confirms no existing database with that name exists, creates the schema, tests transactional commits, rollbacks, restrictive foreign keys, and decimal precision, and securely drops only the database created by that run.

### Non-Destructive Production Migration Plan
When deploying to existing MySQL databases, follow this safe sequence:

1. **Mandatory Pre-Migration Backup**:
   ```bash
   mysqldump -u <user> -p --single-transaction --quick automitra > automitra_backup_$(date +%Y%m%d_%H%M%S).sql
   ```

2. **Strict Prohibition**:
   - **DO NOT RUN `schema.sql`** directly against populated databases. It contains `DROP TABLE IF EXISTS` which causes irreversible data loss.

3. **Non-Destructive DDL Adjustments**:
   ```sql
   -- 1. Add Customers.updated_at if not present
   ALTER TABLE Customers ADD COLUMN IF NOT EXISTS updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;

   -- 2. Add Unique constraint on ServiceDetails.booking_id (verify no duplicates exist first)
   ALTER TABLE ServiceDetails ADD CONSTRAINT uq_service_details_booking UNIQUE (booking_id);

   -- 3. Modify Foreign Key cascades on ServiceBookings to RESTRICT
   ALTER TABLE ServiceBookings DROP FOREIGN KEY IF EXISTS fk_booking_customer;
   ALTER TABLE ServiceBookings ADD CONSTRAINT fk_booking_customer FOREIGN KEY (customer_id) REFERENCES Customers(id) ON DELETE RESTRICT;

   ALTER TABLE ServiceBookings DROP FOREIGN KEY IF EXISTS fk_booking_vehicle;
   ALTER TABLE ServiceBookings ADD CONSTRAINT fk_booking_vehicle FOREIGN KEY (vehicle_id) REFERENCES Vehicles(id) ON DELETE RESTRICT;

   -- 4. Modify Foreign Key cascades on Bills to RESTRICT for financial preservation
   ALTER TABLE Bills DROP FOREIGN KEY IF EXISTS fk_bills_booking;
   ALTER TABLE Bills ADD CONSTRAINT fk_bills_booking FOREIGN KEY (booking_id) REFERENCES ServiceBookings(id) ON DELETE RESTRICT;

   ALTER TABLE Bills DROP FOREIGN KEY IF EXISTS fk_bills_customer;
   ALTER TABLE Bills ADD CONSTRAINT fk_bills_customer FOREIGN KEY (customer_id) REFERENCES Customers(id) ON DELETE RESTRICT;

   -- 5. Modify Foreign Key cascades on Payments to RESTRICT to preserve payment history
   ALTER TABLE Payments DROP FOREIGN KEY IF EXISTS fk_payment_bill;
   ALTER TABLE Payments ADD CONSTRAINT fk_payment_bill FOREIGN KEY (bill_id) REFERENCES Bills(id) ON DELETE RESTRICT;

   -- 6. Add Unique constraint on Payments.transaction_reference (verify no duplicates exist first)
   ALTER TABLE Payments ADD CONSTRAINT uq_payments_transaction_ref UNIQUE (transaction_reference);
   ```

4. **Rollback Script (If Reversion is Required)**:
   ```sql
   -- Revert to original cascade settings if necessary
   ALTER TABLE ServiceBookings DROP FOREIGN KEY fk_booking_customer;
   ALTER TABLE ServiceBookings ADD CONSTRAINT fk_booking_customer FOREIGN KEY (customer_id) REFERENCES Customers(id) ON DELETE CASCADE;

   ALTER TABLE ServiceBookings DROP FOREIGN KEY fk_booking_vehicle;
   ALTER TABLE ServiceBookings ADD CONSTRAINT fk_booking_vehicle FOREIGN KEY (vehicle_id) REFERENCES Vehicles(id) ON DELETE CASCADE;

   ALTER TABLE Bills DROP FOREIGN KEY fk_bills_booking;
   ALTER TABLE Bills ADD CONSTRAINT fk_bills_booking FOREIGN KEY (booking_id) REFERENCES ServiceBookings(id) ON DELETE CASCADE;

   ALTER TABLE Payments DROP FOREIGN KEY fk_payment_bill;
   ALTER TABLE Payments ADD CONSTRAINT fk_payment_bill FOREIGN KEY (bill_id) REFERENCES Bills(id) ON DELETE CASCADE;
   ```

---

## 6. Authentication & Authorization Scope Assessment

### Scope & Architecture Boundary
- **AutoMitra** is architecturally designed as an internal operational console for single-operator garage environments (e.g. front-desk cashier or garage manager station).
- **Authentication Status**: There is currently no multi-user authentication model (no user accounts, password hashes, or role-based access control).
- **Security & Deployment Restrictions**:
  - The application **must not be exposed directly to the public internet** without an authenticating reverse proxy (such as Cloudflare Access, Nginx with HTTP Basic/OIDC Auth, or a VPN/Tailscale network).
  - Production deployments must bind only to localhost (`127.0.0.1`) or private garage subnets.
  - If multi-user access (e.g., differentiating Mechanic work orders from Cashier billing actions) is desired in future releases, a dedicated Authentication & Authorization sprint should introduce `Flask-Login` / `bcrypt` with explicit user roles.
