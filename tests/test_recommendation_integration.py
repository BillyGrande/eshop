"""
Integration tests for the complete recommendation system
"""

import pytest
from unittest.mock import patch
from eshop.recommender import Recommender
from eshop.hybrid_recommender import HybridRecommender
from eshop.offers import OfferGenerator
from eshop.models import UserInteraction, GuestInteraction, PersonalizedOffer
from datetime import datetime, timedelta


class TestRecommendationIntegration:
    """Integration tests for the full recommendation pipeline"""
    
    def test_guest_initial_recommendations(self, app, client, sample_products, analytics_engine):
        """Test recommendations for new guest users"""
        with app.app_context():
            # Mock session ID
            with patch('eshop.session_manager.SessionManager.get_or_create_session_id', 
                      return_value='guest-123'):
                response = client.get('/')
                assert response.status_code == 200
                
                # Should show mix of best sellers and trending
                # Check that analytics engine has data
                best_sellers = analytics_engine.get_best_sellers(limit=2)
                trending = analytics_engine.get_trending_products(limit=2)
                
                assert len(best_sellers) > 0
                assert len(trending) > 0
    
    def test_guest_cold_start_after_interactions(self, app, sample_products, mock_session_id):
        """Test cold start recommendations for guests after 3+ interactions"""
        with app.app_context():
            # Create guest interactions
            for i in range(4):
                interaction = GuestInteraction(
                    session_id=mock_session_id,
                    product_id=sample_products[i].id,
                    interaction_type='view',
                    timestamp=datetime.utcnow() - timedelta(minutes=i)
                )
                app.db.session.add(interaction)
            app.db.session.commit()
            
            # Get recommendations
            recommendations = Recommender.get_recommendations_for_guest(mock_session_id, limit=4)
            
            # Should use cold start algorithm
            assert len(recommendations) <= 4
            # Should not include already viewed products
            viewed_ids = [sample_products[i].id for i in range(4)]
            for rec in recommendations:
                assert rec.id not in viewed_ids
    
    def test_new_user_recommendations(self, app, sample_users, sample_products, analytics_engine):
        """Test recommendations for new authenticated users"""
        with app.app_context():
            new_user = sample_users[0]  # User with no interactions
            
            recommendations = Recommender.get_recommendations_for_user(new_user.id, limit=4)
            
            # Should get best sellers + trending
            assert len(recommendations) <= 4
            assert all(hasattr(r, 'discount_percentage') for r in recommendations)
    
    def test_minimal_data_user_recommendations(self, app, sample_users, sample_interactions):
        """Test recommendations for users with minimal data"""
        with app.app_context():
            casual_user = sample_users[1]  # User with 8 interactions
            
            recommendations = Recommender.get_recommendations_for_user(casual_user.id, limit=4)
            
            # Should use cold start algorithm
            assert len(recommendations) <= 4
    
    def test_established_user_hybrid_recommendations(self, app, sample_users, sample_interactions, sample_orders):
        """Test hybrid recommendations for established users"""
        with app.app_context():
            vip_user = sample_users[3]  # User with 50+ interactions and purchases
            
            hybrid = HybridRecommender()
            recommendations = hybrid.get_recommendations(vip_user.id, limit=10)
            
            # Should use all algorithms
            assert len(recommendations) <= 10
            # Check that products have hybrid scores
            for rec in recommendations:
                assert hasattr(rec, '_hybrid_score')
                assert hasattr(rec, '_hybrid_sources')
                assert len(rec._hybrid_sources) > 0
    
    def test_personalized_offers_generation(self, app, sample_users, sample_interactions):
        """Test personalized offer generation for users"""
        with app.app_context():
            user = sample_users[2]  # Active user
            
            offer_gen = OfferGenerator()
            offers = offer_gen.generate_offers_for_user(user.id, num_offers=4)
            
            assert len(offers) <= 4
            for offer in offers:
                assert offer.user_id == user.id
                assert offer.discount_percentage == 10.0
                assert offer.expires_at > datetime.utcnow()
    
    def test_offer_application_in_checkout(self, app, authenticated_client, sample_products):
        """Test that offers are applied during checkout"""
        with app.app_context():
            # Add product to cart
            product = sample_products[0]
            authenticated_client.post('/cart/add', json={'product_id': product.id})
            
            # Generate offer for this product
            from flask_login import current_user
            offer_gen = OfferGenerator()
            # Note: In real scenario, offers would be pre-generated
            
            # Go to checkout
            response = authenticated_client.get('/checkout')
            assert response.status_code == 200
    
    def test_recommendation_diversity(self, app, sample_users, sample_products, sample_interactions):
        """Test that recommendations include diverse categories"""
        with app.app_context():
            user = sample_users[2]
            
            hybrid = HybridRecommender()
            recommendations = hybrid.get_recommendations(user.id, limit=8)
            
            # Check category diversity
            categories = [r.category for r in recommendations]
            unique_categories = set(categories)
            
            # Should have at least 2 different categories in top 8
            assert len(unique_categories) >= 2
    
    def test_algorithm_weight_determination(self, app, sample_users):
        """Test correct algorithm weights for different user segments"""
        with app.app_context():
            hybrid = HybridRecommender()
            
            # New user
            weights_new = hybrid.get_algorithm_weights(sample_users[0].id)
            assert weights_new['segment'] == 'new_user'
            assert weights_new['weights']['best_sellers'] == 0.5
            assert weights_new['weights']['trending'] == 0.5
            
            # Minimal data user
            weights_minimal = hybrid.get_algorithm_weights(sample_users[1].id)
            assert weights_minimal['segment'] == 'minimal_data'
            assert weights_minimal['weights']['cold_start'] == 1.0
            
            # Established user
            weights_established = hybrid.get_algorithm_weights(sample_users[3].id)
            assert weights_established['segment'] == 'established_user'
            assert weights_established['weights']['linear_svm'] == 0.3
            assert weights_established['weights']['neighbors'] == 0.3


class TestRecommendationAccuracy:
    """Tests for recommendation accuracy and quality metrics"""
    
    def test_purchase_prediction_accuracy(self, app, sample_users, sample_interactions):
        """Test if recommendations match actual purchase patterns"""
        with app.app_context():
            user = sample_users[3]  # VIP user with purchase history
            
            # Get user's purchased products
            purchased_products = set()
            for interaction in sample_interactions:
                if (interaction.user_id == user.id and 
                    interaction.interaction_type == 'purchase'):
                    purchased_products.add(interaction.product_id)
            
            # Get recommendations
            recommendations = Recommender.get_recommendations_for_user(user.id, limit=20)
            
            # Recommendations should not include already purchased items
            recommended_ids = [r.id for r in recommendations]
            assert not any(pid in purchased_products for pid in recommended_ids)
    
    def test_cold_start_relevance(self, app, sample_users, sample_products):
        """Test if cold start recommendations are relevant to user preferences"""
        with app.app_context():
            user = sample_users[1]
            
            # Create specific interactions to test preference learning
            # User views only Electronics products
            electronics_products = [p for p in sample_products if p.category == 'Electronics'][:5]
            
            for product in electronics_products:
                interaction = UserInteraction(
                    user_id=user.id,
                    product_id=product.id,
                    interaction_type='view',
                    timestamp=datetime.utcnow()
                )
                app.db.session.add(interaction)
            app.db.session.commit()
            
            # Get recommendations
            recommendations = Recommender.get_cold_start_recommendations(user.id, limit=4)
            
            # Most recommendations should be Electronics
            electronics_count = sum(1 for r in recommendations if r.category == 'Electronics')
            assert electronics_count >= len(recommendations) // 2