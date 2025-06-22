import pytest
from unittest.mock import Mock, patch
from collections import defaultdict
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from eshop.models import UserInteraction
from eshop.ml_recommenders import AdvancedNeighborsRecommender


class TestAdvancedNeighborsRecommender:
    """Test suite for Advanced Neighbors collaborative filtering algorithm"""
    
    @pytest.fixture
    def recommender(self):
        """Create an AdvancedNeighborsRecommender instance"""
        return AdvancedNeighborsRecommender(min_common_items=2, similarity_threshold=0.1)
    
    @pytest.fixture
    def sample_products(self):
        """Create sample products for testing"""
        products = []
        for i in range(10):
            product = Mock()
            product.id = i + 1
            product.name = f"Product {i + 1}"
            products.append(product)
        return products
    
    def test_get_user_item_interactions(self, recommender):
        """Test extraction of user-item interaction scores"""
        user_id = 1
        
        # Mock interaction data
        mock_interactions = [
            (1, 'view', 3),      # Product 1: 3 views
            (1, 'click', 2),     # Product 1: 2 clicks
            (2, 'purchase', 1),  # Product 2: 1 purchase
            (3, 'view', 5),      # Product 3: 5 views
            (3, 'add_to_cart', 1)  # Product 3: 1 cart addition
        ]
        
        with patch('eshop.models.db.session.query') as mock_query:
            mock_query.return_value.filter.return_value.group_by.return_value.all.return_value = mock_interactions
            
            item_scores = recommender._get_user_item_interactions(user_id)
            
            # Check calculated scores
            # Product 1: 3*1 + 2*2 = 7
            assert item_scores[1] == 7.0
            # Product 2: 1*5 = 5
            assert item_scores[2] == 5.0
            # Product 3: 5*1 + 1*3 = 8
            assert item_scores[3] == 8.0
    
    def test_calculate_user_similarity(self, recommender):
        """Test user similarity calculation"""
        # User 1 items and scores
        user1_items = {1: 5.0, 2: 3.0, 3: 4.0, 4: 2.0}
        # User 2 items and scores
        user2_items = {1: 4.0, 2: 5.0, 5: 3.0, 6: 2.0}
        # Common items
        common_items = {1, 2}
        
        similarity = recommender._calculate_user_similarity(
            user1_items, user2_items, common_items
        )
        
        # Should calculate cosine similarity on common items
        # For items 1,2: user1=[5,3], user2=[4,5]
        # Cosine similarity = (5*4 + 3*5) / (sqrt(25+9) * sqrt(16+25))
        # = 35 / (sqrt(34) * sqrt(41))
        assert 0.0 <= similarity <= 1.0
        assert similarity > 0.9  # Should be high similarity
    
    def test_calculate_user_similarity_no_common_items(self, recommender):
        """Test similarity when users have no common items"""
        user1_items = {1: 5.0, 2: 3.0}
        user2_items = {3: 4.0, 4: 5.0}
        common_items = set()
        
        similarity = recommender._calculate_user_similarity(
            user1_items, user2_items, common_items
        )
        
        assert similarity == 0.0
    
    def test_find_similar_users(self, recommender):
        """Test finding similar users"""
        user_id = 1
        user_items = {1: 5.0, 2: 3.0, 3: 4.0}
        
        # Mock common users query
        mock_common_users = [
            (2, 1),  # User 2 interacted with product 1
            (2, 2),  # User 2 interacted with product 2
            (3, 1),  # User 3 interacted with product 1
            (3, 3),  # User 3 interacted with product 3
            (4, 1),  # User 4 interacted with product 1
        ]
        
        with patch('eshop.models.db.session.query') as mock_query:
            mock_query.return_value.filter.return_value.distinct.return_value.all.return_value = mock_common_users
            
            # Mock get_user_item_interactions for other users
            def mock_get_interactions(uid):
                if uid == 2:
                    return {1: 4.0, 2: 5.0, 4: 2.0}
                elif uid == 3:
                    return {1: 3.0, 3: 5.0, 5: 1.0}
                elif uid == 4:
                    return {1: 2.0, 6: 3.0}
                return {}
            
            with patch.object(recommender, '_get_user_item_interactions', side_effect=mock_get_interactions):
                similar_users = recommender._find_similar_users(user_id, user_items)
                
                # Should find users 2 and 3 (they have >= 2 common items)
                # User 4 should be excluded (only 1 common item)
                assert len(similar_users) == 2
                assert all(uid in [2, 3] for uid, _ in similar_users)
                
                # Check that users are sorted by similarity
                similarities = [sim for _, sim in similar_users]
                assert similarities == sorted(similarities, reverse=True)
    
    def test_get_neighbor_recommendations(self, recommender, sample_products):
        """Test getting recommendations from neighbors"""
        user_id = 1
        similar_users = [(2, 0.9), (3, 0.7), (4, 0.5)]
        
        # Mock user's existing items
        with patch.object(recommender, '_get_user_item_interactions') as mock_get_items:
            # User 1 already has products 1, 2
            def mock_interactions(uid):
                if uid == 1:
                    return {1: 5.0, 2: 3.0}
                elif uid == 2:
                    return {1: 4.0, 3: 5.0, 4: 3.0}  # Recommends 3, 4
                elif uid == 3:
                    return {2: 3.0, 3: 4.0, 5: 5.0}  # Recommends 3, 5
                elif uid == 4:
                    return {1: 2.0, 4: 4.0, 5: 2.0}  # Recommends 4, 5
                return {}
            
            mock_get_items.side_effect = mock_interactions
            
            recommendations = recommender._get_neighbor_recommendations(
                user_id, similar_users, sample_products[:6], limit=3
            )
            
            # Should recommend products 3, 4, 5 (not 1, 2 which user already has)
            assert len(recommendations) <= 3
            recommended_ids = [p.id for p in recommendations]
            assert 1 not in recommended_ids  # User already has this
            assert 2 not in recommended_ids  # User already has this
            
            # Check that products have scores attached
            assert all(hasattr(p, '_neighbor_score') for p in recommendations)
    
    def test_cold_start_handling(self, recommender, sample_products):
        """Test handling of users with insufficient interactions"""
        user_id = 1
        
        # Mock user with too few interactions
        with patch.object(recommender, '_get_user_item_interactions', return_value={1: 1.0}):
            recommendations = recommender.get_recommendations(user_id, sample_products, limit=5)
            
            # Should return empty list for users with < 3 interactions
            assert recommendations == []
    
    def test_no_similar_users(self, recommender, sample_products):
        """Test when no similar users are found"""
        user_id = 1
        
        with patch.object(recommender, '_get_user_item_interactions', return_value={1: 5.0, 2: 3.0, 3: 4.0}):
            with patch.object(recommender, '_find_similar_users', return_value=[]):
                recommendations = recommender.get_recommendations(user_id, sample_products, limit=5)
                
                # Should return empty list when no similar users found
                assert recommendations == []
    
    def test_similarity_threshold(self, recommender):
        """Test that similarity threshold is respected"""
        user_id = 1
        user_items = {1: 5.0, 2: 3.0}
        
        # Create recommender with high threshold
        high_threshold_recommender = AdvancedNeighborsRecommender(
            min_common_items=2, 
            similarity_threshold=0.9
        )
        
        # Mock data
        mock_common_users = [
            (2, 1), (2, 2),  # User 2 has 2 common items
            (3, 1), (3, 2),  # User 3 has 2 common items
        ]
        
        with patch('eshop.models.db.session.query') as mock_query:
            mock_query.return_value.filter.return_value.distinct.return_value.all.return_value = mock_common_users
            
            # Mock interactions with low similarity
            def mock_get_interactions(uid):
                if uid == 2:
                    return {1: 1.0, 2: 1.0}  # Very different scores
                elif uid == 3:
                    return {1: 5.0, 2: 3.0}  # Same scores (high similarity)
                return {}
            
            with patch.object(high_threshold_recommender, '_get_user_item_interactions', 
                            side_effect=mock_get_interactions):
                similar_users = high_threshold_recommender._find_similar_users(user_id, user_items)
                
                # Only user 3 should pass the high threshold
                assert len(similar_users) == 1
                assert similar_users[0][0] == 3