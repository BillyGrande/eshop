#!/usr/bin/env python3
"""
Seed sample interactions and orders for testing analytics.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
import random
from eshop import create_app
from eshop.models import db, User, Product, Order, OrderItem, UserInteraction, GuestInteraction
from werkzeug.security import generate_password_hash

def seed_interactions():
    """Seed sample interactions and orders"""
    app = create_app()
    
    with app.app_context():
        print("Seeding sample interactions and orders...")
        
        # Create some test users
        test_users = []
        for i in range(10):
            email = f"testuser{i}@example.com"
            user = User.query.filter_by(email=email).first()
            if not user:
                user = User(email=email)
                user.set_password("password123")
                db.session.add(user)
                db.session.commit()
            test_users.append(user)
        
        # Get all products
        products = Product.query.all()
        if not products:
            print("No products found. Please run seed_products.py first.")
            return
        
        # Generate interactions for the past 30 days
        now = datetime.utcnow()
        
        # User interactions
        print("Generating user interactions...")
        for user in test_users:
            # Each user interacts with 10-30 products
            num_interactions = random.randint(10, 30)
            interacted_products = random.sample(products, min(num_interactions, len(products)))
            
            for product in interacted_products:
                # Generate multiple interaction types
                # View
                interaction_time = now - timedelta(days=random.randint(0, 30), hours=random.randint(0, 23))
                view = UserInteraction(
                    user_id=user.id,
                    product_id=product.id,
                    interaction_type='view',
                    timestamp=interaction_time
                )
                db.session.add(view)
                
                # 50% chance of click
                if random.random() < 0.5:
                    click_time = interaction_time + timedelta(minutes=random.randint(1, 5))
                    click = UserInteraction(
                        user_id=user.id,
                        product_id=product.id,
                        interaction_type='click',
                        timestamp=click_time
                    )
                    db.session.add(click)
                    
                    # 30% chance of purchase
                    if random.random() < 0.3:
                        purchase_time = click_time + timedelta(minutes=random.randint(5, 30))
                        purchase = UserInteraction(
                            user_id=user.id,
                            product_id=product.id,
                            interaction_type='purchase',
                            timestamp=purchase_time
                        )
                        db.session.add(purchase)
        
        # Guest interactions
        print("Generating guest interactions...")
        for i in range(20):
            session_id = f"guest_session_{i}"
            num_interactions = random.randint(3, 15)
            interacted_products = random.sample(products, min(num_interactions, len(products)))
            
            for product in interacted_products:
                interaction_time = now - timedelta(days=random.randint(0, 7), hours=random.randint(0, 23))
                
                # View
                view = GuestInteraction(
                    session_id=session_id,
                    product_id=product.id,
                    interaction_type='view',
                    timestamp=interaction_time
                )
                db.session.add(view)
                
                # 40% chance of click
                if random.random() < 0.4:
                    click_time = interaction_time + timedelta(minutes=random.randint(1, 5))
                    click = GuestInteraction(
                        session_id=session_id,
                        product_id=product.id,
                        interaction_type='click',
                        timestamp=click_time
                    )
                    db.session.add(click)
                    
                    # 20% chance of add to cart
                    if random.random() < 0.2:
                        cart_time = click_time + timedelta(minutes=random.randint(1, 10))
                        cart = GuestInteraction(
                            session_id=session_id,
                            product_id=product.id,
                            interaction_type='add_to_cart',
                            timestamp=cart_time
                        )
                        db.session.add(cart)
        
        # Generate orders
        print("Generating orders...")
        for user in test_users:
            # Each user has 1-5 orders
            num_orders = random.randint(1, 5)
            
            for _ in range(num_orders):
                order_time = now - timedelta(days=random.randint(0, 30), hours=random.randint(0, 23))
                
                # Create order
                order = Order(
                    user_id=user.id,
                    total=0,
                    created_at=order_time
                )
                db.session.add(order)
                db.session.flush()  # Get order ID
                
                # Add 1-5 items to order
                num_items = random.randint(1, 5)
                order_products = random.sample(products, min(num_items, len(products)))
                total = 0
                
                for product in order_products:
                    quantity = random.randint(1, 3)
                    price = product.get_discounted_price()
                    
                    order_item = OrderItem(
                        order_id=order.id,
                        product_id=product.id,
                        quantity=quantity,
                        price=price
                    )
                    db.session.add(order_item)
                    total += price * quantity
                
                # Update order total
                order.total = total
        
        db.session.commit()
        
        # Print summary
        interaction_count = UserInteraction.query.count()
        guest_interaction_count = GuestInteraction.query.count()
        order_count = Order.query.count()
        order_item_count = OrderItem.query.count()
        
        print(f"\nSeeding complete!")
        print(f"- User interactions: {interaction_count}")
        print(f"- Guest interactions: {guest_interaction_count}")
        print(f"- Orders: {order_count}")
        print(f"- Order items: {order_item_count}")

if __name__ == '__main__':
    seed_interactions()