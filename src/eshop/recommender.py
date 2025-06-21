from collections import defaultdict
from datetime import datetime, timedelta
from .models import db, Product, UserInteraction, OrderItem, GuestInteraction
from .analytics import AnalyticsEngine
from sqlalchemy import func, and_, or_
import random

class Recommender:
    @staticmethod
    def get_popular_products(limit=10):
        """Get most popular products based on all interactions"""
        popular = db.session.query(
            Product,
            func.count(UserInteraction.id).label('interaction_count')
        ).join(
            UserInteraction
        ).group_by(
            Product.id
        ).order_by(
            func.count(UserInteraction.id).desc()
        ).limit(limit).all()
        
        return [product for product, _ in popular]
    
    @staticmethod
    def get_recommendations_for_guest(session_id, limit=10):
        """Get recommendations for guest users based on session interactions"""
        # Count guest interactions
        interaction_count = GuestInteraction.query.filter_by(session_id=session_id).count()
        
        if interaction_count < 3:
            # Initial state: 50% best sellers + 50% trending
            # Use ceiling division to ensure we get enough recommendations
            best_sellers_limit = (limit + 1) // 2
            trending_limit = limit - best_sellers_limit
            
            best_sellers = AnalyticsEngine.get_best_sellers(time_window='30d', limit=best_sellers_limit)
            trending = AnalyticsEngine.get_trending_products(limit=trending_limit)
            
            # Combine and shuffle
            recommendations = best_sellers + trending
            random.shuffle(recommendations)
            
            # If not enough recommendations, get more from popular products
            if len(recommendations) < limit:
                additional_needed = limit - len(recommendations)
                existing_ids = {r.id for r in recommendations}
                popular = Recommender.get_popular_products(limit=additional_needed + 10)
                for product in popular:
                    if product.id not in existing_ids and len(recommendations) < limit:
                        recommendations.append(product)
            
            return recommendations[:limit]
        else:
            # After 3+ interactions: 50% cold start + 25% best sellers + 25% trending
            cold_start_limit = (limit + 1) // 2
            best_sellers_limit = (limit + 3) // 4
            trending_limit = (limit + 3) // 4
            
            cold_start_recs = Recommender._cold_start_for_guest(session_id, limit=cold_start_limit)
            best_sellers = AnalyticsEngine.get_best_sellers(time_window='30d', limit=best_sellers_limit)
            trending = AnalyticsEngine.get_trending_products(limit=trending_limit)
            
            # Combine all recommendations
            recommendations = cold_start_recs + best_sellers + trending
            
            # Remove duplicates while preserving order
            seen = set()
            unique_recommendations = []
            for product in recommendations:
                if product and product.id not in seen:
                    seen.add(product.id)
                    unique_recommendations.append(product)
            
            # If not enough recommendations, get more from popular products
            if len(unique_recommendations) < limit:
                additional_needed = limit - len(unique_recommendations)
                existing_ids = {r.id for r in unique_recommendations}
                popular = Recommender.get_popular_products(limit=additional_needed + 10)
                for product in popular:
                    if product.id not in existing_ids and len(unique_recommendations) < limit:
                        unique_recommendations.append(product)
            
            return unique_recommendations[:limit]
    
    @staticmethod
    def _cold_start_for_guest(session_id, limit=5):
        """Cold start recommendations based on guest session activity"""
        # Get guest's interaction history
        interactions = GuestInteraction.query.filter_by(session_id=session_id).all()
        
        if not interactions:
            return []
        
        # Extract patterns from interactions
        category_counts = defaultdict(int)
        viewed_products = set()
        price_points = []
        
        for interaction in interactions:
            product = interaction.product
            category_counts[product.category] += 1
            viewed_products.add(product.id)
            if interaction.interaction_type in ['click', 'add_to_cart']:
                price_points.append(product.price)
        
        # Find preferred categories
        preferred_categories = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        preferred_categories = [cat for cat, _ in preferred_categories]
        
        # Calculate price range preference
        if price_points:
            avg_price = sum(price_points) / len(price_points)
            price_min = avg_price * 0.7
            price_max = avg_price * 1.3
        else:
            price_min = 0
            price_max = float('inf')
        
        # Find products in preferred categories and price range
        recommendations = Product.query.filter(
            and_(
                Product.category.in_(preferred_categories),
                Product.price >= price_min,
                Product.price <= price_max,
                ~Product.id.in_(viewed_products)
            )
        ).order_by(func.random()).limit(limit * 2).all()
        
        # If not enough, expand search
        if len(recommendations) < limit:
            additional = Product.query.filter(
                and_(
                    Product.price >= price_min,
                    Product.price <= price_max,
                    ~Product.id.in_(viewed_products),
                    ~Product.id.in_([r.id for r in recommendations])
                )
            ).order_by(func.random()).limit(limit - len(recommendations)).all()
            recommendations.extend(additional)
        
        return recommendations[:limit]
    
    @staticmethod
    def get_recommendations_for_user(user_id, limit=10):
        """Get personalized recommendations for a user"""
        # Check if user has enough interactions
        interaction_count = UserInteraction.query.filter_by(user_id=user_id).count()
        
        if interaction_count < 5:
            # Fall back to popular products for new users
            return Recommender.get_popular_products(limit)
        
        # Get products the user has interacted with
        user_products = db.session.query(UserInteraction.product_id).filter_by(
            user_id=user_id
        ).subquery()
        
        # Find other users who bought the same products
        similar_users = db.session.query(
            UserInteraction.user_id
        ).filter(
            UserInteraction.product_id.in_(user_products),
            UserInteraction.user_id != user_id,
            UserInteraction.interaction_type == 'purchase'
        ).distinct().subquery()
        
        # Get products those similar users bought
        recommendations = db.session.query(
            Product,
            func.count(UserInteraction.id).label('score')
        ).join(
            UserInteraction
        ).filter(
            UserInteraction.user_id.in_(similar_users),
            UserInteraction.interaction_type == 'purchase',
            ~Product.id.in_(user_products)
        ).group_by(
            Product.id
        ).order_by(
            func.count(UserInteraction.id).desc()
        ).limit(limit).all()
        
        return [product for product, _ in recommendations]
    
    @staticmethod
    def get_similar_products(product_id, limit=5):
        """Get products similar to a given product"""
        product = Product.query.get(product_id)
        if not product:
            return []
        
        # Simple category-based similarity
        similar = Product.query.filter(
            Product.category == product.category,
            Product.id != product_id
        ).order_by(
            func.abs(Product.price - product.price)
        ).limit(limit).all()
        
        return similar