from flask import Blueprint, render_template, send_from_directory, jsonify, request, current_app
from flask_login import current_user, login_required
from .models import db, Product, UserInteraction, GuestInteraction, BestSeller, TrendingProduct, Category
from .recommender import Recommender
from .session_manager import SessionManager
from .offers import OfferGenerator
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
    personalized_offers = []
    
    if current_user.is_authenticated:
        # Get recommendations for authenticated users
        recommended_products = Recommender.get_recommendations_for_user(current_user.id, limit=8)
        
        # Get or generate personalized offers
        offer_generator = OfferGenerator()
        active_offers = offer_generator.refresh_user_offers(current_user.id, num_offers=4)
        
        # Create a set of product IDs with active offers
        offer_product_ids = {offer.product_id for offer in active_offers}
        
        # Prioritize products with offers in recommendations
        products_with_offers = []
        products_without_offers = []
        
        for product in recommended_products:
            if product.id in offer_product_ids:
                # Find the corresponding offer
                offer = next((o for o in active_offers if o.product_id == product.id), None)
                if offer:
                    products_with_offers.append({
                        'product': product,
                        'has_offer': True,
                        'offer': offer,
                        'final_price': offer_generator.apply_offer_to_product_price(product, current_user.id)[0]
                    })
            else:
                products_without_offers.append({
                    'product': product,
                    'has_offer': False,
                    'offer': None,
                    'final_price': product.get_discounted_price()
                })
        
        # Combine offers first, then other recommendations
        personalized_offers = (products_with_offers + products_without_offers)[:4]
        
    else:
        # Get session ID for guest recommendations
        session_id = SessionManager.get_or_create_session_id()
        recommended_products = Recommender.get_recommendations_for_guest(session_id, limit=4)
        
        # For guests, no personalized offers
        personalized_offers = [
            {
                'product': product,
                'has_offer': False,
                'offer': None,
                'final_price': product.get_discounted_price()
            }
            for product in recommended_products
        ]
    
    # Log recommendation count for debugging
    print(f"[DEBUG] Returning {len(personalized_offers)} recommendations for {'user' if current_user.is_authenticated else 'guest'}")
    
    # Get main categories for navigation
    main_categories = Category.get_main_categories()
    
    return render_template('index.html', 
                         personalized_offers=personalized_offers,
                         main_categories=main_categories)

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
    
    # Check if this is a recommendation click with discount
    rec_discount = request.args.get('rec_discount', type=float, default=0)
    if rec_discount > 0 and rec_discount <= 100:
        # Apply the recommendation discount if it's valid
        product.discount_percentage = rec_discount
    
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
    
    # Get main categories for navigation
    main_categories = Category.get_main_categories()
    
    return render_template('product.html', 
                         product=product, 
                         similar_products=similar_products,
                         main_categories=main_categories)

@main.route('/category/<slug>')
def category_view(slug):
    """View products in a specific category"""
    category = Category.query.filter_by(slug=slug).first_or_404()
    
    # Get all products in this category (including subcategories)
    products = category.get_all_products(include_subcategories=True)
    
    # Get main categories for navigation
    main_categories = Category.get_main_categories()
    
    # Get breadcrumb path
    breadcrumb = category.get_path()
    
    return render_template('category.html',
                         category=category,
                         products=products,
                         main_categories=main_categories,
                         breadcrumb=breadcrumb)

@main.route('/categories')
def categories_list():
    """Show all categories"""
    main_categories = Category.get_main_categories()
    
    # Build category tree with product counts
    category_tree = []
    for main_cat in main_categories:
        category_data = {
            'category': main_cat,
            'product_count': main_cat.get_product_count(include_subcategories=True),
            'subcategories': []
        }
        for sub_cat in main_cat.children:
            category_data['subcategories'].append({
                'category': sub_cat,
                'product_count': sub_cat.get_product_count()
            })
        category_tree.append(category_data)
    
    return render_template('categories.html',
                         category_tree=category_tree,
                         main_categories=main_categories)

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

@main.route('/deals')
def deals():
    """Display all available deals and personalized offers"""
    from .analytics import AnalyticsEngine
    
    # Get best deals (products with highest discounts)
    best_deals = Product.query.filter(
        Product.discount_percentage > 0,
        Product.stock_quantity > 0
    ).order_by(Product.discount_percentage.desc()).limit(20).all()
    
    # Get personalized offers if user is authenticated
    personalized_offers = []
    if current_user.is_authenticated:
        offer_generator = OfferGenerator()
        active_offers = offer_generator.get_active_offers(current_user.id)
        
        # Create offer items with product details
        for offer in active_offers:
            personalized_offers.append({
                'product': offer.product,
                'offer': offer,
                'final_price': offer.product.price * (1 - offer.discount_percentage / 100),
                'savings': offer.product.price * (offer.discount_percentage / 100)
            })
    
    # Get trending products with discounts
    analytics = AnalyticsEngine()
    trending = analytics.get_trending_products(limit=10)
    trending_deals = []
    
    for product in trending:
        if product.discount_percentage > 0 or product.stock_quantity < 10:
            trending_deals.append({
                'product': product,
                'is_limited_stock': product.stock_quantity < 10,
                'final_price': product.get_discounted_price()
            })
    
    return render_template('deals.html',
                         best_deals=best_deals,
                         personalized_offers=personalized_offers,
                         trending_deals=trending_deals)