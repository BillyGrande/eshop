#!/usr/bin/env python3
"""
Add is_admin column to User table
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eshop import create_app
from eshop.models import db
from sqlalchemy import text

def add_admin_column():
    """Add is_admin column to User table if it doesn't exist"""
    app = create_app()
    
    with app.app_context():
        print("Adding is_admin column to User table...")
        
        try:
            # Check if column already exists
            result = db.session.execute(text("PRAGMA table_info(user)"))
            columns = [row[1] for row in result]
            
            if 'is_admin' not in columns:
                # Add the column
                db.session.execute(text("ALTER TABLE user ADD COLUMN is_admin BOOLEAN DEFAULT 0 NOT NULL"))
                db.session.commit()
                print("is_admin column added successfully!")
            else:
                print("is_admin column already exists!")
                
        except Exception as e:
            print(f"Error: {e}")
            db.session.rollback()

if __name__ == '__main__':
    add_admin_column()