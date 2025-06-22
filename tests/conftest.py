"""
Pytest configuration and fixtures for recommendation system testing
"""

import pytest
import tempfile
import os
import sys
from datetime import datetime, timedelta

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from eshop import create_app
from eshop.models import db, User, Product, Order, OrderItem, UserInteraction, GuestInteraction, Category
from eshop.analytics import AnalyticsEngine


@pytest.fixture
def app():
    """Create and configure a test Flask application"""
    # Create a temporary database file
    db_fd, db_path = tempfile.mkstemp()
    
    # Create app with test config
    app = create_app()
    app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{db_path}',
        'SECRET_KEY': 'test-secret-key',
        'WTF_CSRF_ENABLED': False
    })
    
    with app.app_context():
        db.create_all()
        yield app
        
    # Clean up
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    """Create a test client for the Flask application"""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create a test CLI runner"""
    return app.test_cli_runner()


@pytest.fixture
def sample_users(app):
    """Create sample users for testing"""
    with app.app_context():
        users = [
            User(email='newuser@test.com'),  # New user with no interactions
            User(email='casual@test.com'),    # Casual user with some interactions
            User(email='active@test.com'),    # Active user with many interactions
            User(email='vip@test.com')        # VIP user with purchase history
        ]
        
        for user in users:
            user.set_password('password123')
            db.session.add(user)
        
        db.session.commit()
        return users


@pytest.fixture
def sample_products(app):
    """Create sample products across different categories"""
    with app.app_context():
        categories = ['Electronics', 'Books', 'Clothing', 'Home', 'Sports']
        products = []
        
        for i in range(50):
            product = Product(
                name=f'Product {i+1}',
                price=10.0 + (i * 5) % 200,
                category=categories[i % len(categories)],
                description=f'Description for product {i+1}',
                brand=f'Brand{i % 5}',
                tags=f'tag{i % 3},tag{i % 4}',
                stock_quantity=100 - (i % 10) * 10,
                discount_percentage=0 if i % 5 else 10  # Every 5th product has discount
            )
            products.append(product)
            db.session.add(product)
        
        db.session.commit()
        return products


@pytest.fixture
def sample_interactions(app, sample_users, sample_products):
    """Create sample user interactions for different user segments"""
    with app.app_context():
        interactions = []
        
        # New user - no interactions
        # (User 0 has no interactions)
        
        # Casual user - 8 interactions
        for i in range(8):
            interaction = UserInteraction(
                user_id=sample_users[1].id,
                product_id=sample_products[i].id,
                interaction_type=['view', 'click', 'view'][i % 3],
                timestamp=datetime.utcnow() - timedelta(days=i)
            )
            interactions.append(interaction)
            db.session.add(interaction)
        
        # Active user - 25 interactions with some purchases
        for i in range(25):
            interaction = UserInteraction(
                user_id=sample_users[2].id,
                product_id=sample_products[i % 20].id,
                interaction_type=['view', 'click', 'purchase', 'add_to_cart'][i % 4],
                timestamp=datetime.utcnow() - timedelta(days=i//2)
            )
            interactions.append(interaction)
            db.session.add(interaction)
        
        # VIP user - 50+ interactions with many purchases
        for i in range(50):
            interaction = UserInteraction(
                user_id=sample_users[3].id,
                product_id=sample_products[i % 30].id,
                interaction_type=['view', 'click', 'purchase', 'purchase'][i % 4],
                timestamp=datetime.utcnow() - timedelta(days=i//3)
            )
            interactions.append(interaction)
            db.session.add(interaction)
        
        db.session.commit()
        return interactions


@pytest.fixture
def sample_orders(app, sample_users, sample_products):
    """Create sample orders for testing shopping cart recommendations"""
    with app.app_context():
        orders = []
        
        # Create orders with common product combinations
        order_patterns = [
            [0, 1, 2],      # Products often bought together
            [0, 1, 3],      # Another combination with product 0 and 1
            [1, 2, 4],      # Products 1 and 2 appear in multiple orders
            [5, 6, 7],      # Different product set
            [0, 5, 8],      # Cross-category purchase
            [1, 2, 3, 4],   # Larger order
        ]
        
        for i, pattern in enumerate(order_patterns):
            order = Order(
                user_id=sample_users[2 + i % 2].id,  # Alternate between active and VIP users
                total=sum(sample_products[p].price for p in pattern),
                created_at=datetime.utcnow() - timedelta(days=30-i*5)
            )
            db.session.add(order)
            db.session.flush()
            
            for product_idx in pattern:
                order_item = OrderItem(
                    order_id=order.id,
                    product_id=sample_products[product_idx].id,
                    quantity=1,
                    price=sample_products[product_idx].price
                )
                db.session.add(order_item)
            
            orders.append(order)
        
        db.session.commit()
        return orders


@pytest.fixture
def analytics_engine(app, sample_orders):
    """Initialize analytics engine with sample data"""
    with app.app_context():
        engine = AnalyticsEngine()
        engine.update_analytics()  # Calculate best sellers and trending
        return engine


@pytest.fixture
def authenticated_client(client, sample_users):
    """Create a test client with authenticated user"""
    # Login as active user
    client.post('/login', data={
        'email': 'active@test.com',
        'password': 'password123'
    })
    return client


@pytest.fixture
def mock_session_id():
    """Generate a mock session ID for guest testing"""
    return 'test-session-12345'