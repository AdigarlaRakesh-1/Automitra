# AutoMitra - Centralized Garage Management System (₹ INR)

An open-source automotive service center management web application engineered to solve critical operational bottlenecks in small and medium auto workshops, fully localized in **Indian Rupees (₹)**.

---

## 🎯 Problem Statement & Personalized Project Focus

Small and medium auto service centers often struggle with six major operational pain points:

1. **Duplicate Customer Records**: Fragmented customer entries across multiple visits lead to conflicting contact details, communication breakdown, and distorted service histories.
2. **Missed Bookings**: Unmonitored appointments lead to bay vacancies, idle technician hours, and customer churn when follow-ups are omitted.
3. **Mechanic Allocation & Workload Imbalances**: Ineffective visibility into technician specialties, status (Available, Busy, On Leave), and active jobs causing bay bottlenecks.
4. **Spare-Parts Stock Outages**: Poor inventory visibility, unexpected stockouts during active repairs, and missing reorder alerts causing vehicle turnaround delays.
5. **Billing Inaccuracies**: Inconsistencies when combining technician labor hours with consumed parts, leading to missed charges, billing errors, or dispute-prone invoices.
6. **Service-History Tracking**: Inability to pull a vehicle's chronological repair timeline, past mechanic diagnoses, and replaced parts during customer diagnostics.

**AutoMitra** addresses all of these challenges through a web application backed by a centralized relational database.

---

## 🗄️ Proposed Relational Database Schema (9 Tables)

The centralized relational database comprises the 9 proposed tables with foreign-key constraints, cascading actions, and indexing:

| # | Table Name | Purpose & Solution | Key Fields |
|---|------------|--------------------|------------|
| 1 | **`Customers`** | Eliminates duplicate customer records with live unique phone & email detection | `id`, `name`, `phone` *(unique)*, `email`, `address`, `created_at` |
| 2 | **`Vehicles`** | Maps multiple vehicles per owner and links full repair logs | `id`, `customer_id` *(FK)*, `license_plate` *(unique)*, `make`, `model`, `year`, `vin`, `mileage`, `fuel_type` |
| 3 | **`Mechanics`** | Manages mechanic bay allocation, specialties, and statuses | `id`, `name`, `phone`, `specialty`, `status` *(Available/Busy/On Leave)*, `hourly_rate` *(₹/hr)*, `created_at` |
| 4 | **`ServiceBookings`** | Resolves missed bookings with proactive alerts & 1-click rescheduling | `id`, `booking_number` *(unique)*, `customer_id` *(FK)*, `vehicle_id` *(FK)*, `booking_date`, `booking_time`, `service_type`, `status` *(Pending/Confirmed/In Progress/Completed/Missed)* |
| 5 | **`ServiceDetails`** | Tracks technician job orders, diagnostics, and labor hours | `id`, `booking_id` *(FK)*, `mechanic_id` *(FK)*, `job_description`, `diagnosis`, `labor_hours`, `labor_cost` *(₹)*, `status`, `started_at`, `completed_at` |
| 6 | **`SpareParts`** | Monitors inventory stock, categories, and min safety reorder thresholds | `id`, `part_number` *(SKU, unique)*, `name`, `category`, `cost_price` *(₹)*, `selling_price` *(₹)*, `stock_quantity`, `min_reorder_level`, `location_bin` |
| 7 | **`PartUsage`** | Records parts consumed on a job; automatically decrements inventory stock | `id`, `service_detail_id` *(FK)*, `part_id` *(FK)*, `quantity`, `unit_price` *(₹)*, `subtotal` *(₹)*, `used_at` |
| 8 | **`Bills`** | Auto-generates invoices consolidating labor charges, parts used, and taxes | `id`, `invoice_number` *(unique)*, `booking_id` *(FK)*, `customer_id` *(FK)*, `parts_total`, `labor_total`, `tax_amount`, `discount_amount`, `grand_total` *(₹)*, `payment_status` |
| 9 | **`Payments`** | Records payment transactions (UPI, Card, Cash, etc.) and tracks balance | `id`, `bill_id` *(FK)*, `amount` *(₹)*, `payment_method`, `transaction_reference`, `payment_date`, `notes` |

The native DDL script is provided in `schema.sql`.

---

## 🛠️ Technology Stack

- **Backend**: Python 3.11+ / Flask 3.1
- **ORM / Database Access**: SQLAlchemy 2.0 / Flask-SQLAlchemy
- **Currency**: **Indian Rupees (INR - ₹)** across all labor, parts, bills, and payments
- **Database Engine**: 
  - **MySQL 8.0+** (native target via `PyMySQL`)
  - **Embedded SQLite** (`automitra.db`): explicitly enabled via `USE_SQLITE=true` for zero-setup local development and isolated testing.
- **Frontend**: Modern Vanilla HTML5 / CSS3 / Vanilla JavaScript
  - Dark / Light mode glassmorphism interface
  - Debounced live duplicate customer detection
  - Dynamic customer-to-vehicle dropdown loading
  - Printable Invoices and Payment Receipts in ₹

---

## 🚀 Quickstart & Installation

### 1. Prerequisites
Ensure you have **Python 3.10+** installed:
```bash
python --version
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 3. Database Configuration

#### Option A: Running with MySQL (Recommended for Production)
1. Start your local MySQL server (port 3306).
2. Create the database:
   ```sql
   CREATE DATABASE automitra CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```
3. Copy `.env.example` to `.env` and set your credentials:
   ```env
   SECRET_KEY=your-secure-random-secret-key-here
   MYSQL_USER=your_mysql_username
   MYSQL_PASSWORD=your_mysql_password
   MYSQL_HOST=localhost
   MYSQL_PORT=3306
   MYSQL_DB=automitra
   USE_SQLITE=false
   ```
4. Run the database initialization tool:
   ```bash
   python init_db.py
   ```

#### Option B: Zero-Setup Mode (Embedded SQLite for Local Development)
To run with zero setup using embedded SQLite, set `USE_SQLITE=true` in your `.env` or environment:
```bash
# In your .env or shell:
USE_SQLITE=true

# Initialize database:
python init_db.py
```

---

## 🖥️ Running the Web Application

Start the Flask development server:
```bash
python app.py
```
Open your browser and navigate to:
```
http://127.0.0.1:5000
```

---

## 🧪 Automated Testing

AutoMitra includes a comprehensive 41-item automated test suite covering all 9 tables, CSRF protection, concurrency safety, decimal precision accounting, cascade deletion restrictions, and real MySQL integration:

```bash
# Run test suite with isolated in-memory/file SQLite and live MySQL tests:
python -m pytest test_app.py -v
```

All 41 tests execute in ~7.5 seconds with zero deprecation warnings.

---

## 🔒 Security, CSRF Protection & Deployment Model

- **CSRF Protection**: All state-changing form actions (POST requests) are protected with cryptographic tokens via `Flask-WTF`. Missing or invalid tokens are rejected with HTTP 400.
- **Error Sanitization**: In production (`DEBUG=False`), HTTP 500 error handlers sanitize exception messages, ensuring internal tracebacks, SQL statements, and database credentials are never exposed.
- **Single-Operator Architecture**: AutoMitra is designed for single-operator internal garage operations. It does not implement multi-user authentication (passwords or RBAC).
- **Deployment Restrictions**:
  - **Do not expose directly to the public internet** without an authenticating reverse proxy (e.g., Cloudflare Access, Nginx with OIDC/HTTP Auth, or private Tailscale/VPN).
  - Bind to localhost (`127.0.0.1`) or a secured private local network in production.

---

## 📄 License
Released under the [MIT License](LICENSE).
