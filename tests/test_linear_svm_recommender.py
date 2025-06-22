import pytest
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from eshop.models import db, User, Product, UserInteraction, Order, OrderItem
from eshop.ml_recommenders import LinearSVMRecommender


class TestLinearSVMRecommender:
    """Test suite for Linear SVM recommendation algorithm"""
    
    @pytest.fixture
    def recommender(self):
        """Create a LinearSVMRecommender instance"""
        return LinearSVMRecommender()
    
    @pytest.fixture
    def sample_user(self):
        """Create a sample user for testing"""
        user = Mock(spec=User)
        user.id = 1
        user.created_at = datetime.utcnow() - timedelta(days=30)
        return user
    
    @pytest.fixture
    def sample_products(self):
        """Create sample products for testing"""
        products = []
        categories = ['Electronics', 'Books', 'Clothing', 'Home']
        for i in range(20):
            product = Mock(spec=Product)
            product.id = i + 1
            product.name = f"Product {i + 1}"
            product.price = 10.0 + (i * 5)
            product.category = categories[i % 4]
            product.brand = f"Brand {i % 3}"
            product.tags = f"tag{i % 2},tag{i % 3}"
            products.append(product)
        return products
    
    def test_feature_extraction_for_user(self, recommender, sample_user, sample_products):
        """Test feature extraction from user interactions"""
        # Create mock interactions
        interactions = []
        for i in range(5):
            interaction = Mock(spec=UserInteraction)
            interaction.user_id = sample_user.id
            interaction.product_id = sample_products[i].id
            interaction.product = sample_products[i]
            interaction.interaction_type = ['view', 'click', 'purchase'][i % 3]
            interaction.timestamp = datetime.utcnow() - timedelta(days=i)
            interactions.append(interaction)
        
        # Extract features
        features = recommender._extract_user_features(sample_user, interactions)
        
        # Assertions
        assert 'avg_price' in features
        assert 'category_preferences' in features
        assert 'brand_preferences' in features
        assert 'interaction_recency' in features
        assert 'purchase_frequency' in features
        
        # Check feature values
        assert features['avg_price'] > 0
        assert isinstance(features['category_preferences'], dict)
        assert len(features['category_preferences']) > 0
        assert features['interaction_recency'] >= 0
    
    def test_feature_extraction_for_products(self, recommender, sample_products):
        """Test feature extraction for products"""
        product = sample_products[0]
        
        features = recommender._extract_product_features(product)
        
        # Assertions
        assert 'price' in features
        assert 'category' in features
        assert 'brand' in features
        assert 'tags' in features
        
        # Check feature values
        assert features['price'] == product.price
        assert features['category'] == product.category
        assert features['brand'] == product.brand
        assert isinstance(features['tags'], list)
    
    def test_create_feature_vector(self, recommender):
        """Test feature vector creation for SVM"""
        user_features = {
            'avg_price': 50.0,
            'category_preferences': {'Electronics': 0.6, 'Books': 0.4},
            'brand_preferences': {'Brand1': 0.7, 'Brand2': 0.3},
            'interaction_recency': 2.5,
            'purchase_frequency': 0.8
        }
        
        product_features = {
            'price': 45.0,
            'category': 'Electronics',
            'brand': 'Brand1',
            'tags': ['tag1', 'tag2']
        }
        
        vector = recommender._create_feature_vector(user_features, product_features)
        
        # Assertions
        assert isinstance(vector, np.ndarray)
        assert vector.shape[0] > 0  # Should have multiple features
        assert not np.any(np.isnan(vector))  # No NaN values
        assert not np.any(np.isinf(vector))  # No infinite values
    
    def test_train_model_with_insufficient_data(self, recommender, sample_user):
        """Test model training with insufficient data"""
        # Mock query results with too few interactions
        with patch('eshop.models.UserInteraction.query') as mock_query:
            mock_query.filter_by.return_value.count.return_value = 3
            
            model = recommender._train_user_model(sample_user.id)
            
            # Should return None when insufficient data
            assert model is None
    
    def test_train_model_with_sufficient_data(self, recommender, sample_user, sample_products):
        """Test model training with sufficient interaction data"""
        # Create mock interactions
        interactions = []
        for i in range(20):
            interaction = Mock(spec=UserInteraction)
            interaction.user_id = sample_user.id
            interaction.product_id = sample_products[i % 10].id
            interaction.product = sample_products[i % 10]
            interaction.interaction_type = ['view', 'click', 'purchase'][i % 3]
            interaction.timestamp = datetime.utcnow() - timedelta(days=i)
            interactions.append(interaction)
        
        # Mock the database queries
        with patch.object(recommender, '_get_user_interactions', return_value=interactions):
            with patch.object(recommender, '_get_user_purchases', return_value=[p.id for p in sample_products[:5]]):
                model = recommender._train_user_model(sample_user.id)
                
                # Assertions
                assert model is not None
                assert hasattr(model, 'predict')
                assert hasattr(model, 'decision_function')
    
    def test_predict_preferences(self, recommender, sample_user, sample_products):
        """Test preference prediction for products"""
        # Create a mock trained model
        mock_model = Mock()
        mock_model.decision_function.return_value = np.array([0.8, -0.2, 0.5, 0.9, -0.5])
        
        with patch.object(recommender, '_train_user_model', return_value=mock_model):
            # Get top 3 recommendations
            recommendations = recommender.get_recommendations(sample_user.id, sample_products[:5], limit=3)
            
            # Assertions
            assert len(recommendations) == 3
            # Should be sorted by score (descending)
            assert all(hasattr(p, '_svm_score') for p in recommendations)
            scores = [p._svm_score for p in recommendations]
            assert scores == sorted(scores, reverse=True)
    
    def test_cold_start_handling(self, recommender, sample_user, sample_products):
        """Test handling of new users with no interactions"""
        # Mock no interactions
        with patch('eshop.models.UserInteraction.query') as mock_query:
            mock_query.filter_by.return_value.count.return_value = 0
            
            recommendations = recommender.get_recommendations(sample_user.id, sample_products, limit=5)
            
            # Should return empty list for cold start users
            assert recommendations == []
    
    def test_feature_normalization(self, recommender):
        """Test that features are properly normalized"""
        user_features = {
            'avg_price': 1000.0,  # High price
            'category_preferences': {'Electronics': 1.0},
            'brand_preferences': {'Brand1': 1.0},
            'interaction_recency': 30.0,  # Old interaction
            'purchase_frequency': 0.1  # Low frequency
        }
        
        product_features = {
            'price': 50.0,  # Low price
            'category': 'Electronics',
            'brand': 'Brand1',
            'tags': []
        }
        
        vector = recommender._create_feature_vector(user_features, product_features)
        
        # All values should be normalized between -1 and 1 (approximately)
        assert np.all(vector >= -2.0)
        assert np.all(vector <= 2.0)
    
    def test_category_similarity_calculation(self, recommender):
        """Test category similarity calculation"""
        user_features = {
            'category_preferences': {'Electronics': 0.6, 'Books': 0.3, 'Clothing': 0.1}
        }
        
        # High similarity - matching top category
        similarity1 = recommender._calculate_category_similarity(user_features, 'Electronics')
        # Medium similarity - matching secondary category
        similarity2 = recommender._calculate_category_similarity(user_features, 'Books')
        # Low similarity - non-preferred category
        similarity3 = recommender._calculate_category_similarity(user_features, 'Home')
        
        assert similarity1 > similarity2
        assert similarity2 > similarity3
        assert similarity3 >= 0  # Should still be non-negative