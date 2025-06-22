import numpy as np
from collections import defaultdict
from datetime import datetime
from .models import db, Order, OrderItem
from sqlalchemy import func


class ShoppingCartRecommender:
    """
    Shopping cart based recommendation system using association rules
    and market basket analysis to find frequently bought together items.
    """
    
    def __init__(self, min_support=2, min_confidence=0.1):
        self.min_support = min_support
        self.min_confidence = min_confidence
        
    def get_recommendations_for_cart(self, cart_product_ids, limit=10):
        """
        Simplified interface for getting cart recommendations
        Gets all products as candidates automatically
        """
        from .models import Product
        candidate_products = Product.query.all()
        return self.get_cart_recommendations(cart_product_ids, candidate_products, limit)
        
    def get_cart_recommendations(self, cart_product_ids, candidate_products, limit=10, diversify=False):
        """
        Get product recommendations based on current cart contents
        
        Args:
            cart_product_ids: List of product IDs currently in cart
            candidate_products: List of products to recommend from
            limit: Number of recommendations
            diversify: Whether to ensure category diversity
            
        Returns:
            List of recommended products
        """
        if not cart_product_ids:
            return []
        
        # Get association data
        associations, product_counts, total_orders = self._get_association_data()
        
        # Score each candidate product
        product_scores = {}
        
        for product in candidate_products:
            if product.id in cart_product_ids:
                continue  # Skip products already in cart
                
            # Calculate association score with all cart items
            total_score = 0.0
            for cart_item_id in cart_product_ids:
                score = self._calculate_association_score(
                    cart_item_id, 
                    product.id,
                    associations,
                    product_counts,
                    total_orders
                )
                total_score += score
            
            if total_score > 0:
                product_scores[product.id] = total_score
                product._cart_association_score = total_score
        
        # Sort products by score
        scored_products = []
        for product in candidate_products:
            if product.id in product_scores:
                scored_products.append((product_scores[product.id], product))
        
        scored_products.sort(key=lambda x: x[0], reverse=True)
        
        if diversify:
            return self._diversify_recommendations([p for _, p in scored_products], limit)
        else:
            return [product for _, product in scored_products[:limit]]
    
    def get_complementary_products(self, product_id, candidate_products, limit=5):
        """
        Get products that are frequently bought with a specific product
        """
        associations, product_counts, total_orders = self._get_association_data()
        
        scored_products = []
        for product in candidate_products:
            if product.id == product_id:
                continue
                
            score = self._calculate_association_score(
                product_id,
                product.id,
                associations,
                product_counts,
                total_orders
            )
            
            if score > 0:
                product._complementary_score = score
                scored_products.append((score, product))
        
        scored_products.sort(key=lambda x: x[0], reverse=True)
        return [product for _, product in scored_products[:limit]]
    
    def get_abandoned_cart_recovery(self, user_id, abandoned_items, candidate_products, limit=5):
        """
        Get recommendations to recover abandoned cart based on user history
        """
        # Get user's purchase history
        purchase_history = self._get_user_purchase_history(user_id)
        
        # Get associations
        associations, product_counts, total_orders = self._get_association_data()
        
        # Score products based on association with both history and abandoned items
        product_scores = {}
        
        for product in candidate_products:
            if product.id in abandoned_items or product.id in purchase_history:
                continue
                
            score = 0.0
            
            # Score based on abandoned items
            for item_id in abandoned_items:
                score += self._calculate_association_score(
                    item_id, product.id, associations, product_counts, total_orders
                ) * 1.5  # Weight abandoned items more
            
            # Score based on purchase history
            for item_id in purchase_history[-5:]:  # Last 5 purchases
                score += self._calculate_association_score(
                    item_id, product.id, associations, product_counts, total_orders
                )
            
            if score > 0:
                product_scores[product.id] = score
                product._recovery_score = score
        
        # Sort and return
        scored_products = [(score, p) for p in candidate_products 
                          if p.id in product_scores]
        scored_products.sort(key=lambda x: x[0], reverse=True)
        
        return [product for _, product in scored_products[:limit]]
    
    def _get_association_data(self):
        """Get product association data from order history"""
        # Get all orders with their items
        orders_data = []
        orders = db.session.query(Order).all()
        
        for order in orders:
            items = db.session.query(OrderItem.product_id).filter_by(order_id=order.id).all()
            if items:
                products = [item[0] for item in items]
                orders_data.append((order.id, products))
        
        # Build association matrix
        associations = self._build_association_matrix(orders_data)
        
        # Count product occurrences
        product_counts = defaultdict(int)
        for _, products in orders_data:
            for product_id in products:
                product_counts[product_id] += 1
        
        total_orders = len(orders_data)
        
        return associations, dict(product_counts), total_orders
    
    def _build_association_matrix(self, orders_data):
        """Build co-occurrence matrix from order data"""
        associations = defaultdict(int)
        
        for order_id, products in orders_data:
            # Count co-occurrences for all product pairs in the order
            for i, product1 in enumerate(products):
                for product2 in products[i+1:]:
                    if product1 != product2:
                        associations[(product1, product2)] += 1
                        associations[(product2, product1)] += 1
        
        return dict(associations)
    
    def _build_association_matrix_with_time_decay(self, orders_with_time):
        """Build association matrix with time decay for recency"""
        associations = defaultdict(float)
        
        current_time = datetime.utcnow()
        
        for order_id, products, order_date in orders_with_time:
            # Calculate time decay factor
            days_old = (current_time - order_date).days
            decay_factor = 1.0 / (1.0 + days_old / 30.0)  # 30-day half-life
            
            # Count co-occurrences with decay
            for i, product1 in enumerate(products):
                for product2 in products[i+1:]:
                    if product1 != product2:
                        associations[(product1, product2)] += decay_factor
                        associations[(product2, product1)] += decay_factor
        
        return dict(associations)
    
    def _calculate_association_score(self, product1_id, product2_id, 
                                   associations, product_counts, total_orders):
        """Calculate association score using confidence and lift metrics"""
        # Get co-occurrence count
        co_occurrence = associations.get((product1_id, product2_id), 0)
        
        if co_occurrence < self.min_support:
            return 0.0
        
        # Calculate confidence: P(product2 | product1)
        product1_count = product_counts.get(product1_id, 1)
        confidence = co_occurrence / product1_count
        
        if confidence < self.min_confidence:
            return 0.0
        
        # Calculate lift: confidence / P(product2)
        product2_count = product_counts.get(product2_id, 1)
        product2_probability = product2_count / max(total_orders, 1)
        lift = confidence / max(product2_probability, 0.001)
        
        # Combine metrics
        score = confidence * lift * np.log(1 + co_occurrence)
        
        return score
    
    def _get_user_purchase_history(self, user_id):
        """Get list of products user has purchased"""
        purchases = db.session.query(OrderItem.product_id).join(Order).filter(
            Order.user_id == user_id
        ).order_by(Order.created_at.desc()).all()
        
        return [p[0] for p in purchases]
    
    def _diversify_recommendations(self, products, limit):
        """Ensure category diversity in recommendations"""
        diversified = []
        categories_seen = set()
        
        # First pass: add top product from each category
        for product in products:
            if product.category not in categories_seen and len(diversified) < limit:
                diversified.append(product)
                categories_seen.add(product.category)
        
        # Second pass: fill remaining slots
        for product in products:
            if product not in diversified and len(diversified) < limit:
                diversified.append(product)
        
        return diversified
    
    def _filter_associations_by_support(self, associations):
        """Filter associations by minimum support threshold"""
        return {k: v for k, v in associations.items() if v >= self.min_support}