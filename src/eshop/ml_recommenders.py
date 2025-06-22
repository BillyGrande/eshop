import numpy as np
from sklearn.svm import LinearSVC
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from collections import defaultdict
from datetime import datetime, timedelta
from .models import db, Product, UserInteraction, Order, OrderItem, User
from sqlalchemy import func, and_
from .shopping_cart_recommender import ShoppingCartRecommender


class LinearSVMRecommender:
    """
    Linear SVM-based recommendation system that learns user preferences
    from interaction history and predicts product preferences.
    """
    
    def __init__(self):
        self.scaler = StandardScaler()
        self.feature_dimensions = None
        self.category_encoder = {}
        self.brand_encoder = {}
        
    def get_recommendations(self, user_id, candidate_products, limit=10):
        """
        Get product recommendations for a user using Linear SVM
        
        Args:
            user_id: User ID
            candidate_products: List of products to rank
            limit: Number of recommendations to return
            
        Returns:
            List of recommended products sorted by preference score
        """
        # Check if user has enough interactions
        interaction_count = UserInteraction.query.filter_by(user_id=user_id).count()
        if interaction_count < 5:
            return []  # Not enough data for SVM
        
        # Train or load model for user
        model = self._train_user_model(user_id)
        if model is None:
            return []
        
        # Get user features
        user = User.query.get(user_id)
        interactions = self._get_user_interactions(user_id)
        user_features = self._extract_user_features(user, interactions)
        
        # Score each candidate product
        scored_products = []
        for product in candidate_products:
            product_features = self._extract_product_features(product)
            feature_vector = self._create_feature_vector(user_features, product_features)
            
            # Get SVM decision score (distance from hyperplane)
            score = model.decision_function(feature_vector.reshape(1, -1))[0]
            product._svm_score = score
            scored_products.append((score, product))
        
        # Sort by score and return top products
        scored_products.sort(key=lambda x: x[0], reverse=True)
        return [product for _, product in scored_products[:limit]]
    
    def _get_user_interactions(self, user_id, days_back=90):
        """Get user interactions from the last N days"""
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)
        return UserInteraction.query.filter(
            UserInteraction.user_id == user_id,
            UserInteraction.timestamp >= cutoff_date
        ).all()
    
    def _get_user_purchases(self, user_id):
        """Get list of product IDs the user has purchased"""
        purchased_products = db.session.query(OrderItem.product_id).join(Order).filter(
            Order.user_id == user_id
        ).all()
        return [p[0] for p in purchased_products]
    
    def _extract_user_features(self, user, interactions):
        """Extract features from user's interaction history"""
        features = {
            'avg_price': 0.0,
            'category_preferences': defaultdict(float),
            'brand_preferences': defaultdict(float),
            'interaction_recency': 0.0,
            'purchase_frequency': 0.0
        }
        
        if not interactions:
            return features
        
        # Calculate average price of interacted products
        prices = []
        category_counts = defaultdict(int)
        brand_counts = defaultdict(int)
        purchase_count = 0
        
        for interaction in interactions:
            product = interaction.product
            prices.append(product.price)
            category_counts[product.category] += 1
            brand_counts[product.brand] += 1
            
            if interaction.interaction_type == 'purchase':
                purchase_count += 1
        
        features['avg_price'] = np.mean(prices) if prices else 0.0
        
        # Normalize category and brand preferences
        total_interactions = len(interactions)
        for category, count in category_counts.items():
            features['category_preferences'][category] = count / total_interactions
        
        for brand, count in brand_counts.items():
            features['brand_preferences'][brand] = count / total_interactions
        
        # Calculate interaction recency (average days since interaction)
        days_since_interactions = [
            (datetime.utcnow() - interaction.timestamp).days 
            for interaction in interactions
        ]
        features['interaction_recency'] = np.mean(days_since_interactions)
        
        # Purchase frequency
        days_since_first = (datetime.utcnow() - user.created_at).days
        features['purchase_frequency'] = purchase_count / max(days_since_first, 1)
        
        return features
    
    def _extract_product_features(self, product):
        """Extract features from a product"""
        return {
            'price': product.price,
            'category': product.category,
            'brand': product.brand,
            'tags': product.get_tags_list() if hasattr(product, 'get_tags_list') else []
        }
    
    def _create_feature_vector(self, user_features, product_features):
        """Create a numerical feature vector for SVM"""
        features = []
        
        # Price difference (normalized)
        price_diff = abs(user_features['avg_price'] - product_features['price'])
        normalized_price_diff = price_diff / max(user_features['avg_price'], 1.0)
        features.append(normalized_price_diff)
        
        # Price ratio
        price_ratio = product_features['price'] / max(user_features['avg_price'], 1.0)
        features.append(price_ratio)
        
        # Category match score
        category_score = self._calculate_category_similarity(
            user_features, 
            product_features['category']
        )
        features.append(category_score)
        
        # Brand match score
        brand_score = user_features['brand_preferences'].get(
            product_features['brand'], 
            0.0
        )
        features.append(brand_score)
        
        # Interaction recency (normalized)
        recency_score = 1.0 / (1.0 + user_features['interaction_recency'] / 30.0)
        features.append(recency_score)
        
        # Purchase frequency
        features.append(user_features['purchase_frequency'])
        
        # Product price tier (low, medium, high)
        price_tier = self._get_price_tier(product_features['price'])
        features.extend(price_tier)
        
        return np.array(features)
    
    def _calculate_category_similarity(self, user_features, product_category):
        """Calculate similarity between user preferences and product category"""
        return user_features['category_preferences'].get(product_category, 0.0)
    
    def _get_price_tier(self, price):
        """Convert price to one-hot encoded tier"""
        if price < 50:
            return [1, 0, 0]  # Low
        elif price < 150:
            return [0, 1, 0]  # Medium
        else:
            return [0, 0, 1]  # High
    
    def _train_user_model(self, user_id):
        """Train an SVM model for a specific user"""
        # Get user interactions
        interactions = self._get_user_interactions(user_id)
        if len(interactions) < 10:
            return None  # Not enough data
        
        # Get purchased products (positive examples)
        purchased_ids = set(self._get_user_purchases(user_id))
        if len(purchased_ids) < 3:
            return None  # Not enough positive examples
        
        # Prepare training data
        user = User.query.get(user_id)
        user_features = self._extract_user_features(user, interactions)
        
        X_train = []
        y_train = []
        
        # Add positive examples (purchased products)
        for interaction in interactions:
            if interaction.product_id in purchased_ids:
                product_features = self._extract_product_features(interaction.product)
                feature_vector = self._create_feature_vector(user_features, product_features)
                X_train.append(feature_vector)
                y_train.append(1)  # Positive class
        
        # Add negative examples (viewed but not purchased)
        for interaction in interactions:
            if (interaction.interaction_type == 'view' and 
                interaction.product_id not in purchased_ids):
                product_features = self._extract_product_features(interaction.product)
                feature_vector = self._create_feature_vector(user_features, product_features)
                X_train.append(feature_vector)
                y_train.append(0)  # Negative class
        
        # Balance classes if needed
        X_train = np.array(X_train)
        y_train = np.array(y_train)
        
        if len(np.unique(y_train)) < 2:
            return None  # Need both classes
        
        # Train Linear SVM
        model = LinearSVC(C=1.0, max_iter=1000, random_state=42)
        model.fit(X_train, y_train)
        
        return model


class AdvancedNeighborsRecommender:
    """
    Advanced collaborative filtering using neighbor-based approach
    with multiple similarity metrics and hybrid techniques.
    """
    
    def __init__(self, min_common_items=2, similarity_threshold=0.1):
        self.min_common_items = min_common_items
        self.similarity_threshold = similarity_threshold
        
    def get_recommendations(self, user_id, candidate_products, limit=10):
        """
        Get recommendations using advanced neighbor-based collaborative filtering
        """
        # Get user's interaction history
        user_items = self._get_user_item_interactions(user_id)
        if len(user_items) < 3:
            return []  # Not enough data
        
        # Find similar users
        similar_users = self._find_similar_users(user_id, user_items)
        if not similar_users:
            return []
        
        # Get recommendations from similar users
        recommendations = self._get_neighbor_recommendations(
            user_id, 
            similar_users, 
            candidate_products,
            limit
        )
        
        return recommendations
    
    def _get_user_item_interactions(self, user_id):
        """Get all items a user has interacted with and their scores"""
        interactions = db.session.query(
            UserInteraction.product_id,
            UserInteraction.interaction_type,
            func.count(UserInteraction.id).label('count')
        ).filter(
            UserInteraction.user_id == user_id
        ).group_by(
            UserInteraction.product_id,
            UserInteraction.interaction_type
        ).all()
        
        # Calculate weighted scores for each item
        item_scores = defaultdict(float)
        weights = {
            'view': 1.0,
            'click': 2.0,
            'add_to_cart': 3.0,
            'purchase': 5.0
        }
        
        for product_id, interaction_type, count in interactions:
            score = weights.get(interaction_type, 1.0) * count
            item_scores[product_id] += score
        
        return dict(item_scores)
    
    def _find_similar_users(self, user_id, user_items):
        """Find users similar to the target user"""
        # Get all users who have interacted with at least one common item
        common_users = db.session.query(
            UserInteraction.user_id,
            UserInteraction.product_id
        ).filter(
            UserInteraction.product_id.in_(user_items.keys()),
            UserInteraction.user_id != user_id
        ).distinct().all()
        
        # Group by user
        user_common_items = defaultdict(set)
        for other_user_id, product_id in common_users:
            user_common_items[other_user_id].add(product_id)
        
        # Calculate similarity scores
        similar_users = []
        for other_user_id, common_products in user_common_items.items():
            if len(common_products) >= self.min_common_items:
                # Get the other user's items
                other_items = self._get_user_item_interactions(other_user_id)
                
                # Calculate similarity
                similarity = self._calculate_user_similarity(
                    user_items, 
                    other_items,
                    common_products
                )
                
                if similarity >= self.similarity_threshold:
                    similar_users.append((other_user_id, similarity))
        
        # Sort by similarity
        similar_users.sort(key=lambda x: x[1], reverse=True)
        return similar_users[:50]  # Top 50 most similar users
    
    def _calculate_user_similarity(self, items1, items2, common_items):
        """Calculate similarity between two users based on their interactions"""
        # Cosine similarity on common items
        if not common_items:
            return 0.0
        
        numerator = 0.0
        sum_sq1 = 0.0
        sum_sq2 = 0.0
        
        for item in common_items:
            score1 = items1.get(item, 0.0)
            score2 = items2.get(item, 0.0)
            
            numerator += score1 * score2
            sum_sq1 += score1 ** 2
            sum_sq2 += score2 ** 2
        
        denominator = np.sqrt(sum_sq1) * np.sqrt(sum_sq2)
        if denominator == 0:
            return 0.0
        
        return numerator / denominator
    
    def _get_neighbor_recommendations(self, user_id, similar_users, candidate_products, limit):
        """Get recommendations based on similar users' preferences"""
        # Get user's existing items to exclude
        user_items = set(self._get_user_item_interactions(user_id).keys())
        
        # Aggregate scores from similar users
        product_scores = defaultdict(float)
        product_neighbor_count = defaultdict(int)
        
        candidate_ids = {p.id for p in candidate_products}
        
        for neighbor_id, similarity in similar_users:
            neighbor_items = self._get_user_item_interactions(neighbor_id)
            
            for product_id, score in neighbor_items.items():
                if product_id not in user_items and product_id in candidate_ids:
                    # Weight by similarity
                    product_scores[product_id] += score * similarity
                    product_neighbor_count[product_id] += 1
        
        # Normalize scores by number of neighbors who rated each item
        for product_id in product_scores:
            if product_neighbor_count[product_id] > 0:
                product_scores[product_id] /= product_neighbor_count[product_id]
        
        # Get products and sort by score
        scored_products = []
        for product in candidate_products:
            if product.id in product_scores:
                product._neighbor_score = product_scores[product.id]
                scored_products.append((product_scores[product.id], product))
        
        scored_products.sort(key=lambda x: x[0], reverse=True)
        return [product for _, product in scored_products[:limit]]
