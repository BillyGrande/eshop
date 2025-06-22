"""
Performance benchmarks for recommendation algorithms
"""

import pytest
import time
from contextlib import contextmanager
from eshop.hybrid_recommender import HybridRecommender
from eshop.ml_recommenders import LinearSVMRecommender, AdvancedNeighborsRecommender
from eshop.shopping_cart_recommender import ShoppingCartRecommender
from eshop.analytics import AnalyticsEngine
from tests.mock_data_generator import MockDataGenerator


@contextmanager
def timer(name):
    """Context manager for timing code execution"""
    start = time.time()
    yield
    end = time.time()
    print(f"\n{name}: {end - start:.4f} seconds")


class TestPerformanceBenchmarks:
    """Benchmark tests for recommendation system performance"""
    
    @pytest.fixture(scope='class')
    def large_dataset(self, app):
        """Generate a large dataset for performance testing"""
        with app.app_context():
            generator = MockDataGenerator()
            data = generator.generate_complete_test_dataset()
            return data
    
    def test_hybrid_recommender_performance(self, app, large_dataset):
        """Benchmark hybrid recommender with various user types"""
        with app.app_context():
            hybrid = HybridRecommender()
            users = large_dataset['users']
            
            # Test different user segments
            user_segments = {
                'new': [u for u in users if hasattr(u, '_mock_type') and u._mock_type == 'new'][:5],
                'casual': [u for u in users if hasattr(u, '_mock_type') and u._mock_type == 'casual'][:5],
                'vip': [u for u in users if hasattr(u, '_mock_type') and u._mock_type == 'vip'][:5]
            }
            
            for segment, segment_users in user_segments.items():
                total_time = 0
                for user in segment_users:
                    start = time.time()
                    recommendations = hybrid.get_recommendations(user.id, limit=10)
                    total_time += time.time() - start
                
                avg_time = total_time / len(segment_users)
                print(f"\nAverage time for {segment} users: {avg_time:.4f} seconds")
                
                # Performance assertions
                assert avg_time < 1.0  # Should complete in under 1 second
    
    def test_svm_training_performance(self, app, large_dataset):
        """Benchmark SVM model training time"""
        with app.app_context():
            svm = LinearSVMRecommender()
            users = large_dataset['users']
            
            # Test with users having different amounts of data
            test_users = [u for u in users if hasattr(u, '_mock_type') and u._mock_type == 'vip'][:3]
            
            for user in test_users:
                with timer(f"SVM training for user {user.id}"):
                    model = svm._train_user_model(user.id)
                    assert model is not None or user.id == test_users[0].id
    
    def test_neighbors_search_performance(self, app, large_dataset):
        """Benchmark neighbor search algorithm"""
        with app.app_context():
            neighbors = AdvancedNeighborsRecommender()
            users = large_dataset['users']
            products = large_dataset['products']
            
            # Test with active user
            active_user = [u for u in users if hasattr(u, '_mock_type') and u._mock_type == 'regular'][0]
            
            with timer("Neighbor search and recommendation"):
                recommendations = neighbors.get_recommendations(
                    active_user.id, 
                    products[:100],  # Limit products for testing
                    limit=10
                )
            
            assert len(recommendations) <= 10
    
    def test_cart_association_performance(self, app, large_dataset):
        """Benchmark shopping cart association mining"""
        with app.app_context():
            cart_rec = ShoppingCartRecommender()
            products = large_dataset['products']
            
            # Test with different cart sizes
            cart_sizes = [1, 3, 5, 10]
            
            for size in cart_sizes:
                cart_items = [p.id for p in products[:size]]
                
                with timer(f"Cart recommendations for {size} items"):
                    recommendations = cart_rec.get_cart_recommendations(
                        cart_items,
                        products,
                        limit=10
                    )
                
                assert len(recommendations) <= 10
    
    def test_analytics_update_performance(self, app, large_dataset):
        """Benchmark analytics engine update performance"""
        with app.app_context():
            analytics = AnalyticsEngine()
            
            with timer("Analytics full update"):
                analytics.update_analytics()
            
            # Verify analytics were calculated
            best_sellers = analytics.get_best_sellers(limit=10)
            trending = analytics.get_trending_products(limit=10)
            
            assert len(best_sellers) > 0
            assert len(trending) > 0
    
    def test_concurrent_user_performance(self, app, large_dataset):
        """Simulate multiple concurrent users getting recommendations"""
        with app.app_context():
            hybrid = HybridRecommender()
            users = large_dataset['users'][:10]  # Test with 10 concurrent users
            
            start = time.time()
            
            # Simulate concurrent requests
            for user in users:
                recommendations = hybrid.get_recommendations(user.id, limit=10)
                assert len(recommendations) <= 10
            
            total_time = time.time() - start
            avg_time = total_time / len(users)
            
            print(f"\nAverage time per user (concurrent simulation): {avg_time:.4f} seconds")
            print(f"Total time for {len(users)} users: {total_time:.4f} seconds")
            
            # Should handle 10 users in reasonable time
            assert total_time < 10.0
    
    def test_memory_usage(self, app, large_dataset):
        """Test memory usage of recommendation algorithms"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        
        with app.app_context():
            # Baseline memory
            baseline_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            # Create all recommenders
            hybrid = HybridRecommender()
            svm = LinearSVMRecommender()
            neighbors = AdvancedNeighborsRecommender()
            cart = ShoppingCartRecommender()
            
            # Generate recommendations for multiple users
            users = large_dataset['users'][:20]
            for user in users:
                hybrid.get_recommendations(user.id, limit=10)
            
            # Check memory after recommendations
            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = final_memory - baseline_memory
            
            print(f"\nMemory usage - Baseline: {baseline_memory:.2f} MB")
            print(f"Memory usage - Final: {final_memory:.2f} MB")
            print(f"Memory increase: {memory_increase:.2f} MB")
            
            # Memory increase should be reasonable
            assert memory_increase < 500  # Less than 500MB increase