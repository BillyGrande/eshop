#!/usr/bin/env python3
"""
Create/update database tables.
Run this script to create new tables or update existing schema.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eshop import create_app
from eshop.models import db

def create_tables():
    """Create all database tables"""
    app = create_app()
    
    with app.app_context():
        print("Creating database tables...")
        
        # Create all tables
        db.create_all()
        
        print("Database tables created successfully!")
        
        # List all tables
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        print(f"\nDatabase contains {len(tables)} tables:")
        for table in sorted(tables):
            print(f"  - {table}")

if __name__ == '__main__':
    create_tables()