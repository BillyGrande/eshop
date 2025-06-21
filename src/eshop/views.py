from flask import Blueprint, render_template, send_from_directory, jsonify, request, current_app
from flask_login import current_user, login_required
from .models import db, Product, UserInteraction, GuestInteraction, BestSeller, TrendingProduct
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
        recommended_products = Recommender.get_recommendations_for_user(current_user.id, limit=4)
    else:
        # Get session ID for guest recommendations
        session_id = SessionManager.get_or_create_session_id()
        recommended_products = Recommender.get_recommendations_for_guest(session_id, limit=4)
    
    # Log recommendation count for debugging
    print(f"[DEBUG] Returning {len(recommended_products)} recommendations for {'user' if current_user.is_authenticated else 'guest'}")
    
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

@main.route('/debug/recommendations')
def debug_recommendations():
    """Debug endpoint to check recommendation system"""
    from .session_manager import SessionManager
    from .analytics import AnalyticsEngine
    
    session_id = SessionManager.get_or_create_session_id()
    
    # Get interaction count for current session
    if current_user.is_authenticated:
        user_type = "authenticated"
        user_id = current_user.id
        interaction_count = UserInteraction.query.filter_by(user_id=user_id).count()
    else:
        user_type = "guest"
        user_id = session_id
        interaction_count = GuestInteraction.query.filter_by(session_id=session_id).count()
    
    # Get recommendations
    if current_user.is_authenticated:
        recommendations = Recommender.get_recommendations_for_user(current_user.id, limit=4)
    else:
        recommendations = Recommender.get_recommendations_for_guest(session_id, limit=4)
    
    # Get analytics data
    best_sellers = AnalyticsEngine.get_best_sellers(time_window='30d', limit=5)
    trending = AnalyticsEngine.get_trending_products(limit=5)
    
    debug_info = {
        'user_type': user_type,
        'user_id': user_id,
        'interaction_count': interaction_count,
        'recommendations_count': len(recommendations),
        'recommendations': [
            {
                'id': r.id,
                'name': r.name,
                'category': r.category,
                'price': float(r.price)
            } for r in recommendations
        ],
        'best_sellers_count': len(best_sellers),
        'trending_count': len(trending),
        'total_products': Product.query.count(),
        'analytics_status': {
            'best_sellers_cached': BestSeller.query.filter_by(category=None).count(),
            'trending_cached': TrendingProduct.query.filter_by(category=None).count()
        }
    }
    
    return jsonify(debug_info)