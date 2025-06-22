"""
Edge case tests for recommendation algorithms
Tests unusual scenarios and boundary conditions
"""

import pytest
from datetime import datetime, timedelta
from eshop.models import db, User, Product, UserInteraction, Order, OrderItem
from eshop.hybrid_recommender import HybridRecommender
from eshop.ml_recommenders import LinearSVMRecommender, AdvancedNeighborsRecommender
from eshop.shopping_cart_recommender import ShoppingCartRecommender
from eshop.analytics import AnalyticsEngine


class TestAlgorithmEdgeCases:
    """Test edge cases for individual recommendation algorithms"""
    
    def test_svm_with_single_interaction(self, app, sample_users, sample_products):
        """Test SVM with only one interaction"""
        with app.app_context():
            user = sample_users[0]
            product = sample_products[0]
            
            # Add single interaction
            interaction = UserInteraction(
                user_id=user.id,
                product_id=product.id,
                interaction_type='view'
            )
            db.session.add(interaction)
            db.session.commit()
            
            svm = LinearSVMRecommender()
            recommendations = svm.get_recommendations(user.id, sample_products, limit=5)
            
            # Should return empty (not enough data)
            assert recommendations == []
    
    def test_svm_with_identical_products(self, app):
        """Test SVM when all products have identical features"""
        with app.app_context():
            # Create user
            user = User(email='test@example.com')
            user.set_password('password')
            db.session.add(user)
            
            # Create identical products
            products = []
            for i in range(10):
                product = Product(
                    name=f'Identical Product {i}',
                    price=100.0,  # Same price
                    category='Electronics',  # Same category
                    brand='BrandA',  # Same brand
                    tags='tag1,tag2',  # Same tags
                    stock_quantity=100
                )
                products.append(product)
                db.session.add(product)
            
            db.session.commit()
            
            # Add varied interactions
            for i, product in enumerate(products[:5]):
                interaction = UserInteraction(
                    user_id=user.id,
                    product_id=product.id,
                    interaction_type='purchase' if i < 2 else 'view'
                )
                db.session.add(interaction)
            
            db.session.commit()
            
            svm = LinearSVMRecommender()
            recommendations = svm.get_recommendations(user.id, products, limit=5)
            
            # Should handle gracefully even with no feature variation
            assert isinstance(recommendations, list)
    
    def test_neighbors_with_no_common_items(self, app):
        """Test neighbors algorithm when users have no common items"""
        with app.app_context():
            # Create users
            users = []
            for i in range(3):
                user = User(email=f'user{i}@test.com')
                user.set_password('password')
                users.append(user)
                db.session.add(user)
            
            # Create products
            products = []
            for i in range(15):
                product = Product(
                    name=f'Product {i}',
                    price=50 + i * 10,
                    category='Test',
                    stock_quantity=100
                )
                products.append(product)
                db.session.add(product)
            
            db.session.commit()
            
            # Each user interacts with completely different products
            for user_idx, user in enumerate(users):
                start_idx = user_idx * 5
                for product in products[start_idx:start_idx + 5]:
                    interaction = UserInteraction(
                        user_id=user.id,
                        product_id=product.id,
                        interaction_type='view'
                    )
                    db.session.add(interaction)
            
            db.session.commit()
            
            neighbors = AdvancedNeighborsRecommender()
            recommendations = neighbors.get_recommendations(
                users[0].id, products, limit=5
            )
            
            # Should return empty (no similar users)
            assert recommendations == []
    
    def test_cart_recommender_with_single_item_orders(self, app):
        """Test cart recommender when all orders contain only one item"""
        with app.app_context():
            user = User(email='single@test.com')
            user.set_password('password')
            db.session.add(user)
            
            products = []
            for i in range(10):
                product = Product(
                    name=f'Product {i}',
                    price=100,
                    category='Test',
                    stock_quantity=100
                )
                products.append(product)
                db.session.add(product)
            
            db.session.commit()
            
            # Create orders with single items
            for product in products[:5]:
                order = Order(
                    user_id=user.id,
                    total=product.price
                )
                db.session.add(order)
                db.session.flush()
                
                order_item = OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    quantity=1,
                    price=product.price
                )
                db.session.add(order_item)
            
            db.session.commit()
            
            cart_rec = ShoppingCartRecommender()
            recommendations = cart_rec.get_cart_recommendations(
                [products[0].id], products, limit=5
            )
            
            # Should return empty (no associations)
            assert recommendations == []
    
    def test_hybrid_with_extreme_user_segments(self, app):
        """Test hybrid recommender with extreme user behaviors"""
        with app.app_context():
            # User with exactly 5 interactions (boundary)
            user = User(email='boundary@test.com')
            user.set_password('password')
            db.session.add(user)
            
            products = Product.query.limit(10).all()
            
            # Add exactly 5 interactions
            for i in range(5):
                interaction = UserInteraction(
                    user_id=user.id,
                    product_id=products[i].id,
                    interaction_type='view'
                )
                db.session.add(interaction)
            
            db.session.commit()
            
            hybrid = HybridRecommender()
            segment = hybrid._determine_user_segment(user.id)
            
            # Should be minimal_data (not new_user)
            assert segment == 'minimal_data'
            
            recommendations = hybrid.get_recommendations(user.id, limit=5)
            assert len(recommendations) <= 5


class TestDataQualityEdgeCases:
    """Test algorithms with poor quality or unusual data"""
    
    def test_recommendations_with_future_timestamps(self, app):
        """Test when interactions have future timestamps"""
        with app.app_context():
            user = User(email='timetravel@test.com')
            user.set_password('password')
            db.session.add(user)
            
            product = Product.query.first()
            
            # Add interaction with future timestamp
            future_interaction = UserInteraction(
                user_id=user.id,
                product_id=product.id,
                interaction_type='view',
                timestamp=datetime.utcnow() + timedelta(days=30)
            )
            db.session.add(future_interaction)
            db.session.commit()
            
            hybrid = HybridRecommender()
            recommendations = hybrid.get_recommendations(user.id, limit=5)
            
            # Should handle gracefully
            assert isinstance(recommendations, list)
    
    def test_recommendations_with_negative_prices(self, app):
        """Test recommendations when products have invalid prices"""
        with app.app_context():
            # Create product with negative price
            weird_product = Product(
                name='Negative Price Product',
                price=-50.0,  # Invalid
                category='Test',
                stock_quantity=100
            )
            db.session.add(weird_product)
            
            # Create product with zero price
            free_product = Product(
                name='Free Product',
                price=0.0,
                category='Test',
                stock_quantity=100
            )
            db.session.add(free_product)
            
            db.session.commit()
            
            products = Product.query.all()
            hybrid = HybridRecommender()
            
            # Should not crash
            recommendations = hybrid.get_recommendations(1, limit=5)
            assert isinstance(recommendations, list)
    
    def test_circular_purchase_patterns(self, app):
        """Test when users have circular purchase patterns"""
        with app.app_context():
            # Create users and products
            users = []
            for i in range(3):
                user = User(email=f'circular{i}@test.com')
                user.set_password('password')
                users.append(user)
                db.session.add(user)
            
            products = Product.query.limit(3).all()
            db.session.commit()
            
            # Create circular pattern: A buys 1,2; B buys 2,3; C buys 3,1
            patterns = [(0, [0, 1]), (1, [1, 2]), (2, [2, 0])]
            
            for user_idx, product_indices in patterns:
                order = Order(
                    user_id=users[user_idx].id,
                    total=100
                )
                db.session.add(order)
                db.session.flush()
                
                for prod_idx in product_indices:
                    order_item = OrderItem(
                        order_id=order.id,
                        product_id=products[prod_idx].id,
                        quantity=1,
                        price=50
                    )
                    db.session.add(order_item)
            
            db.session.commit()
            
            neighbors = AdvancedNeighborsRecommender()
            recommendations = neighbors.get_recommendations(
                users[0].id, products, limit=3
            )
            
            # Should handle circular patterns
            assert isinstance(recommendations, list)


class TestScalabilityEdgeCases:
    """Test algorithms with extreme scale"""
    
    def test_user_with_thousands_of_interactions(self, app):
        """Test recommendations for power user with many interactions"""
        with app.app_context():
            user = User(email='poweruser@test.com')
            user.set_password('password')
            db.session.add(user)
            
            products = Product.query.limit(50).all()
            
            # Add 1000 interactions
            for i in range(1000):
                interaction = UserInteraction(
                    user_id=user.id,
                    product_id=products[i % len(products)].id,
                    interaction_type=['view', 'click', 'purchase'][i % 3],
                    timestamp=datetime.utcnow() - timedelta(hours=i)
                )
                db.session.add(interaction)
                
                if i % 100 == 0:
                    db.session.flush()  # Batch commits
            
            db.session.commit()
            
            # Test performance
            import time
            start = time.time()
            
            hybrid = HybridRecommender()
            recommendations = hybrid.get_recommendations(user.id, limit=10)
            
            duration = time.time() - start
            
            # Should complete in reasonable time
            assert duration < 5.0  # 5 seconds max
            assert len(recommendations) <= 10
    
    def test_empty_database(self, app):
        """Test all algorithms with empty database"""
        with app.app_context():
            # Clear all data
            UserInteraction.query.delete()
            OrderItem.query.delete()
            Order.query.delete()
            Product.query.delete()
            User.query.delete()
            db.session.commit()
            
            # Create single user
            user = User(email='lonely@test.com')
            user.set_password('password')
            db.session.add(user)
            db.session.commit()
            
            # Test all algorithms
            hybrid = HybridRecommender()
            svm = LinearSVMRecommender()
            neighbors = AdvancedNeighborsRecommender()
            cart = ShoppingCartRecommender()
            analytics = AnalyticsEngine()
            
            # All should handle empty data gracefully
            assert hybrid.get_recommendations(user.id, limit=5) == []
            assert svm.get_recommendations(user.id, [], limit=5) == []
            assert neighbors.get_recommendations(user.id, [], limit=5) == []
            assert cart.get_cart_recommendations([], [], limit=5) == []
            assert analytics.get_best_sellers(limit=5) == []
            assert analytics.get_trending_products(limit=5) == []
    
    def test_all_products_out_of_stock(self, app, sample_users, sample_products):
        """Test recommendations when entire catalog is out of stock"""
        with app.app_context():
            # Set all products to out of stock
            Product.query.update({Product.stock_quantity: 0})
            db.session.commit()
            
            hybrid = HybridRecommender()
            recommendations = hybrid.get_recommendations(sample_users[0].id, limit=10)
            
            # Should return empty list (no products in stock)
            assert recommendations == []


class TestConcurrencyEdgeCases:
    """Test concurrent access scenarios"""
    
    def test_simultaneous_offer_generation(self, app):
        """Test when multiple processes try to generate offers simultaneously"""
        with app.app_context():
            from eshop.offers import OfferGenerator
            
            user = User.query.first()
            offer_gen = OfferGenerator()
            
            # Generate offers twice (simulating race condition)
            offers1 = offer_gen.generate_offers_for_user(user.id, num_offers=4)
            offers2 = offer_gen.generate_offers_for_user(user.id, num_offers=4)
            
            # Should not create duplicates due to unique constraint
            all_offers = PersonalizedOffer.query.filter_by(user_id=user.id).all()
            
            # Check no duplicate product offers
            product_ids = [offer.product_id for offer in all_offers]
            assert len(product_ids) == len(set(product_ids))
    
    def test_concurrent_analytics_update(self, app):
        """Test concurrent analytics updates"""
        with app.app_context():
            analytics1 = AnalyticsEngine()
            analytics2 = AnalyticsEngine()
            
            # Both try to update simultaneously
            analytics1.update_analytics()
            analytics2.update_analytics()
            
            # Should not corrupt data
            best_sellers = analytics1.get_best_sellers(limit=10)
            assert isinstance(best_sellers, list)