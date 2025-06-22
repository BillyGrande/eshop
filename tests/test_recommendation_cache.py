"""
Tests for recommendation caching system
Tests both in-memory and Redis-based caching functionality
"""

import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import redis
from eshop.recommendation_cache import (
    RecommendationCache, get_cache, cached_recommendation, CacheManager
)
from eshop.models import db, User, Product, UserInteraction
from eshop.hybrid_recommender import HybridRecommender


class TestRecommendationCache:
    """Test basic cache functionality"""
    
    def test_in_memory_cache_basic(self):
        """Test basic in-memory cache operations"""
        cache = RecommendationCache(redis_client=None)
        
        # Test set and get
        cache.set('test_key', 'test_value', ttl=60)
        assert cache.get('test_key') == 'test_value'
        
        # Test cache hit statistics
        stats = cache.get_stats()
        assert stats['hits'] == 1
        assert stats['misses'] == 0
        
        # Test cache miss
        assert cache.get('nonexistent_key') is None
        stats = cache.get_stats()
        assert stats['misses'] == 1
    
    def test_cache_expiration(self):
        """Test cache TTL and expiration"""
        cache = RecommendationCache(redis_client=None)
        
        # Set with very short TTL
        cache.set('expire_test', 'value', ttl=1)
        assert cache.get('expire_test') == 'value'
        
        # Wait for expiration
        time.sleep(1.1)
        assert cache.get('expire_test') is None
        
        stats = cache.get_stats()
        assert stats['evictions'] == 1
    
    def test_cache_key_generation(self):
        """Test consistent cache key generation"""
        cache = RecommendationCache()
        
        # Test basic key generation
        key1 = cache._generate_cache_key('test', user_id=1, limit=10)
        key2 = cache._generate_cache_key('test', limit=10, user_id=1)  # Different order
        assert key1 == key2  # Should be consistent regardless of argument order
        
        # Test long key hashing
        long_data = 'x' * 300
        long_key = cache._generate_cache_key('test', data=long_data)
        assert 'hash:' in long_key
        assert len(long_key) < 250
    
    def test_cache_eviction_policy(self):
        """Test cache eviction when memory limit is reached"""
        cache = RecommendationCache(redis_client=None)
        
        # Fill cache beyond limit
        for i in range(1100):
            cache.set(f'key_{i}', f'value_{i}', ttl=3600)
        
        # Check that cache size is limited
        assert len(cache.in_memory_cache) <= 1000
        stats = cache.get_stats()
        assert stats['evictions'] > 0
    
    def test_cache_invalidation(self):
        """Test cache invalidation by pattern"""
        cache = RecommendationCache(redis_client=None)
        
        # Set multiple keys
        cache.set('user_id=1:rec', [1, 2, 3])
        cache.set('user_id=1:offers', [4, 5])
        cache.set('user_id=2:rec', [6, 7])
        
        # Invalidate user 1's cache
        cache.invalidate('user_id=1')
        
        # Check invalidation
        assert cache.get('user_id=1:rec') is None
        assert cache.get('user_id=1:offers') is None
        assert cache.get('user_id=2:rec') == [6, 7]  # Should still exist
    
    def test_complex_data_types(self):
        """Test caching of complex data structures"""
        cache = RecommendationCache(redis_client=None)
        
        # Test list of dictionaries (typical recommendation format)
        recommendations = [
            {'product_id': 1, 'score': 0.9},
            {'product_id': 2, 'score': 0.8}
        ]
        cache.set('complex_rec', recommendations)
        retrieved = cache.get('complex_rec')
        assert retrieved == recommendations
        
        # Test nested structures
        nested_data = {
            'user_segment': 'established',
            'weights': {'svm': 0.3, 'neighbors': 0.3},
            'metadata': {'timestamp': datetime.now().isoformat()}
        }
        cache.set('nested_data', nested_data)
        assert cache.get('nested_data') == nested_data


class TestRedisCache:
    """Test Redis-based caching functionality"""
    
    @patch('redis.Redis')
    def test_redis_connection(self, mock_redis_class):
        """Test Redis connection handling"""
        mock_redis = Mock()
        mock_redis_class.return_value = mock_redis
        mock_redis.ping.return_value = True
        
        cache = RecommendationCache(redis_client=mock_redis)
        
        # Test set operation
        cache.set('test_key', 'test_value', ttl=60)
        mock_redis.setex.assert_called_once()
        
        # Test get operation
        mock_redis.get.return_value = b'pickled_data'
        with patch('pickle.loads', return_value='test_value'):
            result = cache.get('test_key')
            assert result == 'test_value'
    
    @patch('redis.Redis')
    def test_redis_failure_fallback(self, mock_redis_class):
        """Test fallback to in-memory when Redis fails"""
        mock_redis = Mock()
        mock_redis_class.return_value = mock_redis
        mock_redis.ping.side_effect = Exception("Connection failed")
        
        # Should still work with in-memory cache
        cache = RecommendationCache(redis_client=None)  # Falls back to memory only
        cache.set('test_key', 'test_value')
        assert cache.get('test_key') == 'test_value'
    
    @patch('redis.Redis')
    def test_redis_invalidation(self, mock_redis_class):
        """Test Redis cache invalidation"""
        mock_redis = Mock()
        mock_redis_class.return_value = mock_redis
        mock_redis.scan_iter.return_value = [b'user_id=1:rec1', b'user_id=1:rec2']
        
        cache = RecommendationCache(redis_client=mock_redis)
        cache.invalidate('user_id=1')
        
        # Check that scan and delete were called
        mock_redis.scan_iter.assert_called_once_with(match='*user_id=1*')
        assert mock_redis.delete.call_count == 2


class TestCacheDecorator:
    """Test the @cached_recommendation decorator"""
    
    def test_decorator_basic(self):
        """Test basic decorator functionality"""
        call_count = 0
        
        @cached_recommendation(ttl=60)
        def expensive_function(user_id, limit=10):
            nonlocal call_count
            call_count += 1
            return [1, 2, 3]
        
        # First call should execute function
        result1 = expensive_function(1, limit=10)
        assert result1 == [1, 2, 3]
        assert call_count == 1
        
        # Second call should use cache
        result2 = expensive_function(1, limit=10)
        assert result2 == [1, 2, 3]
        assert call_count == 1  # Function not called again
        
        # Different arguments should call function
        result3 = expensive_function(2, limit=10)
        assert call_count == 2
    
    def test_decorator_with_recommender(self, app, sample_users, sample_products):
        """Test decorator with actual recommender class"""
        with app.app_context():
            # Patch the recommender method
            original_method = HybridRecommender.get_recommendations
            call_count = 0
            
            @cached_recommendation(ttl=300)
            def cached_get_recommendations(self, user_id, limit=10):
                nonlocal call_count
                call_count += 1
                return original_method(self, user_id, limit)
            
            # Replace method with cached version
            HybridRecommender.get_recommendations = cached_get_recommendations
            
            recommender = HybridRecommender()
            user = sample_users[0]
            
            # First call
            rec1 = recommender.get_recommendations(user.id, limit=5)
            assert call_count == 1
            
            # Second call (should be cached)
            rec2 = recommender.get_recommendations(user.id, limit=5)
            assert call_count == 1  # No additional call
            assert rec1 == rec2
            
            # Restore original method
            HybridRecommender.get_recommendations = original_method


class TestCacheManager:
    """Test cache management and invalidation strategies"""
    
    def test_user_cache_invalidation(self):
        """Test invalidating all cache for a user"""
        cache = get_cache()
        cache.clear()
        
        # Set various user-related cache entries
        cache.set('get_recommendations:user_id=1:limit=10', [1, 2, 3])
        cache.set('get_offers:user_id=1', [4, 5])
        cache.set('get_recommendations:user_id=2:limit=10', [6, 7])
        
        # Invalidate user 1
        CacheManager.invalidate_user_cache(1)
        
        # Check results
        assert cache.get('get_recommendations:user_id=1:limit=10') is None
        assert cache.get('get_offers:user_id=1') is None
        assert cache.get('get_recommendations:user_id=2:limit=10') == [6, 7]
    
    def test_product_cache_invalidation(self):
        """Test invalidating cache for a product"""
        cache = get_cache()
        cache.clear()
        
        # Set product-related cache
        cache.set('similar_products:product_id=1', [2, 3, 4])
        cache.set('product_stats:product_id=1', {'views': 100})
        cache.set('similar_products:product_id=2', [1, 3])
        
        # Invalidate product 1
        CacheManager.invalidate_product_cache(1)
        
        # Check results
        assert cache.get('similar_products:product_id=1') is None
        assert cache.get('product_stats:product_id=1') is None
        assert cache.get('similar_products:product_id=2') == [1, 3]
    
    def test_cache_warmup(self, app, sample_users, sample_products):
        """Test cache warming functionality"""
        with app.app_context():
            cache = get_cache()
            cache.clear()
            
            # Add some interactions for users
            for i, user in enumerate(sample_users[:3]):
                for j, product in enumerate(sample_products[:5]):
                    interaction = UserInteraction(
                        user_id=user.id,
                        product_id=product.id,
                        interaction_type='view'
                    )
                    db.session.add(interaction)
            db.session.commit()
            
            # Warm cache
            warmed = CacheManager.warmup_cache(limit=3)
            
            # Check that cache was populated
            stats = cache.get_stats()
            assert stats['memory_entries'] > 0
            assert warmed > 0


class TestCachePerformance:
    """Test cache performance improvements"""
    
    def test_cache_performance_improvement(self, app, sample_users, sample_products):
        """Test that cache improves recommendation performance"""
        with app.app_context():
            import time
            
            recommender = HybridRecommender()
            user = sample_users[0]
            
            # Clear cache
            cache = get_cache()
            cache.clear()
            
            # Time without cache
            start = time.time()
            rec1 = recommender.get_recommendations(user.id, limit=10)
            uncached_time = time.time() - start
            
            # Time with cache (second call)
            start = time.time()
            rec2 = recommender.get_recommendations(user.id, limit=10)
            cached_time = time.time() - start
            
            # Cached should be much faster
            assert cached_time < uncached_time * 0.5  # At least 2x faster
            assert rec1 == rec2  # Results should be identical
    
    def test_concurrent_cache_access(self):
        """Test thread-safe cache access"""
        import threading
        
        cache = RecommendationCache(redis_client=None)
        results = []
        errors = []
        
        def worker(worker_id):
            try:
                for i in range(100):
                    cache.set(f'worker_{worker_id}_key_{i}', i)
                    value = cache.get(f'worker_{worker_id}_key_{i}')
                    if value != i:
                        errors.append(f"Worker {worker_id}: Expected {i}, got {value}")
                results.append(worker_id)
            except Exception as e:
                errors.append(f"Worker {worker_id} error: {e}")
        
        # Run multiple threads
        threads = []
        for i in range(5):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()
        
        # Wait for completion
        for t in threads:
            t.join()
        
        # Check results
        assert len(results) == 5
        assert len(errors) == 0


class TestCacheIntegration:
    """Integration tests with the full recommendation system"""
    
    def test_recommendation_caching_flow(self, app, authenticated_client, sample_products):
        """Test full recommendation flow with caching"""
        with app.app_context():
            cache = get_cache()
            cache.clear()
            
            # Get initial cache stats
            initial_stats = cache.get_stats()
            
            # First request - should miss cache
            response1 = authenticated_client.get('/')
            assert response1.status_code == 200
            
            # Check cache was populated
            stats = cache.get_stats()
            assert stats['misses'] > initial_stats['misses']
            
            # Second request - should hit cache
            response2 = authenticated_client.get('/')
            assert response2.status_code == 200
            
            # Check cache hit
            final_stats = cache.get_stats()
            assert final_stats['hits'] > stats['hits']
    
    def test_cache_invalidation_on_interaction(self, app, sample_users, sample_products):
        """Test that cache is invalidated when user interactions change"""
        with app.app_context():
            cache = get_cache()
            cache.clear()
            
            user = sample_users[0]
            recommender = HybridRecommender()
            
            # Get initial recommendations (will be cached)
            rec1 = recommender.get_recommendations(user.id, limit=5)
            
            # Add new interaction
            interaction = UserInteraction(
                user_id=user.id,
                product_id=sample_products[0].id,
                interaction_type='purchase'
            )
            db.session.add(interaction)
            db.session.commit()
            
            # Invalidate cache for this user
            CacheManager.invalidate_user_cache(user.id)
            
            # Get recommendations again (should recalculate)
            rec2 = recommender.get_recommendations(user.id, limit=5)
            
            # Should have recalculated (cache miss)
            stats = cache.get_stats()
            assert stats['misses'] >= 2  # At least 2 misses