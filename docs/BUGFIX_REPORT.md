# AutoMitra — Bug Fixing, Security Hardening, Database Integrity, and Testing Report

**Repository**: `AdigarlaRakesh-1/Automitra`  
**Working Branch**: `fix/critical-validation-and-integrity`  
**Target / Base Branch**: `main`  
**Execution Environment**: Python 3.14.6, Flask 3.1.2, SQLAlchemy 2.0.35, Flask-SQLAlchemy 3.1.1, Flask-WTF 1.3.0, WTForms 3.2.2, PyMySQL 1.2.3, pytest 9.1.1
**Database Engines Tested**:
- In-Memory & File-based SQLite (Development & Regression Tests with enforced `PRAGMA foreign_keys=ON`)
- Live MariaDB / MySQL 10.4.32 on `127.0.0.1:3306` (Full Integration, Safety Guards & Migration Verification)
- MySQL 8.0 CI Service Container on GitHub Actions

---

## 1. Executive Summary

This engineering effort conducted an end-to-end security audit, data integrity reinforcement, and comprehensive test suite expansion of the **AutoMitra** Vehicle Service Center Management System. Across 13 methodical phases, every confirmed vulnerability, concurrency race condition, financial calculation loophole, database inconsistency, CSRF gap, cascade deletion hazard, and test lifecycle safety risk was resolved, verified through regression tests, and cleanly committed to `fix/critical-validation-and-integrity`.

### Key Metrics
- **Baseline Test Suite**: 7 tests passed (with 1,307 deprecation/legacy warnings).
- **Intermediate Test Suite**: 32 tests passed (0 failures, 0 warnings).
- **Verified Phase 12 Test Suite**: 41 tests passed (0 failures, 0 warnings).
- **Verified Phase 13 Test Suite**: 49 tests passed (0 failures, 0 warnings).
- **Final Hardened Test Suite**: **53 tests passed** (0 failures, 0 warnings, execution time ~8.0s).
- **Live MySQL Integration**: **100% Verified** against local MariaDB/MySQL server and CI MySQL 8.0 using dynamically isolated databases (`automitra_test_<uuid>`) and lifecycle protection guards ensuring pre-existing databases can never be dropped or overwritten.
- **Migration Safety Verified**: The non-destructive production migration procedure is automated and regression-tested against a disposable database (`test_live_mysql_non_destructive_migration_procedure`).
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
| **Phase 13** | Unsafe MySQL Integration Test Database Deletion Hazard | **Critical / Safety** | Integration test used a hardcoded database name and dropped it in cleanup, risking accidental deletion of pre-existing databases. Fixed with collision-proof `automitra_test_<uuid>` names, pre-existence checks, explicit test ownership tracking, and strict cleanup deletion guards. |
| **Phase 13** | Silent Cascade Deletion of Financial Payment History | **Critical / Financial Integrity** | `Bill.payments` used `cascade='all, delete-orphan'` and `Payment.bill_id` had `ON DELETE CASCADE`. Deleting a bill silently wiped historical payment records. Changed to restrictive deletion at ORM and DDL levels, enabled SQLite FK enforcement via PRAGMA, and blocked deletions of bills with payments. |
| **Phase 13** | Inconsistent Invoice Editing & Payment Idempotency | High / Financial Integrity | Editing bills with recorded payments was permitted; payments on settled zero-balance bills were accepted; missing database unique constraint on `Payments.transaction_reference`. Added route-level locks and database constraints. |
| **Phase 14** | Test Database Connection Leaks on Setup Failures & Incomplete Duplicate Pre-Check | **Critical / Reliability & Migration Integrity** | Admin connection `_admin_conn` in `SafeMySQLTestDatabase` leaked on candidate name collision or creation failure; payments migration pre-check excluded empty strings `''`, which violate unique indexes in MySQL with error 1062. Implemented structured connection cleanup, complete non-NULL duplicate pre-flight detection, and regression tests. |

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
  - Verified integration against local MariaDB/MySQL 10.4.32 on port 3306, testing DDL creation, transactions, rollbacks, and decimal precision.
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
     - Explicit ownership tracking in `test_mysql_lifecycle_guards_preexisting_database_from_deletion`, generating collision-resistant fixture databases (`automitra_fixture_<uuid>`), confirming pre-existing databases and system databases (`mysql`) can never be dropped.
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
       - `test_billing_edit_rou        - `test_payment_unique_transaction_reference_db_constraint`
  4. **Automated Non-Destructive Migration Testing**:
     - Added `test_live_mysql_non_destructive_migration_procedure` in `test_app.py` verifying the complete backup-first, portable migration procedure on a disposable MySQL database.

### Phase 14: Test Database Connection Lifecycle Hardening & Complete Non-NULL Migration Pre-Check
- **Files Modified**: `test_app.py`, `docs/BUGFIX_REPORT.md`, `README.md`.
- **Changes**:
  1. **Administrative Connection Lifecycle Protection (`SafeMySQLTestDatabase`)**:
     - Ensured `_admin_conn` is closed whenever setup encounters an error or candidate name collision in `SafeMySQLTestDatabase.__enter__`.
     - Wrapped pre-existence collision check and creation in `try...except Exception: self.close_admin(); raise`.
     - Added idempotent `close_admin()` method that safely closes and resets `self._admin_conn = None`.
     - Added unit test with mocks (`test_safe_mysql_admin_connection_cleanup_on_collision_and_error`) verifying cleanup occurs on candidate collision or creation failure without masking original exceptions.
  2. **Comprehensive Payments Migration Pre-Check (Detecting Empty Strings & Non-NULL Duplicates)**:
     - Updated Check 1 migration query to inspect all non-NULL references (`WHERE transaction_reference IS NOT NULL GROUP BY transaction_reference HAVING COUNT(*) > 1`), catching duplicate empty strings `''`.
     - Added live MySQL integration test `test_live_mysql_payments_unique_reference_and_empty_string_behavior` proving:
       - Duplicate `''` strings are flagged by pre-check and cause MySQL error 1062 upon `ADD CONSTRAINT ... UNIQUE`.
       - Converting unprovided empty references to `NULL` succeeds.
       - Multiple `NULL` references are accepted by MySQL's unique index.
       - Non-empty duplicate references are strictly rejected.
     - Added `test_sqlite_payments_unique_reference_empty_string_parity` ensuring SQLite behaves consistently.
  3. **Documentation & README Alignment**:
     - Updated `README.md` to clarify restrictive deletion rules for historical and financial records.
     - Aligned Python version requirement to Python 3.11+ across quickstart, tech stack, and CI.

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
collecting ... collected 53 items

test_app.py::test_database_tables_seeded PASSED                          [  1%]
test_app.py::test_duplicate_customer_detection PASSED                    [  3%]
test_app.py::test_missed_bookings_logic PASSED                           [  5%]
test_app.py::test_spare_parts_inventory_deduction PASSED                 [  7%]
test_app.py::test_low_stock_detection PASSED                             [  9%]
test_app.py::test_billing_and_payments PASSED                            [ 11%]
test_app.py::test_all_web_routes PASSED                                  [ 13%]
test_app.py::test_cross_job_part_deletion_rejected PASSED                [ 15%]
test_app.py::test_booking_rejects_vehicle_customer_mismatch PASSED       [ 16%]
test_app.py::test_booking_rejects_nonexistent_customer_or_vehicle PASSED [ 18%]
test_app.py::test_invalid_service_and_inventory_inputs PASSED            [ 20%]
test_app.py::test_insufficient_stock_and_negative_stock_prevention PASSED [ 22%]
test_app.py::test_part_usage_restoration_once PASSED                     [ 24%]
test_app.py::test_authoritative_billing_rejects_client_tampering PASSED  [ 26%]
test_app.py::test_billing_rejects_negative_tax_discount_and_excessive_discount PASSED [ 28%]
test_app.py::test_payments_validation_and_lock_on_billed_invoices PASSED [ 30%]
test_app.py::test_cannot_delete_customer_with_historical_bills_or_history PASSED [ 32%]
test_app.py::test_cannot_delete_vehicle_with_service_history PASSED      [ 33%]
test_app.py::test_valid_deletion_of_disposable_unreferenced_records PASSED [ 35%]
test_app.py::test_orm_metadata_and_updated_at PASSED                     [ 37%]
test_app.py::test_status_and_method_check_constraints PASSED             [ 39%]
test_app.py::test_service_detail_unique_booking_constraint PASSED        [ 41%]
test_app.py::test_production_config_rejects_missing_secret_key PASSED    [ 43%]
test_app.py::test_mysql_failure_prohibits_silent_sqlite_fallback PASSED  [ 45%]
test_app.py::test_explicit_sqlite_mode_allowed PASSED                    [ 47%]
test_app.py::test_inventory_new_part_validation_and_location_bin PASSED  [ 49%]
test_app.py::test_vehicle_creation_and_edit_validation PASSED            [ 50%]
test_app.py::test_mechanic_status_and_rate_validation PASSED             [ 52%]
test_app.py::test_booking_rejects_nonexistent_mechanic PASSED            [ 54%]
test_app.py::test_init_db_and_seeder_idempotency PASSED                  [ 56%]
test_app.py::test_exact_decimal_accounting_and_quantization PASSED       [ 58%]
test_app.py::test_restock_rejects_negative_or_zero_quantity PASSED       [ 60%]
test_app.py::test_csrf_protection_enforced PASSED                        [ 62%]
test_app.py::test_multithreaded_concurrent_stock_deduction PASSED        [ 64%]
test_app.py::test_booking_status_lock_on_paid_invoice PASSED             [ 66%]
test_app.py::test_booking_reschedule_lock_on_completed_or_paid PASSED    [ 67%]
test_app.py::test_service_job_status_lock_on_paid_invoice PASSED         [ 69%]
test_app.py::test_duplicate_payment_transaction_reference_rejected PASSED [ 71%]
test_app.py::test_bill_cascade_deletion_prevention PASSED                [ 73%]
test_app.py::test_500_error_handler_sanitization PASSED                  [ 75%]
test_app.py::test_safe_mysql_admin_connection_cleanup_on_collision_and_error PASSED [ 77%]
test_app.py::test_mysql_lifecycle_guards_preexisting_database_from_deletion PASSED [ 79%]
test_app.py::test_live_mysql_integration_and_integrity PASSED            [ 81%]
test_app.py::test_live_mysql_non_destructive_migration_procedure PASSED  [ 83%]
test_app.py::test_live_mysql_payments_unique_reference_and_empty_string_behavior PASSED [ 84%]
test_app.py::test_sqlite_payments_unique_reference_empty_string_parity PASSED [ 86%]
test_app.py::test_bill_deletion_rejected_when_payments_exist PASSED      [ 88%]
test_app.py::test_raw_sql_bill_deletion_rejected_by_foreign_key_restriction PASSED [ 90%]
test_app.py::test_disposable_bill_without_payments_can_be_deleted PASSED [ 92%]
test_app.py::test_customer_and_booking_deletion_cannot_bypass_payment_safeguards PASSED [ 94%]
test_app.py::test_payment_route_rejects_settled_zero_balance_bill PASSED [ 96%]
test_app.py::test_billing_edit_route_rejects_paid_invoices PASSED        [ 98%]
test_app.py::test_payment_unique_transaction_reference_db_constraint PASSED [100%]

============================= 53 passed in 7.98s ==============================
```

---

## 5. MySQL Verification Status & Non-Destructive Migration PlanDestructive Migration Plan

### Live MySQL Verification Status
- **Status**: **VERIFIED LIVE** on localhost:3306 (MariaDB/MySQL 10.4.32) and CI (`mysql:8.0`).
- **Safety Test Suite**:
  - `test_mysql_lifecycle_guards_preexisting_database_from_deletion`: Rigorously verifies that collision-free candidate names are generated, pre-existing databases are detected via `INFORMATION_SCHEMA.SCHEMATA`, and unowned or pre-existing databases are strictly protected from deletion.
  - `test_live_mysql_integration_and_integrity`: Verifies live DDL creation, transactions, rollbacks, restrictive foreign keys, and decimal precision against an isolated, collision-free disposable database.
  - `test_live_mysql_non_destructive_migration_procedure`: Executes and verifies the exact non-destructive migration script against a disposable database populated with operational legacy data, confirming zero data loss and foreign key enforcement.

---

### Non-Destructive Production Migration Plan (MySQL 8.0 & MariaDB Compatible)

When upgrading existing MySQL 8.0 or MariaDB databases from legacy schemas to the hardened schema, follow this verified, backup-first procedure.

#### Phase 1: Mandatory Pre-Migration Backup
Before performing any schema alterations, take a complete logical backup with routines and triggers:
```bash
mysqldump -u <user> -p \
  --single-transaction \
  --quick \
  --routines \
  --triggers \
  --databases automitra > automitra_pre_migration_backup_$(date +%Y%m%d_%H%M%S).sql
```

> [!CAUTION]
> **STRICT PROHIBITION**: Never execute `schema.sql` directly against a populated production or development database. `schema.sql` contains `DROP TABLE IF EXISTS` which will permanently destroy existing records.

#### Phase 2: Pre-Flight Anomaly & Integrity Checks
Run these read-only diagnostic queries to verify that the existing database has no duplicate references, duplicate 1:1 records, or orphaned rows that would cause constraint creation to fail:

```sql
-- Check 1: Duplicate transaction references in Payments (must return 0 rows)
-- NOTE: Checks ALL non-NULL values, including empty strings ('') which are non-NULL duplicates in unique indexes
SELECT transaction_reference, COUNT(*) AS duplicate_count
FROM Payments
WHERE transaction_reference IS NOT NULL
GROUP BY transaction_reference
HAVING COUNT(*) > 1;

-- Check 2: Duplicate booking assignments in ServiceDetails (must return 0 rows for 1:1 relationship)
SELECT booking_id, COUNT(*) AS duplicate_count
FROM ServiceDetails
WHERE booking_id IS NOT NULL
GROUP BY booking_id
HAVING COUNT(*) > 1;

-- Check 3: Orphaned Payments referencing non-existent Bills (must return 0 rows)
SELECT p.id AS payment_id, p.bill_id
FROM Payments p
LEFT JOIN Bills b ON p.bill_id = b.id
WHERE b.id IS NULL;

-- Check 4: Orphaned Bills referencing non-existent Bookings or Customers (must return 0 rows)
SELECT b.id AS bill_id, b.booking_id, b.customer_id
FROM Bills b
LEFT JOIN ServiceBookings sb ON b.booking_id = sb.id
LEFT JOIN Customers c ON b.customer_id = c.id
WHERE sb.id IS NULL OR c.id IS NULL;

-- Check 5: Orphaned ServiceBookings referencing non-existent Customers or Vehicles (must return 0 rows)
SELECT sb.id AS booking_id, sb.customer_id, sb.vehicle_id
FROM ServiceBookings sb
LEFT JOIN Customers c ON sb.customer_id = c.id
LEFT JOIN Vehicles v ON sb.vehicle_id = v.id
WHERE c.id IS NULL OR v.id IS NULL;
```

##### Resolving Pre-Flight Duplicate Reference Conflicts Safely
> [!IMPORTANT]
> **Understanding Non-NULL Values and Unique Constraints**:
> Under standard SQL and MySQL InnoDB semantics, `NULL` indicates the absence of a value; because `NULL != NULL`, multiple rows may contain `NULL` without violating a unique index.
> In contrast, an **empty string (`''`) is a concrete non-NULL scalar value**. If two or more rows in `Payments` contain an empty string `''`, creating a unique index on `transaction_reference` will fail immediately with:
> `ERROR 1062 (23000): Duplicate entry '' for key 'uq_payments_transaction_ref'`.
> Pre-flight Check 1 therefore inspects **all non-NULL values without exception** (`WHERE transaction_reference IS NOT NULL`) so no potential unique constraint violation is missed.

**Safe, Auditable Conflict Resolution Protocol:**
1. **Identify and Inspect Conflicting Payment Records**:
   Run the following inspection query to extract full accounting context for any conflicting values:
   ```sql
   SELECT id, bill_id, amount, payment_method, transaction_reference, payment_date, notes
   FROM Payments
   WHERE transaction_reference IN (
       SELECT transaction_reference
       FROM Payments
       WHERE transaction_reference IS NOT NULL
       GROUP BY transaction_reference
       HAVING COUNT(*) > 1
   )
   ORDER BY transaction_reference, payment_date;
   ```
2. **Determine the Correct Meaning of Each Value**:
   - Inspect the associated `Bill`, invoice numbers, physical payment receipts, card POS machine audit slips, or bank/UPI gateway settlement reports.
   - **Financial Auditability & Record Preservation Rule**: NEVER invent synthetic reference numbers and NEVER delete payment records to resolve constraint collisions. Payment history must remain completely intact.
3. **Empty String Remediation (`''` -> `NULL`)**:
   - In legacy databases, payments recorded without a transaction reference (e.g., Cash or Cheque where no electronic reference was provided) may have been stored as empty strings `''` rather than `NULL`.
   - Convert empty strings to `NULL` **only if** the application's business rules and data model establish that an empty reference denotes "not provided":
     ```sql
     -- Safely normalize unprovided references to NULL
     UPDATE Payments
     SET transaction_reference = NULL
     WHERE transaction_reference = '';
     ```
4. **Duplicate Non-Empty Reference Remediation**:
   - If two distinct payment rows share a real non-empty reference (e.g. duplicate UTR or auth code):
     - Check whether an operator double-submitted the payment form or entered the wrong reference number.
     - Obtain the actual, verified reference number from the payment gateway or bank statement.
     - Update the record using an explicitly logged administrative change statement with the correct, verified reference.
5. **Mandatory Pre-Flight Re-verification**:
   - The operator **must rerun Check 1** and confirm that it returns **zero rows** before proceeding to Phase 4 DDL execution.
   - Never run destructive schema reinitialization (`schema.sql`) against an existing populated database.

#### Phase 3: Inspect Actual Foreign Key Constraint Names
Constraint names differ depending on whether the database was created with `schema.sql` (e.g. `fk_payment_bill`) or SQLAlchemy `db.create_all()` (e.g. `Payments_ibfk_1`). Query the actual names before dropping:

```sql
SELECT
    TABLE_NAME,
    COLUMN_NAME,
    CONSTRAINT_NAME,
    REFERENCED_TABLE_NAME,
    REFERENCED_COLUMN_NAME
FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
WHERE TABLE_SCHEMA = DATABASE()
  AND REFERENCED_TABLE_NAME IS NOT NULL
  AND TABLE_NAME IN ('Payments', 'Bills', 'ServiceBookings', 'ServiceDetails')
ORDER BY TABLE_NAME, COLUMN_NAME;
```

#### Phase 4: Step-by-Step DDL Alterations (Fully Portable)

```sql
-- Step 1: Add Customers.updated_at (Portable across MySQL 8.0 and MariaDB)
-- In MariaDB: ALTER TABLE Customers ADD COLUMN IF NOT EXISTS updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;
-- In standard MySQL 8.0: Check column existence before adding:
SET @col_exists = (
    SELECT COUNT(*)
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'Customers'
      AND COLUMN_NAME = 'updated_at'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE Customers ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;',
    'SELECT "Column updated_at already exists" AS status;'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Step 2: Enforce 1:1 relationship on ServiceDetails.booking_id
ALTER TABLE ServiceDetails ADD CONSTRAINT uq_service_details_booking UNIQUE (booking_id);

-- Step 3: Replace Payments cascade with ON DELETE RESTRICT
-- (Replace <actual_payment_fk_name> with the constraint name from Phase 3, e.g., fk_payment_bill or Payments_ibfk_1)
ALTER TABLE Payments DROP FOREIGN KEY `<actual_payment_fk_name>`;
ALTER TABLE Payments ADD CONSTRAINT fk_payment_bill FOREIGN KEY (bill_id) REFERENCES Bills(id) ON DELETE RESTRICT;

-- Step 4: Enforce UNIQUE constraint on Payments.transaction_reference
ALTER TABLE Payments ADD CONSTRAINT uq_payments_transaction_ref UNIQUE (transaction_reference);

-- Step 5: Replace Bills cascades with ON DELETE RESTRICT
-- (Replace <actual_bill_booking_fk> and <actual_bill_customer_fk> with names from Phase 3)
ALTER TABLE Bills DROP FOREIGN KEY `<actual_bill_booking_fk>`;
ALTER TABLE Bills ADD CONSTRAINT fk_bill_booking FOREIGN KEY (booking_id) REFERENCES ServiceBookings(id) ON DELETE RESTRICT;

ALTER TABLE Bills DROP FOREIGN KEY `<actual_bill_customer_fk>`;
ALTER TABLE Bills ADD CONSTRAINT fk_bill_customer FOREIGN KEY (customer_id) REFERENCES Customers(id) ON DELETE RESTRICT;

-- Step 6: Replace ServiceBookings cascades with ON DELETE RESTRICT
-- (Replace <actual_booking_customer_fk> and <actual_booking_vehicle_fk> with names from Phase 3)
ALTER TABLE ServiceBookings DROP FOREIGN KEY `<actual_booking_customer_fk>`;
ALTER TABLE ServiceBookings ADD CONSTRAINT fk_booking_customer FOREIGN KEY (customer_id) REFERENCES Customers(id) ON DELETE RESTRICT;

ALTER TABLE ServiceBookings DROP FOREIGN KEY `<actual_booking_vehicle_fk>`;
ALTER TABLE ServiceBookings ADD CONSTRAINT fk_booking_vehicle FOREIGN KEY (vehicle_id) REFERENCES Vehicles(id) ON DELETE RESTRICT;
```

#### Phase 5: Post-Migration Verification
Confirm the new restrictive constraints and indexes are active:
```sql
-- Verify foreign keys reference ON DELETE RESTRICT
SELECT
    TABLE_NAME,
    CONSTRAINT_NAME,
    DELETE_RULE
FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS
WHERE CONSTRAINT_SCHEMA = DATABASE()
  AND TABLE_NAME IN ('Payments', 'Bills', 'ServiceBookings');

-- Verify unique indexes exist
SHOW INDEX FROM Payments WHERE Key_name = 'uq_payments_transaction_ref';
SHOW INDEX FROM ServiceDetails WHERE Key_name = 'uq_service_details_booking';
```

#### Phase 6: Rollback Procedure (Emergency Reversion)
If an emergency rollback is required:
```sql
-- Revert Payments foreign key
ALTER TABLE Payments DROP FOREIGN KEY fk_payment_bill;
ALTER TABLE Payments DROP INDEX uq_payments_transaction_ref;
ALTER TABLE Payments ADD CONSTRAINT fk_payment_bill FOREIGN KEY (bill_id) REFERENCES Bills(id) ON DELETE CASCADE;

-- Revert Bills foreign keys
ALTER TABLE Bills DROP FOREIGN KEY fk_bill_booking;
ALTER TABLE Bills DROP FOREIGN KEY fk_bill_customer;
ALTER TABLE Bills ADD CONSTRAINT fk_bill_booking FOREIGN KEY (booking_id) REFERENCES ServiceBookings(id) ON DELETE CASCADE;
ALTER TABLE Bills ADD CONSTRAINT fk_bill_customer FOREIGN KEY (customer_id) REFERENCES Customers(id) ON DELETE CASCADE;

-- Revert ServiceBookings foreign keys
ALTER TABLE ServiceBookings DROP FOREIGN KEY fk_booking_customer;
ALTER TABLE ServiceBookings DROP FOREIGN KEY fk_booking_vehicle;
ALTER TABLE ServiceBookings ADD CONSTRAINT fk_booking_customer FOREIGN KEY (customer_id) REFERENCES Customers(id) ON DELETE CASCADE;
ALTER TABLE ServiceBookings ADD CONSTRAINT fk_booking_vehicle FOREIGN KEY (vehicle_id) REFERENCES Vehicles(id) ON DELETE CASCADE;

-- Revert ServiceDetails unique constraint
ALTER TABLE ServiceDetails DROP INDEX uq_service_details_booking;
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
