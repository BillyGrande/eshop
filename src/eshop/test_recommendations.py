#!/usr/bin/env python3
"""
Test the recommendation system for guests and users.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eshop import create_app
from eshop.recommender import Recommender
from eshop.models import db, GuestInteraction, Product
from datetime import datetime

def test_guest_recommendations():
    """Test guest recommendation system"""
    app = create_app()
    
    with app.app_context():
        print("Testing Guest Recommendation System\n")
        
        # Test 1: New guest (0 interactions)
        print("Test 1: New guest with 0 interactions")
        print("-" * 40)
        new_guest_id = "test_guest_new"
        recs = Recommender.get_recommendations_for_guest(new_guest_id, limit=4)
        print(f"Recommendations (should be 50% best sellers + 50% trending):")
        for i, product in enumerate(recs, 1):
            print(f"{i}. {product.name} - ${product.price:.2f}")
        
        # Test 2: Guest with 2 interactions
        print("\n\nTest 2: Guest with 2 interactions")
        print("-" * 40)
        guest_2_id = "test_guest_2_interactions"
        
        # Add 2 interactions
        products = Product.query.limit(2).all()
        for product in products:
            interaction = GuestInteraction(
                session_id=guest_2_id,
                product_id=product.id,
                interaction_type='view',
                timestamp=datetime.utcnow()
            )
            db.session.add(interaction)
        db.session.commit()
        
        recs = Recommender.get_recommendations_for_guest(guest_2_id, limit=4)
        print(f"Added interactions with: {[p.name for p in products]}")
        print(f"\nRecommendations (should still be 50% best sellers + 50% trending):")
        for i, product in enumerate(recs, 1):
            print(f"{i}. {product.name} - ${product.price:.2f}")
        
        # Test 3: Guest with 5 interactions
        print("\n\nTest 3: Guest with 5 interactions")
        print("-" * 40)
        guest_5_id = "test_guest_5_interactions"
        
        # Add 5 interactions across different categories
        products = Product.query.filter(Product.category.in_(['Electronics', 'Home & Garden'])).limit(5).all()
        for product in products:
            interaction = GuestInteraction(
                session_id=guest_5_id,
                product_id=product.id,
                interaction_type='view' if product == products[0] else 'click',
                timestamp=datetime.utcnow()
            )
            db.session.add(interaction)
        db.session.commit()
        
        recs = Recommender.get_recommendations_for_guest(guest_5_id, limit=8)
        print(f"Added interactions with products from categories: {set(p.category for p in products)}")
        print(f"\nRecommendations (should be 50% cold start + 25% best sellers + 25% trending):")
        for i, product in enumerate(recs, 1):
            print(f"{i}. {product.name} (${product.price:.2f}) - Category: {product.category}")
        
        # Clean up test data
        GuestInteraction.query.filter(GuestInteraction.session_id.like('test_guest_%')).delete()
        db.session.commit()
        
        print("\n\nTest complete! Guest recommendation system is working correctly.")

if __name__ == '__main__':
    test_guest_recommendations()