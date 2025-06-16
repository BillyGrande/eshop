from flask import Blueprint, render_template, jsonify, request, redirect, url_for, flash
from flask_login import current_user
from .models import db, Product, CartItem
from .session_manager import SessionManager

cart = Blueprint('cart', __name__)

@cart.route('/cart')
def view_cart():
    """View shopping cart"""
    cart = SessionManager.get_or_create_cart(current_user)
    cart_items = cart.items.all() if cart else []
    total = cart.get_total() if cart else 0
    
    return render_template('cart.html', cart_items=cart_items, total=total)

@cart.route('/cart/add', methods=['POST'])
def add_to_cart():
    """Add product to cart"""
    data = request.get_json()
    product_id = data.get('product_id')
    quantity = data.get('quantity', 1)
    
    if not product_id:
        return jsonify({'error': 'Product ID required'}), 400
    
    product = Product.query.get(product_id)
    if not product:
        return jsonify({'error': 'Product not found'}), 404
    
    if product.stock_quantity < quantity:
        return jsonify({'error': 'Insufficient stock'}), 400
    
    # Get or create cart
    cart = SessionManager.get_or_create_cart(current_user)
    
    # Check if product already in cart
    cart_item = cart.items.filter_by(product_id=product_id).first()
    
    if cart_item:
        # Update quantity
        new_quantity = cart_item.quantity + quantity
        if new_quantity > product.stock_quantity:
            return jsonify({'error': 'Insufficient stock'}), 400
        cart_item.quantity = new_quantity
    else:
        # Add new item
        cart_item = CartItem(
            cart_id=cart.id,
            product_id=product_id,
            quantity=quantity
        )
        db.session.add(cart_item)
    
    db.session.commit()
    
    # Track add to cart interaction
    if current_user.is_authenticated:
        from .models import UserInteraction
        interaction = UserInteraction(
            user_id=current_user.id,
            product_id=product_id,
            interaction_type='add_to_cart'
        )
        db.session.add(interaction)
        db.session.commit()
    else:
        SessionManager.track_guest_interaction(product_id, 'add_to_cart')
    
    return jsonify({
        'success': True,
        'cart_count': cart.get_item_count(),
        'message': 'Product added to cart'
    })

@cart.route('/cart/update', methods=['POST'])
def update_cart_item():
    """Update cart item quantity"""
    data = request.get_json()
    cart_item_id = data.get('cart_item_id')
    quantity = data.get('quantity')
    
    if not cart_item_id or quantity is None:
        return jsonify({'error': 'Cart item ID and quantity required'}), 400
    
    cart = SessionManager.get_or_create_cart(current_user)
    cart_item = cart.items.filter_by(id=cart_item_id).first()
    
    if not cart_item:
        return jsonify({'error': 'Cart item not found'}), 404
    
    if quantity <= 0:
        # Remove item
        db.session.delete(cart_item)
    else:
        # Check stock
        if quantity > cart_item.product.stock_quantity:
            return jsonify({'error': 'Insufficient stock'}), 400
        cart_item.quantity = quantity
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'cart_count': cart.get_item_count(),
        'cart_total': cart.get_total()
    })

@cart.route('/cart/remove', methods=['POST'])
def remove_from_cart():
    """Remove item from cart"""
    data = request.get_json()
    cart_item_id = data.get('cart_item_id')
    
    if not cart_item_id:
        return jsonify({'error': 'Cart item ID required'}), 400
    
    cart = SessionManager.get_or_create_cart(current_user)
    cart_item = cart.items.filter_by(id=cart_item_id).first()
    
    if not cart_item:
        return jsonify({'error': 'Cart item not found'}), 404
    
    db.session.delete(cart_item)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'cart_count': cart.get_item_count(),
        'cart_total': cart.get_total()
    })

@cart.route('/cart/count')
def cart_count():
    """Get current cart item count"""
    cart = SessionManager.get_or_create_cart(current_user)
    count = cart.get_item_count() if cart else 0
    
    return jsonify({'count': count})