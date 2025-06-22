#!/usr/bin/env python3
"""
Database migration script to add PersonalizedOffer table
"""

from app import app, db
from models import PersonalizedOffer

def migrate():
    with app.app_context():
        # Create the PersonalizedOffer table
        print("Creating PersonalizedOffer table...")
        db.create_all()
        print("Migration completed successfully!")

if __name__ == '__main__':
    migrate()