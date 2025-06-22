#!/usr/bin/env python3
"""
Database migration script to add category_id column to Product table
"""

from sqlalchemy import text
from eshop import app, db

def add_category_id_column():
    with app.app_context():
        # Check if column already exists
        result = db.session.execute(text("PRAGMA table_info(product)"))
        columns = [row[1] for row in result]
        
        if 'category_id' in columns:
            print("category_id column already exists")
            return
        
        print("Adding category_id column to Product table...")
        
        # Add the column (nullable initially)
        db.session.execute(text("ALTER TABLE product ADD COLUMN category_id INTEGER"))
        db.session.commit()
        
        print("category_id column added successfully!")

if __name__ == '__main__':
    add_category_id_column()