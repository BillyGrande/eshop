from flask import Blueprint, render_template, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timezone
from .models import db, Order, OrderItem, Product
from .session_manager import SessionManager

checkout = Blueprint('checkout', __name__)

@checkout.route('/checkout')
@login_required
def checkout_page():
    """Display checkout page"""
    cart = SessionManager.get_or_create_cart(current_user)
    
    if not cart or cart.items.count() == 0:
        flash('Your cart is empty', 'warning')
        return redirect(url_for('main.home'))
    
    cart_items = cart.items.all()
    total = cart.get_total()
    
    return render_template('checkout.html', cart_items=cart_items, total=total)

@checkout.route('/checkout/process', methods=['POST'])
@login_required
def process_checkout():
    """Process the checkout and create order"""
    cart = SessionManager.get_or_create_cart(current_user)
    
    if not cart or cart.items.count() == 0:
        return jsonify({'error': 'Cart is empty'}), 400
    
    # Verify stock availability
    for item in cart.items:
        if item.product.stock_quantity < item.quantity:
            return jsonify({
                'error': f'Insufficient stock for {item.product.name}. Only {item.product.stock_quantity} available.'
            }), 400
    
    # Create order
    order = Order(
        user_id=current_user.id,
        total=cart.get_total(),
        created_at=datetime.now(timezone.utc)
    )
    db.session.add(order)
    db.session.flush()  # Get order ID
    
    # Create order items and update stock
    for cart_item in cart.items:
        # Create order item
        order_item = OrderItem(
            order_id=order.id,
            product_id=cart_item.product_id,
            quantity=cart_item.quantity,
            price=cart_item.product.get_discounted_price()
        )
        db.session.add(order_item)
        
        # Update product stock
        cart_item.product.stock_quantity -= cart_item.quantity
        
        # Track purchase interaction
        from .models import UserInteraction
        interaction = UserInteraction(
            user_id=current_user.id,
            product_id=cart_item.product_id,
            interaction_type='purchase',
            timestamp=datetime.now(timezone.utc)
        )
        db.session.add(interaction)
    
    # Clear the cart
    for item in cart.items:
        db.session.delete(item)
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'order_id': order.id,
        'redirect': url_for('checkout.order_confirmation', order_id=order.id)
    })

@checkout.route('/order/<int:order_id>')
@login_required
def order_confirmation(order_id):
    """Display order confirmation page"""
    order = Order.query.filter_by(id=order_id, user_id=current_user.id).first_or_404()
    
    return render_template('order_confirmation.html', order=order)

@checkout.route('/orders')
@login_required
def order_history():
    """Display user's order history"""
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    
    return render_template('order_history.html', orders=orders)