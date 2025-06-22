#!/usr/bin/env python3
"""
Test all personalization algorithms to ensure they're working correctly
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eshop import create_app
from eshop.models import db, User, Product, Order, OrderItem, UserInteraction, GuestInteraction, BestSeller, TrendingProduct
from eshop.recommender import Recommender
from eshop.analytics import AnalyticsEngine
from eshop.offers import OfferGenerator
from eshop.hybrid_recommender import HybridRecommender
from datetime import datetime, timedelta
import random

def test_all_algorithms():
    """Test all personalization algorithms"""
    app = create_app()
    
    with app.app_context():
        print("=== Testing Personalization Algorithms ===\n")
        
        # 1. Test Best Sellers
        print("1. Testing Best Sellers Algorithm...")
        analytics = AnalyticsEngine()
        analytics.calculate_best_sellers()
        
        best_sellers = BestSeller.query.order_by(BestSeller.sales_count.desc()).limit(5).all()
        if best_sellers:
            print(f"   ✓ Found {len(best_sellers)} best sellers")
            for bs in best_sellers[:3]:
                product = Product.query.get(bs.product_id)
                if product:
                    print(f"     - {product.name}: sales={bs.sales_count}")
        else:
            print("   ⚠ No best sellers found (may need more order data)")
            
        # 2. Test Trending Products
        print("\n2. Testing Trending Products Algorithm...")
        analytics.calculate_trending_products()
        
        trending = TrendingProduct.query.order_by(TrendingProduct.trending_score.desc()).limit(5).all()
        if trending:
            print(f"   ✓ Found {len(trending)} trending products")
            for tp in trending[:3]:
                product = Product.query.get(tp.product_id)
                if product:
                    print(f"     - {product.name}: score={tp.trending_score:.2f}")
        else:
            print("   ⚠ No trending products found (may need more interaction data)")
            
        # 3. Test Guest Recommendations
        print("\n3. Testing Guest Recommendations...")
        session_id = "test-guest-session"
        
        # Initial recommendations (50% best sellers + 50% trending)
        initial_recs = Recommender.get_recommendations_for_guest(session_id, limit=10)
        print(f"   ✓ Initial recommendations: {len(initial_recs)} products")
        
        # Add some interactions
        products = Product.query.limit(5).all()
        for i, product in enumerate(products):
            interaction = GuestInteraction(
                session_id=session_id,
                product_id=product.id,
                interaction_type='view',
                timestamp=datetime.utcnow() - timedelta(minutes=i)
            )
            db.session.add(interaction)
        db.session.commit()
        
        # Test cold start after interactions
        cold_start_recs = Recommender.get_recommendations_for_guest(session_id, limit=10)
        print(f"   ✓ Cold start recommendations after 5 interactions: {len(cold_start_recs)} products")
        
        # 4. Test Authenticated User Recommendations
        print("\n4. Testing Authenticated User Recommendations...")
        
        # Find or create a test user
        test_user = User.query.filter_by(email='test@example.com').first()
        if not test_user:
            test_user = User(email='test@example.com')
            test_user.set_password('password123')
            db.session.add(test_user)
            db.session.commit()
            
        # Test new user (no data)
        new_user_recs = Recommender.get_recommendations_for_user(test_user.id, limit=10)
        print(f"   ✓ New user recommendations: {len(new_user_recs)} products")
        
        # Add interactions for the user
        products = Product.query.limit(10).all()
        for i, product in enumerate(products):
            interaction = UserInteraction(
                user_id=test_user.id,
                product_id=product.id,
                interaction_type='view',
                timestamp=datetime.utcnow() - timedelta(hours=i)
            )
            db.session.add(interaction)
        db.session.commit()
        
        # Test with minimal data
        minimal_data_recs = Recommender.get_recommendations_for_user(test_user.id, limit=10)
        print(f"   ✓ Minimal data recommendations (10 interactions): {len(minimal_data_recs)} products")
        
        # 5. Test Hybrid Recommender
        print("\n5. Testing Hybrid Recommender...")
        hybrid = HybridRecommender()
        
        # Test weight configuration
        print(f"   ✓ Algorithm weight configurations:")
        print(f"     - New users: {hybrid.weights['new_user']}")
        print(f"     - Minimal data users: {hybrid.weights['minimal_data']}")
        print(f"     - Established users: {hybrid.weights['established_user']}")
            
        # Get hybrid recommendations
        hybrid_recs = hybrid.get_recommendations(test_user.id, limit=10)
        print(f"   ✓ Hybrid recommendations: {len(hybrid_recs)} products")
        
        # 6. Test Linear SVM
        print("\n6. Testing Linear SVM Recommender...")
        try:
            from eshop.ml_recommenders import LinearSVMRecommender
            svm = LinearSVMRecommender()
            
            # Train the model if enough data
            if svm.train_model():
                svm_recs = svm.get_recommendations(test_user.id, limit=5)
                print(f"   ✓ Linear SVM recommendations: {len(svm_recs)} products")
            else:
                print("   ⚠ Not enough data to train Linear SVM")
        except Exception as e:
            print(f"   ✗ Error testing Linear SVM: {e}")
            
        # 7. Test Advanced Neighbors
        print("\n7. Testing Advanced Neighbors Recommender...")
        try:
            from eshop.ml_recommenders import AdvancedNeighborsRecommender
            neighbors = AdvancedNeighborsRecommender()
            
            neighbor_recs = neighbors.get_recommendations(test_user.id, limit=5)
            print(f"   ✓ Advanced Neighbors recommendations: {len(neighbor_recs)} products")
        except Exception as e:
            print(f"   ✗ Error testing Advanced Neighbors: {e}")
            
        # 8. Test Shopping Cart Recommender
        print("\n8. Testing Shopping Cart Recommender...")
        try:
            from eshop.shopping_cart_recommender import ShoppingCartRecommender
            cart_rec = ShoppingCartRecommender()
            
            # Create a sample cart
            cart_items = Product.query.limit(3).all()
            cart_product_ids = [p.id for p in cart_items]
            
            cart_recs = cart_rec.get_recommendations_for_cart(cart_product_ids, limit=5)
            print(f"   ✓ Shopping cart recommendations for {len(cart_product_ids)} items: {len(cart_recs)} products")
        except Exception as e:
            print(f"   ✗ Error testing Shopping Cart: {e}")
            
        # 9. Test Personalized Offers
        print("\n9. Testing Personalized Offers...")
        offer_gen = OfferGenerator()
        
        # Generate offers for the test user
        offers = offer_gen.generate_offers_for_user(test_user.id, num_offers=4)
        print(f"   ✓ Generated {len(offers)} personalized offers")
        
        # Check active offers
        active_offers = offer_gen.get_active_offers(test_user.id)
        print(f"   ✓ Active offers for user: {len(active_offers)}")
        
        # 10. Test A/B Testing Framework
        print("\n10. Testing A/B Testing Framework...")
        try:
            from eshop.ab_testing import ABTestingFramework
            ab_test = ABTestingFramework()
            
            # Create a test experiment
            experiment_id = ab_test.create_experiment(
                name="Test Algorithm Comparison",
                description="Testing recommendation algorithms",
                control_algorithm="best_sellers",
                variant_algorithm="hybrid",
                traffic_split=0.5
            )
            
            if experiment_id:
                print(f"   ✓ Created A/B test experiment: {experiment_id}")
                
                # Get variant for user
                variant = ab_test.get_user_variant(experiment_id, test_user.id)
                print(f"   ✓ User assigned to variant: {variant}")
            else:
                print("   ⚠ Could not create A/B test experiment")
        except Exception as e:
            print(f"   ✗ Error testing A/B Testing: {e}")
            
        print("\n=== All Tests Completed ===")


if __name__ == '__main__':
    test_all_algorithms()