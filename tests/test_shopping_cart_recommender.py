import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from eshop.models import db, OrderItem, CartItem
from eshop.ml_recommenders import ShoppingCartRecommender


class TestShoppingCartRecommender:
    """Test suite for Shopping Cart based recommendation algorithm"""
    
    @pytest.fixture
    def recommender(self):
        """Create a ShoppingCartRecommender instance"""
        return ShoppingCartRecommender()
    
    @pytest.fixture
    def sample_products(self):
        """Create sample products for testing"""
        products = []
        categories = ['Electronics', 'Books', 'Clothing', 'Home']
        for i in range(12):
            product = Mock()
            product.id = i + 1
            product.name = f"Product {i + 1}"
            product.category = categories[i % 4]
            product.price = 20.0 + (i * 10)
            products.append(product)
        return products
    
    def test_get_cart_associations(self, recommender):
        """Test extraction of product associations from historical orders"""
        # Mock order items data
        mock_associations = [
            # Order 1: Products 1, 2, 3 bought together
            (1, [1, 2, 3]),
            # Order 2: Products 2, 4 bought together
            (2, [2, 4]),
            # Order 3: Products 1, 3, 5 bought together
            (3, [1, 3, 5]),
            # Order 4: Products 2, 3, 4 bought together
            (4, [2, 3, 4])
        ]
        
        associations = recommender._build_association_matrix(mock_associations)
        
        # Check co-occurrence counts
        # Products 1 and 3 appear together in 2 orders
        assert associations.get((1, 3), 0) == 2
        assert associations.get((3, 1), 0) == 2
        
        # Products 2 and 4 appear together in 2 orders
        assert associations.get((2, 4), 0) == 2
        assert associations.get((4, 2), 0) == 2
        
        # Products 1 and 4 never appear together
        assert associations.get((1, 4), 0) == 0
    
    def test_calculate_association_score(self, recommender):
        """Test association score calculation with confidence and lift"""
        # Mock association data
        associations = {
            (1, 2): 10,  # Products 1 and 2 bought together 10 times
            (1, 3): 5,   # Products 1 and 3 bought together 5 times
            (2, 1): 10,
            (3, 1): 5
        }
        
        product_counts = {
            1: 20,  # Product 1 appears in 20 orders
            2: 15,  # Product 2 appears in 15 orders
            3: 8    # Product 3 appears in 8 orders
        }
        
        total_orders = 100
        
        # Calculate scores
        score_1_2 = recommender._calculate_association_score(
            1, 2, associations, product_counts, total_orders
        )
        score_1_3 = recommender._calculate_association_score(
            1, 3, associations, product_counts, total_orders
        )
        
        # Product 1->2 should have higher confidence than 1->3
        # Confidence(1->2) = 10/20 = 0.5
        # Confidence(1->3) = 5/20 = 0.25
        assert score_1_2 > score_1_3
    
    def test_get_recommendations_for_cart(self, recommender, sample_products):
        """Test getting recommendations based on current cart items"""
        cart_product_ids = [1, 3, 5]  # Current cart has products 1, 3, 5
        
        # Mock association data
        mock_associations = {
            (1, 2): 8, (1, 4): 5, (1, 6): 3,
            (3, 2): 6, (3, 4): 7, (3, 7): 4,
            (5, 8): 5, (5, 9): 3, (5, 10): 2
        }
        
        mock_product_counts = {i: 10 + i for i in range(1, 11)}
        
        with patch.object(recommender, '_get_association_data', 
                         return_value=(mock_associations, mock_product_counts, 100)):
            recommendations = recommender.get_cart_recommendations(
                cart_product_ids, 
                sample_products,
                limit=5
            )
            
            # Should not recommend products already in cart
            recommended_ids = [p.id for p in recommendations]
            assert 1 not in recommended_ids
            assert 3 not in recommended_ids
            assert 5 not in recommended_ids
            
            # Should have association scores
            assert all(hasattr(p, '_cart_association_score') for p in recommendations)
            
            # Scores should be sorted in descending order
            scores = [p._cart_association_score for p in recommendations]
            assert scores == sorted(scores, reverse=True)
    
    def test_get_complementary_products(self, recommender, sample_products):
        """Test finding complementary products for a single item"""
        product_id = 1
        
        # Mock data showing product 1 is often bought with 2, 3, 4
        mock_associations = {
            (1, 2): 10,
            (1, 3): 8,
            (1, 4): 6,
            (1, 5): 2
        }
        
        mock_product_counts = {1: 15, 2: 12, 3: 10, 4: 8, 5: 5}
        
        with patch.object(recommender, '_get_association_data',
                         return_value=(mock_associations, mock_product_counts, 50)):
            complementary = recommender.get_complementary_products(
                product_id,
                sample_products[:6],
                limit=3
            )
            
            # Should return top 3 associated products
            assert len(complementary) == 3
            
            # Product 2 should be first (highest association)
            assert complementary[0].id == 2
    
    def test_abandoned_cart_recommendations(self, recommender, sample_products):
        """Test recommendations for abandoned cart recovery"""
        user_id = 1
        abandoned_cart_items = [2, 4, 6]
        
        # Mock user's purchase history
        mock_purchase_history = [1, 3, 5, 7]
        
        # Mock associations
        mock_associations = {
            # User's past purchases often lead to products 2, 8
            (1, 2): 5, (1, 8): 4,
            (3, 2): 6, (3, 8): 5,
            # Abandoned items associate with products 8, 9, 10
            (2, 8): 7, (2, 9): 5,
            (4, 9): 6, (4, 10): 4
        }
        
        with patch.object(recommender, '_get_user_purchase_history',
                         return_value=mock_purchase_history):
            with patch.object(recommender, '_get_association_data',
                             return_value=(mock_associations, {i: 10 for i in range(1, 11)}, 100)):
                recommendations = recommender.get_abandoned_cart_recovery(
                    user_id,
                    abandoned_cart_items,
                    sample_products,
                    limit=4
                )
                
                # Should prioritize products associated with both history and abandoned items
                assert len(recommendations) <= 4
                assert all(hasattr(p, '_recovery_score') for p in recommendations)
    
    def test_empty_cart_handling(self, recommender, sample_products):
        """Test handling of empty cart"""
        recommendations = recommender.get_cart_recommendations(
            [],  # Empty cart
            sample_products,
            limit=5
        )
        
        # Should return empty list for empty cart
        assert recommendations == []
    
    def test_category_diversity(self, recommender, sample_products):
        """Test that recommendations include category diversity"""
        cart_product_ids = [1, 5, 9]  # All Electronics (indices 0, 4, 8)
        
        # Mock associations that include different categories
        mock_associations = {
            (1, 2): 8,   # Books
            (1, 3): 7,   # Clothing
            (1, 4): 6,   # Home
            (5, 6): 5,   # Books
            (5, 7): 4,   # Clothing
            (9, 10): 5,  # Books
            (9, 11): 4   # Clothing
        }
        
        with patch.object(recommender, '_get_association_data',
                         return_value=(mock_associations, {i: 10 for i in range(1, 12)}, 100)):
            recommendations = recommender.get_cart_recommendations(
                cart_product_ids,
                sample_products,
                limit=6,
                diversify=True
            )
            
            # Check category diversity
            categories = [p.category for p in recommendations]
            unique_categories = set(categories)
            
            # Should have products from multiple categories
            assert len(unique_categories) > 1
    
    def test_time_decay_in_associations(self, recommender):
        """Test that recent associations are weighted more heavily"""
        # Mock order data with timestamps
        recent_date = datetime.utcnow() - timedelta(days=7)
        old_date = datetime.utcnow() - timedelta(days=90)
        
        mock_orders = [
            # Recent order: strong association
            (1, [1, 2], recent_date),
            # Old order: same products but should have less weight
            (2, [1, 2], old_date),
            # Recent order: different products
            (3, [3, 4], recent_date)
        ]
        
        associations = recommender._build_association_matrix_with_time_decay(mock_orders)
        
        # Recent associations should have higher weight
        # Both orders have products 1,2 but recent one should contribute more
        assert associations[(1, 2)] > 1.0  # More than just count due to recency
    
    def test_min_support_threshold(self, recommender):
        """Test that associations below minimum support are filtered"""
        recommender.min_support = 3  # Require at least 3 co-occurrences
        
        mock_associations = {
            (1, 2): 5,   # Above threshold
            (1, 3): 2,   # Below threshold
            (2, 4): 10,  # Above threshold
            (3, 4): 1    # Below threshold
        }
        
        filtered = recommender._filter_associations_by_support(mock_associations)
        
        # Only associations above threshold should remain
        assert (1, 2) in filtered
        assert (2, 4) in filtered
        assert (1, 3) not in filtered
        assert (3, 4) not in filtered