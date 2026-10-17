#!/usr/bin/env python
"""
Database Initialization & Migration Utility for AutoMitra
Populates all 9 relational tables:
  1. Customers
  2. Vehicles
  3. Mechanics
  4. ServiceBookings
  5. ServiceDetails
  6. SpareParts
  7. PartUsage
  8. Bills
  9. Payments
"""
import sys
from app import create_app
from models import db
from seed_data import seed_database

def main():
    print("=" * 65)
    print(" AutoMitra Database Setup & Seeder (INR)")
    print(" Relational Schema: 9 Tables (MySQL / SQLAlchemy)")
    print("=" * 65)

    app = create_app()
    with app.app_context():
        print("[1/2] Creating tables according to relational schema...")
        db.create_all()
        print("[2/2] Checking sample records & seeding database...")
        seed_database()
        print("\nDatabase initialization complete! You can now start the application:")
        print("   python app.py\n")

if __name__ == '__main__':
    main()
