"""
Caching layer for recommendation system
Provides in-memory and Redis-based caching for improved performance
"""

import pickle
import hashlib
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from functools import wraps
import redis
from flask import current_app
from .models import db, User, Product


class RecommendationCache:
    """Caching layer for recommendation results"""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None, 
                 default_ttl: int = 3600):
        """
        Initialize cache with optional Redis backend
        
        Args:
            redis_client: Redis client instance (None for in-memory only)
            default_ttl: Default time-to-live in seconds
        """
        self.redis_client = redis_client
        self.default_ttl = default_ttl
        self.in_memory_cache = {}
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0
        }
    
    def _generate_cache_key(self, key_type: str, **kwargs) -> str:
        """Generate consistent cache key from parameters"""
        # Sort kwargs for consistent key generation
        sorted_kwargs = sorted(kwargs.items())
        key_data = f"{key_type}:" + ":".join(f"{k}={v}" for k, v in sorted_kwargs)
        
        # Use hash for long keys
        if len(key_data) > 250:
            hash_digest = hashlib.md5(key_data.encode()).hexdigest()
            return f"{key_type}:hash:{hash_digest}"
        
        return key_data
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        # Try in-memory first
        if key in self.in_memory_cache:
            entry = self.in_memory_cache[key]
            if entry['expires_at'] > datetime.utcnow():
                self.cache_stats['hits'] += 1
                return entry['value']
            else:
                # Expired
                del self.in_memory_cache[key]
                self.cache_stats['evictions'] += 1
        
        # Try Redis if available
        if self.redis_client:
            try:
                cached_data = self.redis_client.get(key)
                if cached_data:
                    self.cache_stats['hits'] += 1
                    value = pickle.loads(cached_data)
                    # Also store in memory for faster access
                    self._store_in_memory(key, value, ttl=60)  # Short TTL for memory
                    return value
            except Exception as e:
                print(f"Redis get error: {e}")
        
        self.cache_stats['misses'] += 1
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache with TTL"""
        if ttl is None:
            ttl = self.default_ttl
        
        # Store in memory
        self._store_in_memory(key, value, ttl)
        
        # Store in Redis if available
        if self.redis_client:
            try:
                serialized = pickle.dumps(value)
                self.redis_client.setex(key, ttl, serialized)
                return True
            except Exception as e:
                print(f"Redis set error: {e}")
                return False
        
        return True
    
    def _store_in_memory(self, key: str, value: Any, ttl: int):
        """Store in in-memory cache with expiration"""
        expires_at = datetime.utcnow() + timedelta(seconds=ttl)
        self.in_memory_cache[key] = {
            'value': value,
            'expires_at': expires_at
        }
        
        # Simple eviction if cache gets too large
        if len(self.in_memory_cache) > 1000:
            self._evict_expired()
        
        if len(self.in_memory_cache) > 1000:
            # Remove oldest entries
            sorted_keys = sorted(
                self.in_memory_cache.keys(),
                key=lambda k: self.in_memory_cache[k]['expires_at']
            )
            for key in sorted_keys[:100]:  # Remove 100 oldest
                del self.in_memory_cache[key]
                self.cache_stats['evictions'] += 1
    
    def _evict_expired(self):
        """Remove expired entries from in-memory cache"""
        now = datetime.utcnow()
        expired_keys = [
            key for key, entry in self.in_memory_cache.items()
            if entry['expires_at'] <= now
        ]
        for key in expired_keys:
            del self.in_memory_cache[key]
            self.cache_stats['evictions'] += 1
    
    def invalidate(self, pattern: str):
        """Invalidate cache entries matching pattern"""
        # In-memory invalidation
        keys_to_delete = [
            key for key in self.in_memory_cache.keys()
            if pattern in key
        ]
        for key in keys_to_delete:
            del self.in_memory_cache[key]
        
        # Redis invalidation
        if self.redis_client:
            try:
                for key in self.redis_client.scan_iter(match=f"*{pattern}*"):
                    self.redis_client.delete(key)
            except Exception as e:
                print(f"Redis invalidate error: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self.cache_stats['hits'] + self.cache_stats['misses']
        hit_rate = self.cache_stats['hits'] / total_requests if total_requests > 0 else 0
        
        return {
            'hits': self.cache_stats['hits'],
            'misses': self.cache_stats['misses'],
            'evictions': self.cache_stats['evictions'],
            'hit_rate': hit_rate,
            'memory_entries': len(self.in_memory_cache),
            'total_requests': total_requests
        }
    
    def clear(self):
        """Clear all cache entries"""
        self.in_memory_cache.clear()
        if self.redis_client:
            try:
                self.redis_client.flushdb()
            except Exception as e:
                print(f"Redis clear error: {e}")
        
        # Reset stats
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0
        }


# Global cache instance
_cache_instance = None


def get_cache() -> RecommendationCache:
    """Get or create cache instance"""
    global _cache_instance
    if _cache_instance is None:
        # Try to connect to Redis if available
        redis_client = None
        try:
            redis_client = redis.Redis(
                host='localhost',
                port=6379,
                db=0,
                decode_responses=False  # We're using pickle
            )
            redis_client.ping()  # Test connection
        except:
            print("Redis not available, using in-memory cache only")
            redis_client = None
        
        _cache_instance = RecommendationCache(
            redis_client=redis_client,
            default_ttl=3600  # 1 hour default
        )
    
    return _cache_instance


def cached_recommendation(ttl: int = 3600):
    """Decorator for caching recommendation results"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache = get_cache()
            
            # Generate cache key based on function name and arguments
            cache_key = cache._generate_cache_key(
                key_type=func.__name__,
                args=str(args),
                kwargs=str(kwargs)
            )
            
            # Try to get from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Calculate result
            result = func(*args, **kwargs)
            
            # Store in cache
            cache.set(cache_key, result, ttl=ttl)
            
            return result
        
        return wrapper
    return decorator


class CacheManager:
    """Manager for cache invalidation strategies"""
    
    @staticmethod
    def invalidate_user_cache(user_id: int):
        """Invalidate all cache entries for a specific user"""
        cache = get_cache()
        cache.invalidate(f"user_id={user_id}")
    
    @staticmethod
    def invalidate_product_cache(product_id: int):
        """Invalidate all cache entries for a specific product"""
        cache = get_cache()
        cache.invalidate(f"product_id={product_id}")
    
    @staticmethod
    def invalidate_category_cache(category: str):
        """Invalidate all cache entries for a specific category"""
        cache = get_cache()
        cache.invalidate(f"category={category}")
    
    @staticmethod
    def warmup_cache(user_ids: List[int] = None, limit: int = 100):
        """Pre-populate cache for active users"""
        from .hybrid_recommender import HybridRecommender
        
        if user_ids is None:
            # Get most active users
            from sqlalchemy import func
            from .models import UserInteraction
            
            active_users = db.session.query(
                UserInteraction.user_id,
                func.count(UserInteraction.id).label('interaction_count')
            ).group_by(
                UserInteraction.user_id
            ).order_by(
                func.count(UserInteraction.id).desc()
            ).limit(limit).all()
            
            user_ids = [user_id for user_id, _ in active_users]
        
        recommender = HybridRecommender()
        cache = get_cache()
        
        warmed_count = 0
        for user_id in user_ids:
            try:
                # Generate recommendations (will be cached)
                recommendations = recommender.get_recommendations(user_id, limit=10)
                if recommendations:
                    warmed_count += 1
            except Exception as e:
                print(f"Error warming cache for user {user_id}: {e}")
        
        return warmed_count