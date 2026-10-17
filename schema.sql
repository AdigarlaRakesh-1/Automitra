-- =====================================================================
-- AutoMitra: Centralized Relational Database Schema (MySQL 8.0+)
-- Problem Focus: Eliminating duplicate customer records, missed bookings,
-- mechanic allocation, spare-parts stock, billing, and service-history tracking.
-- Currency: Indian Rupees (INR - ₹)
-- Proposed Tables:
--   1. Customers
--   2. Vehicles
--   3. Mechanics
--   4. ServiceBookings
--   5. ServiceDetails
--   6. SpareParts
--   7. PartUsage
--   8. Bills
--   9. Payments
-- =====================================================================

CREATE DATABASE IF NOT EXISTS automitra CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE automitra;

-- Disable foreign key checks during creation
SET FOREIGN_KEY_CHECKS = 0;

-- ---------------------------------------------------------------------
-- 1. Customers Table
-- Solves: Duplicate customer records with indexed phone & email and unique constraints/warnings
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS Customers;
CREATE TABLE Customers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    phone VARCHAR(30) NOT NULL UNIQUE,
    email VARCHAR(120) NULL,
    address TEXT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_customer_phone (phone),
    INDEX idx_customer_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------
-- 2. Vehicles Table
-- Relates customer to multiple vehicles, vehicle history and identification
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS Vehicles;
CREATE TABLE Vehicles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT NOT NULL,
    license_plate VARCHAR(30) NOT NULL UNIQUE,
    make VARCHAR(60) NOT NULL,
    model VARCHAR(60) NOT NULL,
    year INT NOT NULL,
    vin VARCHAR(60) NULL,
    mileage INT DEFAULT 0,
    fuel_type VARCHAR(30) DEFAULT 'Petrol',
    color VARCHAR(40) NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_vehicle_customer FOREIGN KEY (customer_id) REFERENCES Customers(id) ON DELETE CASCADE,
    INDEX idx_vehicle_plate (license_plate),
    INDEX idx_vehicle_customer (customer_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------
-- 3. Mechanics Table
-- Solves: Mechanic allocation and workload management
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS Mechanics;
CREATE TABLE Mechanics (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    phone VARCHAR(30) NOT NULL,
    specialty VARCHAR(100) NOT NULL DEFAULT 'General Service',
    status ENUM('Available', 'Busy', 'On Leave') DEFAULT 'Available',
    hourly_rate DECIMAL(10,2) DEFAULT 45.00,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_mechanic_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------
-- 4. ServiceBookings Table
-- Solves: Missed bookings and service scheduling
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS ServiceBookings;
CREATE TABLE ServiceBookings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    booking_number VARCHAR(40) NOT NULL UNIQUE,
    customer_id INT NOT NULL,
    vehicle_id INT NOT NULL,
    booking_date DATE NOT NULL,
    booking_time VARCHAR(20) NOT NULL,
    service_type VARCHAR(100) NOT NULL,
    status ENUM('Pending', 'Confirmed', 'In Progress', 'Completed', 'Cancelled', 'Missed') DEFAULT 'Pending',
    notes TEXT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_booking_customer FOREIGN KEY (customer_id) REFERENCES Customers(id) ON DELETE CASCADE,
    CONSTRAINT fk_booking_vehicle FOREIGN KEY (vehicle_id) REFERENCES Vehicles(id) ON DELETE CASCADE,
    INDEX idx_booking_date (booking_date),
    INDEX idx_booking_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------
-- 5. ServiceDetails Table
-- Solves: Job details and mechanic assignment
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS ServiceDetails;
CREATE TABLE ServiceDetails (
    id INT AUTO_INCREMENT PRIMARY KEY,
    booking_id INT NOT NULL,
    mechanic_id INT NULL,
    job_description TEXT NOT NULL,
    diagnosis TEXT NULL,
    labor_hours DECIMAL(5,2) DEFAULT 1.00,
    labor_cost DECIMAL(10,2) DEFAULT 50.00,
    status ENUM('Assigned', 'In Progress', 'Awaiting Parts', 'Completed') DEFAULT 'Assigned',
    started_at DATETIME NULL,
    completed_at DATETIME NULL,
    CONSTRAINT fk_detail_booking FOREIGN KEY (booking_id) REFERENCES ServiceBookings(id) ON DELETE CASCADE,
    CONSTRAINT fk_detail_mechanic FOREIGN KEY (mechanic_id) REFERENCES Mechanics(id) ON DELETE SET NULL,
    INDEX idx_detail_booking (booking_id),
    INDEX idx_detail_mechanic (mechanic_id),
    INDEX idx_detail_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------
-- 6. SpareParts Table
-- Solves: Spare-parts stock and inventory management
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS SpareParts;
CREATE TABLE SpareParts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    part_number VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(150) NOT NULL,
    category VARCHAR(80) NOT NULL,
    cost_price DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    selling_price DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    stock_quantity INT NOT NULL DEFAULT 0,
    min_reorder_level INT NOT NULL DEFAULT 5,
    location_bin VARCHAR(50) NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_part_number (part_number),
    INDEX idx_part_stock (stock_quantity)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------
-- 7. PartUsage Table
-- Tracks spare parts consumed per job, decrements inventory stock
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS PartUsage;
CREATE TABLE PartUsage (
    id INT AUTO_INCREMENT PRIMARY KEY,
    service_detail_id INT NOT NULL,
    part_id INT NOT NULL,
    quantity INT NOT NULL DEFAULT 1,
    unit_price DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    subtotal DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    used_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_usage_detail FOREIGN KEY (service_detail_id) REFERENCES ServiceDetails(id) ON DELETE CASCADE,
    CONSTRAINT fk_usage_part FOREIGN KEY (part_id) REFERENCES SpareParts(id) ON DELETE RESTRICT,
    INDEX idx_usage_detail (service_detail_id),
    INDEX idx_usage_part (part_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------
-- 8. Bills Table
-- Solves: Accurate billing, labor + parts calculation, and taxes
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS Bills;
CREATE TABLE Bills (
    id INT AUTO_INCREMENT PRIMARY KEY,
    invoice_number VARCHAR(50) NOT NULL UNIQUE,
    booking_id INT NOT NULL UNIQUE,
    customer_id INT NOT NULL,
    parts_total DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    labor_total DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    tax_amount DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    discount_amount DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    grand_total DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    payment_status ENUM('Unpaid', 'Partially Paid', 'Paid') DEFAULT 'Unpaid',
    issued_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_bill_booking FOREIGN KEY (booking_id) REFERENCES ServiceBookings(id) ON DELETE CASCADE,
    CONSTRAINT fk_bill_customer FOREIGN KEY (customer_id) REFERENCES Customers(id) ON DELETE CASCADE,
    INDEX idx_bill_invoice (invoice_number),
    INDEX idx_bill_status (payment_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------
-- 9. Payments Table
-- Solves: Payment recording, partial payment tracking and reconciliation
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS Payments;
CREATE TABLE Payments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    bill_id INT NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    payment_method ENUM('Cash', 'Credit Card', 'Debit Card', 'UPI / Online', 'Bank Transfer') NOT NULL DEFAULT 'Cash',
    transaction_reference VARCHAR(100) NULL,
    payment_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    notes TEXT NULL,
    CONSTRAINT fk_payment_bill FOREIGN KEY (bill_id) REFERENCES Bills(id) ON DELETE CASCADE,
    INDEX idx_payment_bill (bill_id),
    INDEX idx_payment_date (payment_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

SET FOREIGN_KEY_CHECKS = 1;
