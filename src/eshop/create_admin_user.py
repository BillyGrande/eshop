#!/usr/bin/env python3
"""
Create an admin user
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eshop import create_app
from eshop.models import db, User

def create_admin_user():
    """Create an admin user with default credentials"""
    app = create_app()
    
    with app.app_context():
        # Admin credentials
        admin_email = "admin@eshop.com"
        admin_password = "admin123!@#"
        
        # Check if admin already exists
        existing_admin = User.query.filter_by(email=admin_email).first()
        
        if existing_admin:
            print(f"Admin user already exists with email: {admin_email}")
            if not existing_admin.is_admin:
                existing_admin.is_admin = True
                db.session.commit()
                print("Updated existing user to admin role.")
        else:
            # Create new admin user
            admin = User(email=admin_email, is_admin=True)
            admin.set_password(admin_password)
            
            db.session.add(admin)
            db.session.commit()
            
            print("Admin user created successfully!")
            print(f"Email: {admin_email}")
            print(f"Password: {admin_password}")
            print("\nIMPORTANT: Please change the password after first login!")
        
        # Verify admin was created
        admin_user = User.query.filter_by(email=admin_email).first()
        if admin_user and admin_user.is_admin:
            print(f"\nVerified: Admin user exists with ID: {admin_user.id}")

if __name__ == '__main__':
    create_admin_user()