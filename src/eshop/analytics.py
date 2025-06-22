from datetime import datetime, timedelta
from sqlalchemy import func, and_, or_
from collections import defaultdict
import math

from .models import db, Product, Order, OrderItem, UserInteraction, GuestInteraction, BestSeller, TrendingProduct
from .recommendation_cache import cached_recommendation


class AnalyticsEngine:
    
    @staticmethod
    def calculate_best_sellers(time_window='30d', top_n=50):
        """
        Calculate best-selling products based on order history.
        
        Args:
            time_window: '7d', '30d', '90d', or 'all'
            top_n: Number of top products to return
        """
        # Calculate time threshold
        now = datetime.utcnow()
        if time_window == '7d':
            start_date = now - timedelta(days=7)
        elif time_window == '30d':
            start_date = now - timedelta(days=30)
        elif time_window == '90d':
            start_date = now - timedelta(days=90)
        else:  # 'all'
            start_date = datetime(2000, 1, 1)  # Effectively no limit
        
        # Query for overall best sellers
        sales_data = db.session.query(
            OrderItem.product_id,
            func.sum(OrderItem.quantity).label('sales_count'),
            func.sum(OrderItem.quantity * OrderItem.price).label('revenue')
        ).join(
            Order, OrderItem.order_id == Order.id
        ).filter(
            Order.created_at >= start_date
        ).group_by(
            OrderItem.product_id
        ).order_by(
            func.sum(OrderItem.quantity).desc()
        ).limit(top_n).all()
        
        # Clear existing entries for this time window
        BestSeller.query.filter_by(time_window=time_window, category=None).delete()
        
        # Insert new best sellers
        for rank, (product_id, sales_count, revenue) in enumerate(sales_data, 1):
            best_seller = BestSeller(
                product_id=product_id,
                category=None,  # Overall best sellers
                time_window=time_window,
                sales_count=sales_count,
                revenue=revenue,
                rank=rank,
                last_calculated=now
            )
            db.session.add(best_seller)
        
        # Calculate category-specific best sellers
        categories = db.session.query(Product.category).distinct().all()
        for (category,) in categories:
            category_sales = db.session.query(
                OrderItem.product_id,
                func.sum(OrderItem.quantity).label('sales_count'),
                func.sum(OrderItem.quantity * OrderItem.price).label('revenue')
            ).join(
                Order, OrderItem.order_id == Order.id
            ).join(
                Product, OrderItem.product_id == Product.id
            ).filter(
                and_(
                    Order.created_at >= start_date,
                    Product.category == category
                )
            ).group_by(
                OrderItem.product_id
            ).order_by(
                func.sum(OrderItem.quantity).desc()
            ).limit(20).all()  # Top 20 per category
            
            # Clear existing category entries
            BestSeller.query.filter_by(time_window=time_window, category=category).delete()
            
            # Insert category best sellers
            for rank, (product_id, sales_count, revenue) in enumerate(category_sales, 1):
                best_seller = BestSeller(
                    product_id=product_id,
                    category=category,
                    time_window=time_window,
                    sales_count=sales_count,
                    revenue=revenue,
                    rank=rank,
                    last_calculated=now
                )
                db.session.add(best_seller)
        
        db.session.commit()
    
    @staticmethod
    def calculate_trending_products(hours_window=24, top_n=50):
        """
        Calculate trending products based on recent interaction velocity.
        
        Args:
            hours_window: Number of hours to look back for calculating velocity
            top_n: Number of top trending products to return
        """
        now = datetime.utcnow()
        start_time = now - timedelta(hours=hours_window)
        
        # Aggregate all interactions (both user and guest)
        interaction_data = defaultdict(lambda: {'views': 0, 'clicks': 0, 'carts': 0, 'purchases': 0})
        
        # User interactions
        user_interactions = db.session.query(
            UserInteraction.product_id,
            UserInteraction.interaction_type,
            func.count(UserInteraction.id).label('count')
        ).filter(
            UserInteraction.timestamp >= start_time
        ).group_by(
            UserInteraction.product_id,
            UserInteraction.interaction_type
        ).all()
        
        for product_id, interaction_type, count in user_interactions:
            if interaction_type == 'view':
                interaction_data[product_id]['views'] += count
            elif interaction_type == 'click':
                interaction_data[product_id]['clicks'] += count
            elif interaction_type == 'purchase':
                interaction_data[product_id]['purchases'] += count
        
        # Guest interactions
        guest_interactions = db.session.query(
            GuestInteraction.product_id,
            GuestInteraction.interaction_type,
            func.count(GuestInteraction.id).label('count')
        ).filter(
            GuestInteraction.timestamp >= start_time
        ).group_by(
            GuestInteraction.product_id,
            GuestInteraction.interaction_type
        ).all()
        
        for product_id, interaction_type, count in guest_interactions:
            if interaction_type == 'view':
                interaction_data[product_id]['views'] += count
            elif interaction_type == 'click':
                interaction_data[product_id]['clicks'] += count
            elif interaction_type == 'add_to_cart':
                interaction_data[product_id]['carts'] += count
        
        # Calculate trending scores with time decay
        trending_scores = []
        for product_id, data in interaction_data.items():
            # Calculate velocities (per hour)
            view_velocity = data['views'] / hours_window
            click_velocity = data['clicks'] / hours_window
            cart_velocity = data['carts'] / hours_window
            purchase_velocity = data['purchases'] / hours_window
            
            # Calculate weighted trending score
            # Purchases are most important, followed by cart adds, clicks, then views
            trending_score = (
                view_velocity * 1.0 +
                click_velocity * 2.0 +
                cart_velocity * 5.0 +
                purchase_velocity * 10.0
            )
            
            # Apply time decay boost for very recent interactions
            recent_boost = AnalyticsEngine._calculate_recency_boost(product_id, hours=6)
            trending_score *= recent_boost
            
            trending_scores.append({
                'product_id': product_id,
                'trending_score': trending_score,
                'view_velocity': view_velocity,
                'purchase_velocity': purchase_velocity,
                'cart_velocity': cart_velocity
            })
        
        # Sort by trending score
        trending_scores.sort(key=lambda x: x['trending_score'], reverse=True)
        
        # Clear existing trending entries
        TrendingProduct.query.filter_by(category=None).delete()
        
        # Insert overall trending products
        for rank, item in enumerate(trending_scores[:top_n], 1):
            trending = TrendingProduct(
                product_id=item['product_id'],
                category=None,
                trending_score=item['trending_score'],
                view_velocity=item['view_velocity'],
                purchase_velocity=item['purchase_velocity'],
                cart_velocity=item['cart_velocity'],
                rank=rank,
                last_calculated=now
            )
            db.session.add(trending)
        
        # Calculate category-specific trending
        categories = db.session.query(Product.category).distinct().all()
        for (category,) in categories:
            # Get products in this category
            category_products = {p_id for (p_id,) in db.session.query(Product.id).filter_by(category=category).all()}
            
            # Filter trending scores for this category
            category_trending = [item for item in trending_scores if item['product_id'] in category_products]
            
            # Clear existing category trending entries
            TrendingProduct.query.filter_by(category=category).delete()
            
            # Insert category trending products
            for rank, item in enumerate(category_trending[:20], 1):  # Top 20 per category
                trending = TrendingProduct(
                    product_id=item['product_id'],
                    category=category,
                    trending_score=item['trending_score'],
                    view_velocity=item['view_velocity'],
                    purchase_velocity=item['purchase_velocity'],
                    cart_velocity=item['cart_velocity'],
                    rank=rank,
                    last_calculated=now
                )
                db.session.add(trending)
        
        db.session.commit()
    
    @staticmethod
    def _calculate_recency_boost(product_id, hours=6):
        """
        Calculate a recency boost factor based on very recent interactions.
        """
        now = datetime.utcnow()
        recent_threshold = now - timedelta(hours=hours)
        
        # Count very recent interactions
        recent_count = db.session.query(func.count()).select_from(
            db.union(
                db.session.query(UserInteraction.id).filter(
                    and_(
                        UserInteraction.product_id == product_id,
                        UserInteraction.timestamp >= recent_threshold
                    )
                ),
                db.session.query(GuestInteraction.id).filter(
                    and_(
                        GuestInteraction.product_id == product_id,
                        GuestInteraction.timestamp >= recent_threshold
                    )
                )
            ).subquery()
        ).scalar()
        
        # Apply logarithmic boost (diminishing returns)
        if recent_count > 0:
            return 1.0 + math.log(1 + recent_count) * 0.1
        return 1.0
    
    @staticmethod
    @cached_recommendation(ttl=1800)  # Cache for 30 minutes
    def get_best_sellers(time_window='30d', category=None, limit=10):
        """
        Retrieve best sellers from cache.
        """
        query = BestSeller.query.filter_by(
            time_window=time_window,
            category=category
        ).order_by(BestSeller.rank)
        
        if limit:
            query = query.limit(limit)
        
        return [bs.product for bs in query.all()]
    
    @staticmethod
    @cached_recommendation(ttl=900)  # Cache for 15 minutes
    def get_trending_products(category=None, limit=10):
        """
        Retrieve trending products from cache.
        """
        query = TrendingProduct.query.filter_by(
            category=category
        ).order_by(TrendingProduct.rank)
        
        if limit:
            query = query.limit(limit)
        
        return [tp.product for tp in query.all()]
    
    @staticmethod
    def update_analytics():
        """
        Update all analytics (best sellers and trending).
        Should be called periodically (e.g., hourly via cron job).
        """
        # Update best sellers for different time windows
        for window in ['7d', '30d', '90d', 'all']:
            AnalyticsEngine.calculate_best_sellers(time_window=window)
        
        # Update trending products
        AnalyticsEngine.calculate_trending_products(hours_window=24)
        
        print(f"Analytics updated at {datetime.utcnow()}")