from flask import Blueprint, render_template, send_from_directory, jsonify, request, current_app
from flask_login import current_user, login_required
from .models import db, Product, UserInteraction, GuestInteraction
from .recommender import Recommender
from .session_manager import SessionManager
import os

main = Blueprint('main', __name__)

@main.route('/')
def home():
    # Initialize sample products if database is empty
    if Product.query.count() == 0:
        sample_products = [
            Product(name='Premium Noise-Cancelling Wireless Headphones', price=129.99, 
                   category='Electronics', image='placeholder.jpg',
                   description='Noise-cancelling wireless headphones with premium sound quality.'),
            Product(name='Smart Fitness Watch', price=89.99,
                   category='Electronics', image='placeholder.jpg',
                   description='Track your fitness goals with this advanced smart watch.'),
            Product(name='Ultra-Portable Power Bank', price=49.99,
                   category='Electronics', image='placeholder.jpg',
                   description='20,000mAh power bank for all your charging needs.'),
            Product(name='Waterproof Bluetooth Speaker', price=79.99,
                   category='Electronics', image='placeholder.jpg',
                   description='Waterproof speaker with 360° sound.')
        ]
        db.session.add_all(sample_products)
        db.session.commit()
    
    # Get personalized recommendations
    if current_user.is_authenticated:
        recommended_products = Recommender.get_recommendations_for_user(current_user.id)
    else:
        recommended_products = Recommender.get_popular_products(4)
    
    return render_template('index.html', recommended_products=recommended_products)

@main.route('/static/images/<path:filename>')
def serve_placeholder(filename):
    # For simplicity, serve a placeholder for all image requests
    return send_from_directory(os.path.join(current_app.root_path, 'static'), 'style.css')

@main.route('/track', methods=['POST'])
def track_interaction():
    """Track user/guest interactions with products"""
    data = request.get_json()
    product_id = data.get('product_id')
    interaction_type = data.get('type', 'view')
    
    if product_id:
        if current_user.is_authenticated:
            # Track for authenticated user
            interaction = UserInteraction(
                user_id=current_user.id,
                product_id=product_id,
                interaction_type=interaction_type
            )
            db.session.add(interaction)
            db.session.commit()
        else:
            # Track for guest user
            SessionManager.track_guest_interaction(product_id, interaction_type)
    
    return jsonify({'status': 'ok'})

@main.route('/product/<int:product_id>')
def product_detail(product_id):
    """Show product details and track view"""
    product = Product.query.get_or_404(product_id)
    
    # Track view for both guests and authenticated users
    if current_user.is_authenticated:
        interaction = UserInteraction(
            user_id=current_user.id,
            product_id=product_id,
            interaction_type='view'
        )
        db.session.add(interaction)
        db.session.commit()
    else:
        SessionManager.track_guest_interaction(product_id, 'view')
    
    # Get similar products
    similar_products = Recommender.get_similar_products(product_id, limit=4)
    
    return render_template('product.html', product=product, similar_products=similar_products)