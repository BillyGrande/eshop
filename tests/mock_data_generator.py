"""
Mock data generator for comprehensive testing of recommendation system
"""

import random
from datetime import datetime, timedelta
from faker import Faker
from eshop.models import db, User, Product, Order, OrderItem, UserInteraction, GuestInteraction


class MockDataGenerator:
    """Generate realistic mock data for testing recommendation algorithms"""
    
    def __init__(self):
        self.fake = Faker()
        self.categories = ['Electronics', 'Books', 'Clothing', 'Home', 'Sports', 'Beauty', 'Toys', 'Food']
        self.brands = ['BrandA', 'BrandB', 'BrandC', 'BrandD', 'BrandE']
        self.interaction_types = ['view', 'click', 'add_to_cart', 'purchase']
        
    def generate_users(self, count=100):
        """Generate mock users with different behavior patterns"""
        users = []
        user_types = ['new', 'casual', 'regular', 'vip']
        
        for i in range(count):
            user_type = user_types[i % len(user_types)]
            user = User(
                email=f'{user_type}_{i}@test.com',
                created_at=datetime.utcnow() - timedelta(days=random.randint(1, 365))
            )
            user.set_password('password123')
            user._mock_type = user_type  # Store type for testing
            users.append(user)
            db.session.add(user)
        
        db.session.commit()
        return users
    
    def generate_products(self, count=500):
        """Generate diverse products across categories"""
        products = []
        
        for i in range(count):
            category = random.choice(self.categories)
            base_price = random.uniform(10, 500)
            
            product = Product(
                name=f'{category} Product {self.fake.word().capitalize()} {i}',
                price=round(base_price, 2),
                category=category,
                description=self.fake.text(max_nb_chars=200),
                brand=random.choice(self.brands),
                tags=','.join([f'tag{random.randint(1, 20)}' for _ in range(random.randint(2, 5))]),
                stock_quantity=random.randint(0, 1000),
                discount_percentage=0 if random.random() > 0.2 else random.choice([5, 10, 15, 20]),
                created_at=datetime.utcnow() - timedelta(days=random.randint(1, 180))
            )
            products.append(product)
            db.session.add(product)
        
        db.session.commit()
        return products
    
    def generate_interactions(self, users, products, interaction_count=5000):
        """Generate realistic user interactions based on user types"""
        interactions = []
        
        for _ in range(interaction_count):
            user = random.choice(users)
            product = random.choice(products)
            
            # Interaction probability based on user type
            if hasattr(user, '_mock_type'):
                if user._mock_type == 'new':
                    # New users mostly view
                    weights = [0.7, 0.2, 0.08, 0.02]
                elif user._mock_type == 'casual':
                    # Casual users view and click
                    weights = [0.5, 0.3, 0.15, 0.05]
                elif user._mock_type == 'regular':
                    # Regular users have balanced behavior
                    weights = [0.4, 0.3, 0.2, 0.1]
                else:  # vip
                    # VIP users purchase more
                    weights = [0.3, 0.3, 0.2, 0.2]
            else:
                weights = [0.4, 0.3, 0.2, 0.1]
            
            interaction_type = random.choices(self.interaction_types, weights=weights)[0]
            
            interaction = UserInteraction(
                user_id=user.id,
                product_id=product.id,
                interaction_type=interaction_type,
                timestamp=datetime.utcnow() - timedelta(
                    days=random.randint(0, 30),
                    hours=random.randint(0, 23),
                    minutes=random.randint(0, 59)
                )
            )
            interactions.append(interaction)
            db.session.add(interaction)
        
        db.session.commit()
        return interactions
    
    def generate_orders_with_patterns(self, users, products, order_count=200):
        """Generate orders with realistic buying patterns"""
        orders = []
        
        # Define product bundles (frequently bought together)
        bundles = [
            # Electronics bundles
            ['laptop', 'mouse', 'keyboard'],
            ['phone', 'case', 'charger'],
            ['camera', 'memory_card', 'bag'],
            # Clothing bundles
            ['shirt', 'pants', 'shoes'],
            ['dress', 'heels', 'purse'],
            # Home bundles
            ['sofa', 'cushions', 'throw'],
            ['bed', 'sheets', 'pillows']
        ]
        
        for _ in range(order_count):
            user = random.choice([u for u in users if hasattr(u, '_mock_type') and u._mock_type in ['regular', 'vip']])
            
            # 30% chance of buying a bundle
            if random.random() < 0.3 and len(products) > 3:
                # Select 2-4 related products
                num_items = random.randint(2, 4)
                # Products from same category are more likely to be bought together
                category = random.choice(self.categories)
                category_products = [p for p in products if p.category == category]
                if len(category_products) >= num_items:
                    order_products = random.sample(category_products, num_items)
                else:
                    order_products = random.sample(products, num_items)
            else:
                # Random selection
                num_items = random.randint(1, 5)
                order_products = random.sample(products, num_items)
            
            order = Order(
                user_id=user.id,
                total=sum(p.get_discounted_price() for p in order_products),
                created_at=datetime.utcnow() - timedelta(days=random.randint(0, 60))
            )
            db.session.add(order)
            db.session.flush()
            
            for product in order_products:
                order_item = OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    quantity=random.randint(1, 3),
                    price=product.get_discounted_price()
                )
                db.session.add(order_item)
            
            orders.append(order)
        
        db.session.commit()
        return orders
    
    def generate_guest_sessions(self, products, session_count=50):
        """Generate guest user sessions with interactions"""
        sessions = []
        
        for i in range(session_count):
            session_id = f'guest-session-{i}-{self.fake.uuid4()}'
            
            # Guest users typically have fewer interactions
            num_interactions = random.randint(1, 10)
            
            # Guests often browse within a category
            if random.random() < 0.7:
                category = random.choice(self.categories)
                category_products = [p for p in products if p.category == category]
                session_products = random.sample(
                    category_products if len(category_products) >= num_interactions else products,
                    min(num_interactions, len(category_products))
                )
            else:
                session_products = random.sample(products, num_interactions)
            
            for j, product in enumerate(session_products):
                # Guests mostly view and click
                interaction_type = random.choices(
                    ['view', 'click', 'add_to_cart'],
                    weights=[0.6, 0.3, 0.1]
                )[0]
                
                interaction = GuestInteraction(
                    session_id=session_id,
                    product_id=product.id,
                    interaction_type=interaction_type,
                    timestamp=datetime.utcnow() - timedelta(minutes=num_interactions-j)
                )
                db.session.add(interaction)
                sessions.append(interaction)
        
        db.session.commit()
        return sessions
    
    def generate_complete_test_dataset(self):
        """Generate a complete dataset for testing"""
        print("Generating users...")
        users = self.generate_users(100)
        
        print("Generating products...")
        products = self.generate_products(500)
        
        print("Generating interactions...")
        interactions = self.generate_interactions(users, products, 5000)
        
        print("Generating orders...")
        orders = self.generate_orders_with_patterns(users, products, 200)
        
        print("Generating guest sessions...")
        guest_sessions = self.generate_guest_sessions(products, 50)
        
        return {
            'users': users,
            'products': products,
            'interactions': interactions,
            'orders': orders,
            'guest_sessions': guest_sessions
        }


class RecommendationMetrics:
    """Calculate metrics for recommendation quality"""
    
    @staticmethod
    def calculate_precision_at_k(recommendations, relevant_items, k=10):
        """Calculate precision@k metric"""
        if not recommendations:
            return 0.0
        
        recommendations_k = recommendations[:k]
        relevant_in_recs = sum(1 for r in recommendations_k if r.id in relevant_items)
        
        return relevant_in_recs / min(k, len(recommendations_k))
    
    @staticmethod
    def calculate_recall_at_k(recommendations, relevant_items, k=10):
        """Calculate recall@k metric"""
        if not relevant_items:
            return 0.0
        
        recommendations_k = recommendations[:k]
        relevant_in_recs = sum(1 for r in recommendations_k if r.id in relevant_items)
        
        return relevant_in_recs / len(relevant_items)
    
    @staticmethod
    def calculate_diversity(recommendations):
        """Calculate category diversity of recommendations"""
        if not recommendations:
            return 0.0
        
        categories = [r.category for r in recommendations]
        unique_categories = len(set(categories))
        
        return unique_categories / len(categories)
    
    @staticmethod
    def calculate_coverage(recommendations, all_products):
        """Calculate catalog coverage"""
        if not all_products:
            return 0.0
        
        recommended_ids = {r.id for r in recommendations}
        all_product_ids = {p.id for p in all_products}
        
        return len(recommended_ids) / len(all_product_ids)