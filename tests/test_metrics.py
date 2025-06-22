"""
Tests for recommendation system accuracy metrics
"""

import pytest
from tests.mock_data_generator import RecommendationMetrics, MockDataGenerator
from eshop.hybrid_recommender import HybridRecommender
from eshop.models import UserInteraction, OrderItem, Order


class TestRecommendationMetrics:
    """Test recommendation quality metrics"""
    
    def test_precision_at_k(self, app, sample_users, sample_products, sample_orders):
        """Test precision@k calculation"""
        with app.app_context():
            user = sample_users[2]  # Active user
            
            # Get user's purchased products as relevant items
            relevant_items = set()
            for order in sample_orders:
                if order.user_id == user.id:
                    for item in order.items:
                        relevant_items.add(item.product_id)
            
            # Get recommendations
            hybrid = HybridRecommender()
            recommendations = hybrid.get_recommendations(user.id, limit=20)
            
            # Calculate precision at different k values
            precision_5 = RecommendationMetrics.calculate_precision_at_k(
                recommendations, relevant_items, k=5
            )
            precision_10 = RecommendationMetrics.calculate_precision_at_k(
                recommendations, relevant_items, k=10
            )
            
            print(f"\nPrecision@5: {precision_5:.3f}")
            print(f"Precision@10: {precision_10:.3f}")
            
            # Precision should be between 0 and 1
            assert 0 <= precision_5 <= 1
            assert 0 <= precision_10 <= 1
    
    def test_recall_at_k(self, app, sample_users, sample_products, sample_orders):
        """Test recall@k calculation"""
        with app.app_context():
            user = sample_users[3]  # VIP user
            
            # Get user's interacted products as relevant items
            interactions = UserInteraction.query.filter_by(
                user_id=user.id,
                interaction_type='purchase'
            ).all()
            relevant_items = {i.product_id for i in interactions}
            
            if relevant_items:
                # Get recommendations
                hybrid = HybridRecommender()
                recommendations = hybrid.get_recommendations(user.id, limit=20)
                
                # Calculate recall
                recall_10 = RecommendationMetrics.calculate_recall_at_k(
                    recommendations, relevant_items, k=10
                )
                recall_20 = RecommendationMetrics.calculate_recall_at_k(
                    recommendations, relevant_items, k=20
                )
                
                print(f"\nRecall@10: {recall_10:.3f}")
                print(f"Recall@20: {recall_20:.3f}")
                
                assert 0 <= recall_10 <= 1
                assert 0 <= recall_20 <= 1
                assert recall_20 >= recall_10  # Recall should increase with k
    
    def test_diversity_metric(self, app, sample_users, sample_products):
        """Test recommendation diversity calculation"""
        with app.app_context():
            user = sample_users[2]
            
            hybrid = HybridRecommender()
            recommendations = hybrid.get_recommendations(user.id, limit=10)
            
            diversity = RecommendationMetrics.calculate_diversity(recommendations)
            
            print(f"\nDiversity score: {diversity:.3f}")
            
            # Diversity should be between 0 and 1
            assert 0 <= diversity <= 1
            
            # With 10 recommendations and multiple categories, 
            # diversity should be reasonable
            if len(recommendations) >= 5:
                assert diversity > 0.1  # At least some diversity
    
    def test_coverage_metric(self, app, sample_users, sample_products):
        """Test catalog coverage metric"""
        with app.app_context():
            # Get recommendations for multiple users
            all_recommendations = []
            hybrid = HybridRecommender()
            
            for user in sample_users:
                recs = hybrid.get_recommendations(user.id, limit=10)
                all_recommendations.extend(recs)
            
            coverage = RecommendationMetrics.calculate_coverage(
                all_recommendations, 
                sample_products
            )
            
            print(f"\nCatalog coverage: {coverage:.3f}")
            
            # Coverage should be between 0 and 1
            assert 0 <= coverage <= 1
            
            # With multiple users, should cover decent portion of catalog
            assert coverage > 0.05  # At least 5% coverage


class TestAccuracyOverTime:
    """Test how recommendation accuracy changes with more user data"""
    
    def test_accuracy_improvement_with_interactions(self, app):
        """Test if recommendations improve as user interacts more"""
        with app.app_context():
            # Create test user and products
            generator = MockDataGenerator()
            users = generator.generate_users(1)
            user = users[0]
            products = generator.generate_products(50)
            
            # Categories user will prefer
            preferred_category = 'Electronics'
            preferred_products = [p for p in products if p.category == preferred_category]
            other_products = [p for p in products if p.category != preferred_category]
            
            # Initial recommendations (no data)
            hybrid = HybridRecommender()
            initial_recs = hybrid.get_recommendations(user.id, limit=10)
            
            # Add interactions gradually
            interaction_counts = [5, 10, 20, 30]
            diversity_scores = []
            
            for count in interaction_counts:
                # Add more interactions with preferred category
                for i in range(count - len(UserInteraction.query.filter_by(user_id=user.id).all())):
                    # 70% interactions with preferred category
                    if i % 10 < 7:
                        product = preferred_products[i % len(preferred_products)]
                    else:
                        product = other_products[i % len(other_products)]
                    
                    interaction = UserInteraction(
                        user_id=user.id,
                        product_id=product.id,
                        interaction_type='view' if i % 3 else 'click'
                    )
                    app.db.session.add(interaction)
                
                app.db.session.commit()
                
                # Get new recommendations
                recs = hybrid.get_recommendations(user.id, limit=10)
                
                # Calculate how many are from preferred category
                preferred_count = sum(1 for r in recs if r.category == preferred_category)
                preference_score = preferred_count / len(recs) if recs else 0
                diversity_scores.append(preference_score)
                
                print(f"\nAfter {count} interactions: {preferred_count}/10 from preferred category")
            
            # Accuracy should improve with more data
            assert diversity_scores[-1] > diversity_scores[0]  # Better than initial