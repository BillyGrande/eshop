from collections import defaultdict
from .models import db, Product, UserInteraction, OrderItem
from sqlalchemy import func

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