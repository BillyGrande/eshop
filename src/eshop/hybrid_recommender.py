"""
Hybrid Recommendation Engine that combines multiple recommendation algorithms
with configurable weights based on user data availability.
"""

import numpy as np
from .models import db, UserInteraction, Order, Product
from .ml_recommenders import LinearSVMRecommender, AdvancedNeighborsRecommender
from .shopping_cart_recommender import ShoppingCartRecommender
from .analytics import AnalyticsEngine
from .recommendation_cache import cached_recommendation, get_cache


class HybridRecommender:
    """
    Combines multiple recommendation strategies based on user data availability:
    - New users: Best sellers + trending
    - Minimal data (5-20 interactions): Cold start algorithm
    - Established users: Linear SVM + Neighbors + Shopping Cart + Best Sellers
    """
    
    def __init__(self):
        self.svm_recommender = LinearSVMRecommender()
        self.neighbors_recommender = AdvancedNeighborsRecommender()
        self.cart_recommender = ShoppingCartRecommender()
        self.analytics = AnalyticsEngine()
        
        # Weight configurations for different user segments
        self.weights = {
            'new_user': {
                'best_sellers': 0.5,
                'trending': 0.5
            },
            'minimal_data': {
                'cold_start': 1.0
            },
            'established_user': {
                'linear_svm': 0.3,
                'neighbors': 0.3,
                'shopping_cart': 0.2,
                'best_sellers': 0.2
            }
        }
    
    def get_recommendations(self, user_id, limit=10):
        """
        Get hybrid recommendations for a user based on their data profile
        
        Args:
            user_id: User ID
            limit: Number of recommendations to return
            
        Returns:
            List of recommended products
        """
        # Determine user segment
        user_segment = self._determine_user_segment(user_id)
        
        # Get all candidate products
        candidate_products = Product.query.filter(
            Product.stock_quantity > 0
        ).all()
        
        if user_segment == 'new_user':
            return self._get_new_user_recommendations(limit)
        elif user_segment == 'minimal_data':
            return self._get_minimal_data_recommendations(user_id, candidate_products, limit)
        else:  # established_user
            return self._get_established_user_recommendations(user_id, candidate_products, limit)
    
    def _determine_user_segment(self, user_id):
        """Determine which recommendation strategy to use based on user data"""
        interaction_count = UserInteraction.query.filter_by(user_id=user_id).count()
        purchase_count = db.session.query(Order).filter_by(user_id=user_id).count()
        
        if interaction_count < 5:
            return 'new_user'
        elif interaction_count < 20 or purchase_count < 2:
            return 'minimal_data'
        else:
            return 'established_user'
    
    def _get_new_user_recommendations(self, limit):
        """Get recommendations for new users (best sellers + trending)"""
        weights = self.weights['new_user']
        
        # Get best sellers
        best_sellers_count = int(limit * weights['best_sellers'])
        best_sellers = self.analytics.get_best_sellers(
            time_window='30d',
            limit=best_sellers_count
        )
        
        # Get trending products
        trending_count = limit - best_sellers_count
        trending = self.analytics.get_trending_products(
            limit=trending_count
        )
        
        # Combine and shuffle
        recommendations = best_sellers + trending
        np.random.shuffle(recommendations)
        
        return recommendations[:limit]
    
    def _get_minimal_data_recommendations(self, user_id, candidate_products, limit):
        """Get recommendations for users with minimal data (cold start)"""
        # Use the existing cold start implementation from recommender.py
        from .recommender import Recommender
        return Recommender.get_cold_start_recommendations(user_id, limit)
    
    def _get_established_user_recommendations(self, user_id, candidate_products, limit):
        """Get recommendations for established users using all algorithms"""
        weights = self.weights['established_user']
        
        # Collect recommendations from each algorithm
        all_recommendations = {}
        
        # Linear SVM recommendations
        if weights['linear_svm'] > 0:
            svm_recs = self.svm_recommender.get_recommendations(
                user_id, candidate_products, limit=limit*2
            )
            for i, product in enumerate(svm_recs):
                if product.id not in all_recommendations:
                    all_recommendations[product.id] = {
                        'product': product,
                        'scores': {},
                        'total_score': 0.0
                    }
                # Normalize rank to score (higher rank = higher score)
                score = 1.0 - (i / len(svm_recs))
                all_recommendations[product.id]['scores']['linear_svm'] = score
        
        # Neighbors recommendations
        if weights['neighbors'] > 0:
            neighbors_recs = self.neighbors_recommender.get_recommendations(
                user_id, candidate_products, limit=limit*2
            )
            for i, product in enumerate(neighbors_recs):
                if product.id not in all_recommendations:
                    all_recommendations[product.id] = {
                        'product': product,
                        'scores': {},
                        'total_score': 0.0
                    }
                score = 1.0 - (i / len(neighbors_recs))
                all_recommendations[product.id]['scores']['neighbors'] = score
        
        # Shopping cart recommendations (based on purchase history)
        if weights['shopping_cart'] > 0:
            # Get user's recent purchases for cart-based recommendations
            recent_purchases = self._get_recent_purchase_ids(user_id, days=30)
            if recent_purchases:
                cart_recs = self.cart_recommender.get_cart_recommendations(
                    recent_purchases, candidate_products, limit=limit*2
                )
                for i, product in enumerate(cart_recs):
                    if product.id not in all_recommendations:
                        all_recommendations[product.id] = {
                            'product': product,
                            'scores': {},
                            'total_score': 0.0
                        }
                    score = 1.0 - (i / len(cart_recs))
                    all_recommendations[product.id]['scores']['shopping_cart'] = score
        
        # Best sellers
        if weights['best_sellers'] > 0:
            best_sellers = self.analytics.get_best_sellers(
                time_window='30d',
                limit=limit*2
            )
            for i, product in enumerate(best_sellers):
                if product.id not in all_recommendations:
                    all_recommendations[product.id] = {
                        'product': product,
                        'scores': {},
                        'total_score': 0.0
                    }
                score = 1.0 - (i / len(best_sellers))
                all_recommendations[product.id]['scores']['best_sellers'] = score
        
        # Calculate weighted total scores
        for product_id, rec_data in all_recommendations.items():
            total_score = 0.0
            for algo, score in rec_data['scores'].items():
                total_score += score * weights.get(algo, 0)
            rec_data['total_score'] = total_score
            # Attach score to product for debugging
            rec_data['product']._hybrid_score = total_score
            rec_data['product']._hybrid_sources = list(rec_data['scores'].keys())
        
        # Sort by total score and return top products
        sorted_recommendations = sorted(
            all_recommendations.values(),
            key=lambda x: x['total_score'],
            reverse=True
        )
        
        # Ensure diversity in top recommendations
        final_recommendations = self._ensure_diversity(
            [r['product'] for r in sorted_recommendations],
            limit
        )
        
        return final_recommendations
    
    def _get_recent_purchase_ids(self, user_id, days=30):
        """Get product IDs from user's recent purchases"""
        from datetime import datetime, timedelta
        from .models import OrderItem
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        recent_purchases = db.session.query(OrderItem.product_id).join(Order).filter(
            Order.user_id == user_id,
            Order.created_at >= cutoff_date
        ).distinct().limit(10).all()
        
        return [p[0] for p in recent_purchases]
    
    def _ensure_diversity(self, products, limit):
        """Ensure category and price diversity in recommendations"""
        if len(products) <= limit:
            return products
        
        diversified = []
        categories_seen = set()
        price_ranges_seen = set()
        
        # First pass: prioritize diversity
        for product in products:
            if len(diversified) >= limit:
                break
                
            category = product.category
            price_range = self._get_price_range(product.price)
            
            # Prioritize products from new categories or price ranges
            if category not in categories_seen or price_range not in price_ranges_seen:
                diversified.append(product)
                categories_seen.add(category)
                price_ranges_seen.add(price_range)
        
        # Second pass: fill remaining slots with highest scored products
        for product in products:
            if len(diversified) >= limit:
                break
            if product not in diversified:
                diversified.append(product)
        
        return diversified
    
    def get_cached_recommendations(self, user_id, limit=10):
        """Cached wrapper for get_recommendations"""
        cache = get_cache()
        
        # Generate cache key
        cache_key = cache._generate_cache_key(
            key_type='hybrid_recommendations',
            user_id=user_id,
            limit=limit
        )
        
        # Try to get from cache
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            return cached_result
        
        # Calculate recommendations
        result = self.get_recommendations(user_id, limit)
        
        # Store in cache
        cache.set(cache_key, result, ttl=3600)  # 1 hour
        
        return result
    
    def _get_price_range(self, price):
        """Categorize price into ranges"""
        if price < 50:
            return 'budget'
        elif price < 150:
            return 'mid'
        elif price < 300:
            return 'premium'
        else:
            return 'luxury'
    
    def get_algorithm_weights(self, user_id):
        """Get the algorithm weights that would be used for a specific user"""
        segment = self._determine_user_segment(user_id)
        return {
            'segment': segment,
            'weights': self.weights[segment]
        }
    
    def update_weights(self, segment, new_weights):
        """Update algorithm weights for a specific user segment"""
        if segment in self.weights:
            # Normalize weights to sum to 1.0
            total = sum(new_weights.values())
            normalized = {k: v/total for k, v in new_weights.items()}
            self.weights[segment] = normalized
            return True
        return False