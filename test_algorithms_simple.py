#!/usr/bin/env python3
"""
Simple test of all personalization algorithms
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eshop import create_app
from eshop.models import db, User, Product, UserInteraction, GuestInteraction
from eshop.recommender import Recommender
from eshop.analytics import AnalyticsEngine
from eshop.offers import OfferGenerator
from datetime import datetime, timedelta

def test_algorithms():
    app = create_app()
    
    with app.app_context():
        print("\n=== PERSONALIZATION ALGORITHMS TEST REPORT ===\n")
        
        # 1. Analytics Engine
        print("1. ANALYTICS ENGINE")
        print("-" * 50)
        try:
            analytics = AnalyticsEngine()
            
            # Update best sellers
            analytics.calculate_best_sellers()
            print("✓ Best sellers calculation: SUCCESS")
            
            # Update trending products
            analytics.calculate_trending_products()
            print("✓ Trending products calculation: SUCCESS")
            
            # Get best sellers
            best_sellers = analytics.get_best_sellers(limit=5)
            print(f"✓ Retrieved {len(best_sellers)} best sellers")
            
            # Get trending products
            trending = analytics.get_trending_products(limit=5)
            print(f"✓ Retrieved {len(trending)} trending products")
        except Exception as e:
            print(f"✗ Analytics Engine Error: {e}")
            
        # 2. Guest Recommendations
        print("\n2. GUEST RECOMMENDATIONS")
        print("-" * 50)
        try:
            session_id = "test-session-001"
            
            # Initial recommendations
            initial = Recommender.get_recommendations_for_guest(session_id, limit=10)
            print(f"✓ Initial guest recommendations: {len(initial)} products")
            
            # Add interactions
            products = Product.query.limit(5).all()
            for i, product in enumerate(products):
                interaction = GuestInteraction(
                    session_id=session_id,
                    product_id=product.id,
                    interaction_type='view',
                    timestamp=datetime.utcnow()
                )
                db.session.add(interaction)
            db.session.commit()
            
            # Cold start recommendations
            cold_start = Recommender.get_recommendations_for_guest(session_id, limit=10)
            print(f"✓ Cold start recommendations: {len(cold_start)} products")
            
            # Clean up
            GuestInteraction.query.filter_by(session_id=session_id).delete()
            db.session.commit()
        except Exception as e:
            print(f"✗ Guest Recommendations Error: {e}")
            
        # 3. User Recommendations
        print("\n3. USER RECOMMENDATIONS")
        print("-" * 50)
        try:
            # Get or create test user
            test_user = User.query.filter_by(email='algo_test@example.com').first()
            if not test_user:
                test_user = User(email='algo_test@example.com')
                test_user.set_password('test123')
                db.session.add(test_user)
                db.session.commit()
            
            # New user recommendations
            new_user_recs = Recommender.get_recommendations_for_user(test_user.id, limit=10)
            print(f"✓ New user recommendations: {len(new_user_recs)} products")
            
            # Add minimal interactions
            products = Product.query.limit(10).all()
            for i, product in enumerate(products):
                interaction = UserInteraction(
                    user_id=test_user.id,
                    product_id=product.id,
                    interaction_type='view',
                    timestamp=datetime.utcnow()
                )
                db.session.add(interaction)
            db.session.commit()
            
            # Minimal data recommendations
            minimal_recs = Recommender.get_recommendations_for_user(test_user.id, limit=10)
            print(f"✓ Minimal data recommendations: {len(minimal_recs)} products")
            
            # Clean up
            UserInteraction.query.filter_by(user_id=test_user.id).delete()
            db.session.commit()
        except Exception as e:
            print(f"✗ User Recommendations Error: {e}")
            
        # 4. ML Algorithms
        print("\n4. ML ALGORITHMS")
        print("-" * 50)
        
        # Linear SVM
        try:
            from eshop.ml_recommenders import LinearSVMRecommender
            svm = LinearSVMRecommender()
            print("✓ Linear SVM Recommender: IMPORTED")
        except Exception as e:
            print(f"✗ Linear SVM Import Error: {e}")
            
        # Advanced Neighbors
        try:
            from eshop.ml_recommenders import AdvancedNeighborsRecommender
            neighbors = AdvancedNeighborsRecommender()
            print("✓ Advanced Neighbors Recommender: IMPORTED")
        except Exception as e:
            print(f"✗ Advanced Neighbors Import Error: {e}")
            
        # Shopping Cart
        try:
            from eshop.shopping_cart_recommender import ShoppingCartRecommender
            cart = ShoppingCartRecommender()
            # Test with sample product IDs
            products = Product.query.limit(3).all()
            if products:
                cart_ids = [p.id for p in products]
                cart_recs = cart.get_recommendations_for_cart(cart_ids, limit=5)
                print(f"✓ Shopping Cart Recommender: {len(cart_recs)} recommendations")
            else:
                print("⚠ Shopping Cart: No products to test with")
        except Exception as e:
            print(f"✗ Shopping Cart Error: {e}")
            
        # 5. Hybrid Recommender
        print("\n5. HYBRID RECOMMENDER")
        print("-" * 50)
        try:
            from eshop.hybrid_recommender import HybridRecommender
            hybrid = HybridRecommender()
            hybrid_recs = hybrid.get_recommendations(test_user.id, limit=10)
            print(f"✓ Hybrid recommendations: {len(hybrid_recs)} products")
        except Exception as e:
            print(f"✗ Hybrid Recommender Error: {e}")
            
        # 6. Personalized Offers
        print("\n6. PERSONALIZED OFFERS")
        print("-" * 50)
        try:
            offer_gen = OfferGenerator()
            
            # Generate offers
            offers = offer_gen.generate_offers_for_user(test_user.id, num_offers=4)
            print(f"✓ Generated {len(offers)} personalized offers")
            
            # Get active offers
            active = offer_gen.get_active_offers(test_user.id)
            print(f"✓ Active offers: {len(active)}")
        except Exception as e:
            print(f"✗ Offers Error: {e}")
            
        # 7. A/B Testing
        print("\n7. A/B TESTING FRAMEWORK")
        print("-" * 50)
        try:
            from eshop.ab_testing import ABTestingFramework
            ab_test = ABTestingFramework()
            print("✓ A/B Testing Framework: IMPORTED")
            
            # Try to create experiment
            exp_id = ab_test.create_experiment(
                name="Test Experiment",
                description="Testing",
                control_algorithm="best_sellers",
                variant_algorithm="hybrid",
                traffic_split=0.5
            )
            if exp_id:
                print(f"✓ Created experiment: {exp_id}")
        except Exception as e:
            print(f"✗ A/B Testing Error: {e}")
            
        # 8. Caching
        print("\n8. RECOMMENDATION CACHE")
        print("-" * 50)
        try:
            from eshop.recommendation_cache import get_cache
            cache = get_cache()
            if cache.redis_available:
                print("✓ Redis cache: AVAILABLE")
            else:
                print("⚠ Redis cache: NOT AVAILABLE (using in-memory)")
        except Exception as e:
            print(f"✗ Cache Error: {e}")
            
        print("\n=== TEST COMPLETE ===\n")


if __name__ == '__main__':
    test_algorithms()