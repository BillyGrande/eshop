from collections import defaultdict
from datetime import datetime, timedelta
from .models import db, Product, UserInteraction, OrderItem, GuestInteraction
from .analytics import AnalyticsEngine
from .hybrid_recommender import HybridRecommender
from sqlalchemy import func, and_, or_
import random

class Recommender:
    @staticmethod
    def _apply_recommendation_discount(products):
        """Apply 10% discount to all recommended products"""
        for product in products:
            product.discount_percentage = 10.0
        return products
    
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
    def get_recommendations_for_guest(session_id, limit=4):
        """Get recommendations for guest users based on session interactions"""
        # Count guest interactions
        interaction_count = GuestInteraction.query.filter_by(session_id=session_id).count()
        
        if interaction_count < 3:
            # Initial state: 50% best sellers + 50% trending
            # Use ceiling division to ensure we get enough recommendations
            best_sellers_limit = (limit + 1) // 2
            trending_limit = limit - best_sellers_limit
            
            # Get more than needed to account for duplicates
            best_sellers = AnalyticsEngine.get_best_sellers(time_window='30d', limit=best_sellers_limit * 2)
            trending = AnalyticsEngine.get_trending_products(limit=trending_limit * 2)
            
            # Remove duplicates while maintaining balance
            seen = set()
            unique_best_sellers = []
            unique_trending = []
            
            for product in best_sellers:
                if product and product.id not in seen:
                    seen.add(product.id)
                    unique_best_sellers.append(product)
                    if len(unique_best_sellers) >= best_sellers_limit:
                        break
            
            for product in trending:
                if product and product.id not in seen:
                    seen.add(product.id)
                    unique_trending.append(product)
                    if len(unique_trending) >= trending_limit:
                        break
            
            # Combine and shuffle
            recommendations = unique_best_sellers + unique_trending
            random.shuffle(recommendations)
            
            # If not enough recommendations, get more from popular products
            if len(recommendations) < limit:
                additional_needed = limit - len(recommendations)
                popular = Recommender.get_popular_products(limit=additional_needed + 10)
                for product in popular:
                    if product and product.id not in seen and len(recommendations) < limit:
                        seen.add(product.id)
                        recommendations.append(product)
            
            return Recommender._apply_recommendation_discount(recommendations[:limit])
        else:
            # After 3+ interactions: 50% cold start + 25% best sellers + 25% trending
            cold_start_limit = (limit + 1) // 2
            best_sellers_limit = (limit + 3) // 4
            trending_limit = (limit + 3) // 4
            
            # Get more than needed to account for duplicates
            cold_start_recs = Recommender._cold_start_for_guest(session_id, limit=cold_start_limit * 2)
            best_sellers = AnalyticsEngine.get_best_sellers(time_window='30d', limit=best_sellers_limit * 2)
            trending = AnalyticsEngine.get_trending_products(limit=trending_limit * 2)
            
            # Remove duplicates while maintaining balance
            seen = set()
            unique_cold_start = []
            unique_best_sellers = []
            unique_trending = []
            
            # First add cold start recommendations
            for product in cold_start_recs:
                if product and product.id not in seen:
                    seen.add(product.id)
                    unique_cold_start.append(product)
                    if len(unique_cold_start) >= cold_start_limit:
                        break
            
            # Then add best sellers
            for product in best_sellers:
                if product and product.id not in seen:
                    seen.add(product.id)
                    unique_best_sellers.append(product)
                    if len(unique_best_sellers) >= best_sellers_limit:
                        break
            
            # Finally add trending
            for product in trending:
                if product and product.id not in seen:
                    seen.add(product.id)
                    unique_trending.append(product)
                    if len(unique_trending) >= trending_limit:
                        break
            
            # Combine all unique recommendations
            unique_recommendations = unique_cold_start + unique_best_sellers + unique_trending
            
            # If not enough recommendations, get more from popular products
            if len(unique_recommendations) < limit:
                additional_needed = limit - len(unique_recommendations)
                popular = Recommender.get_popular_products(limit=additional_needed + 10)
                for product in popular:
                    if product and product.id not in seen and len(unique_recommendations) < limit:
                        seen.add(product.id)
                        unique_recommendations.append(product)
            
            return Recommender._apply_recommendation_discount(unique_recommendations[:limit])
    
    @staticmethod
    def _cold_start_for_guest(session_id, limit=5):
        """Cold start recommendations based on guest session activity with conversion optimization"""
        # Get guest's interaction history
        interactions = GuestInteraction.query.filter_by(session_id=session_id).all()
        
        if not interactions:
            return []
        
        # Extract patterns from interactions with enhanced tracking
        category_counts = defaultdict(int)
        product_interactions = defaultdict(list)  # Track all interactions per product
        price_points = []
        current_time = datetime.utcnow()
        
        # Weight different interaction types
        interaction_weights = {
            'view': 1,
            'click': 2,
            'add_to_cart': 3
        }
        
        for interaction in interactions:
            product = interaction.product
            category_counts[product.category] += 1
            
            # Calculate time decay (interactions within last 24 hours get full weight)
            time_diff = (current_time - interaction.timestamp).total_seconds() / 3600  # hours
            time_decay = max(0.5, 1.0 - (time_diff / 168))  # Decay to 50% over 7 days
            
            # Store interaction with weight and time decay
            weight = interaction_weights.get(interaction.interaction_type, 1) * time_decay
            product_interactions[product.id].append({
                'type': interaction.interaction_type,
                'weight': weight,
                'timestamp': interaction.timestamp,
                'product': product
            })
            
            if interaction.interaction_type in ['click', 'add_to_cart']:
                price_points.append(product.price)
        
        # Calculate interest scores for viewed products
        product_scores = {}
        high_interest_products = []
        low_interest_viewed = set()
        
        for product_id, interactions_list in product_interactions.items():
            total_score = sum(i['weight'] for i in interactions_list)
            product_scores[product_id] = total_score
            
            # High interest: score > 2.5 (e.g., multiple views, or view + click, or cart add)
            if total_score >= 2.5:
                high_interest_products.append({
                    'product': interactions_list[0]['product'],
                    'score': total_score
                })
            else:
                low_interest_viewed.add(product_id)
        
        # Sort high interest products by score
        high_interest_products.sort(key=lambda x: x['score'], reverse=True)
        
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
        
        # Build recommendation list with mixed strategy
        recommendations = []
        
        # 1. Add top high-interest products (30% of limit or max 2)
        high_interest_limit = min(2, max(1, int(limit * 0.3)))
        for item in high_interest_products[:high_interest_limit]:
            recommendations.append(item['product'])
        
        # 2. Find new products in preferred categories (excluding low-interest viewed)
        new_products_needed = limit - len(recommendations)
        new_products = Product.query.filter(
            and_(
                Product.category.in_(preferred_categories),
                Product.price >= price_min,
                Product.price <= price_max,
                ~Product.id.in_(low_interest_viewed),
                ~Product.id.in_([r.id for r in recommendations]),
                Product.stock_quantity > 0
            )
        ).order_by(func.random()).limit(new_products_needed * 2).all()
        
        # Add new products
        for product in new_products[:new_products_needed]:
            recommendations.append(product)
        
        # 3. If still need more, expand search without category restriction
        if len(recommendations) < limit:
            additional_needed = limit - len(recommendations)
            existing_ids = {r.id for r in recommendations}.union(low_interest_viewed)
            
            additional = Product.query.filter(
                and_(
                    Product.price >= price_min,
                    Product.price <= price_max,
                    ~Product.id.in_(existing_ids),
                    Product.stock_quantity > 0
                )
            ).order_by(func.random()).limit(additional_needed).all()
            recommendations.extend(additional)
        
        return recommendations[:limit]
    
    @staticmethod
    def get_cold_start_recommendations(user_id, limit=4):
        """Get recommendations for users with minimal data using cold start algorithm with conversion optimization"""
        # Get user interactions
        interactions = UserInteraction.query.filter_by(user_id=user_id).all()
        
        if not interactions:
            return []
        
        # Extract patterns from interactions with enhanced tracking
        category_counts = defaultdict(int)
        product_interactions = defaultdict(list)  # Track all interactions per product
        price_points = []
        current_time = datetime.utcnow()
        
        # Weight different interaction types for authenticated users
        interaction_weights = {
            'view': 1,
            'click': 2,
            'add_to_cart': 3,
            'purchase': 4  # Higher weight for purchases
        }
        
        # Check if user has purchases
        has_purchases = any(i.interaction_type == 'purchase' for i in interactions)
        
        for interaction in interactions:
            product = interaction.product
            category_counts[product.category] += 1
            
            # Calculate time decay (interactions within last 24 hours get full weight)
            time_diff = (current_time - interaction.timestamp).total_seconds() / 3600  # hours
            time_decay = max(0.5, 1.0 - (time_diff / 168))  # Decay to 50% over 7 days
            
            # Store interaction with weight and time decay
            weight = interaction_weights.get(interaction.interaction_type, 1) * time_decay
            product_interactions[product.id].append({
                'type': interaction.interaction_type,
                'weight': weight,
                'timestamp': interaction.timestamp,
                'product': product
            })
            
            if interaction.interaction_type in ['click', 'add_to_cart', 'purchase']:
                price_points.append(product.price)
        
        # Calculate interest scores for viewed products
        product_scores = {}
        high_interest_products = []
        low_interest_viewed = set()
        purchased_products = set()
        
        for product_id, interactions_list in product_interactions.items():
            total_score = sum(i['weight'] for i in interactions_list)
            product_scores[product_id] = total_score
            
            # Check if product was purchased
            if any(i['type'] == 'purchase' for i in interactions_list):
                purchased_products.add(product_id)
                continue
            
            # High interest threshold is higher for authenticated users
            if total_score >= 3.0:  # Higher threshold than guests
                high_interest_products.append({
                    'product': interactions_list[0]['product'],
                    'score': total_score
                })
            else:
                low_interest_viewed.add(product_id)
        
        # Sort high interest products by score
        high_interest_products.sort(key=lambda x: x['score'], reverse=True)
        
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
        
        # Build recommendation list with mixed strategy
        recommendations = []
        
        # 1. Add top high-interest products (25% of limit for authenticated users)
        high_interest_limit = max(1, int(limit * 0.25))
        for item in high_interest_products[:high_interest_limit]:
            recommendations.append(item['product'])
        
        # 2. Find new products in preferred categories (excluding low-interest and purchased)
        excluded_ids = low_interest_viewed.union(purchased_products)
        new_products_needed = limit - len(recommendations)
        
        new_products = Product.query.filter(
            and_(
                Product.category.in_(preferred_categories),
                Product.price >= price_min,
                Product.price <= price_max,
                ~Product.id.in_(excluded_ids),
                ~Product.id.in_([r.id for r in recommendations]),
                Product.stock_quantity > 0
            )
        ).order_by(func.random()).limit(new_products_needed * 2).all()
        
        # Add new products
        for product in new_products[:new_products_needed]:
            recommendations.append(product)
        
        # 3. If still need more, expand search without category restriction
        if len(recommendations) < limit:
            additional_needed = limit - len(recommendations)
            existing_ids = {r.id for r in recommendations}.union(excluded_ids)
            
            additional = Product.query.filter(
                and_(
                    Product.price >= price_min,
                    Product.price <= price_max,
                    ~Product.id.in_(existing_ids),
                    Product.stock_quantity > 0
                )
            ).order_by(func.random()).limit(additional_needed).all()
            recommendations.extend(additional)
        
        return Recommender._apply_recommendation_discount(recommendations[:limit])
    
    @staticmethod
    def get_recommendations_for_user(user_id, limit=4):
        """Get personalized recommendations for a user using hybrid approach"""
        # Use hybrid recommender for authenticated users
        hybrid = HybridRecommender()
        recommendations = hybrid.get_cached_recommendations(user_id, limit=limit)
        
        # Apply discount to recommendations
        return Recommender._apply_recommendation_discount(recommendations)
    
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