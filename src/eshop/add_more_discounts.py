#!/usr/bin/env python3
"""
Add more discounts to existing products
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import random
from eshop import create_app
from eshop.models import db, Product

def add_more_discounts():
    app = create_app()
    
    with app.app_context():
        # Get products without discounts
        products_no_discount = Product.query.filter_by(discount_percentage=0).all()
        print(f"Found {len(products_no_discount)} products without discounts")
        
        # Add discounts to 50% of them
        products_to_discount = random.sample(products_no_discount, len(products_no_discount) // 2)
        
        for product in products_to_discount:
            # Give them random discounts
            #product.discount_percentage = random.choice([5, 10, 15, 20, 25, 30])
            product.discount_percentage = 10
        
        db.session.commit()
        
        # Show new statistics
        total = Product.query.count()
        with_discount = Product.query.filter(Product.discount_percentage > 0).count()
        
        print(f"\nUpdated discount statistics:")
        print(f"Total products: {total}")
        print(f"Products with discount: {with_discount} ({with_discount/total*100:.1f}%)")
        print(f"Products without discount: {total - with_discount} ({(total-with_discount)/total*100:.1f}%)")

if __name__ == '__main__':
    add_more_discounts()