import uuid
from flask import session
from datetime import datetime, timezone
from .models import db, GuestInteraction, Cart

class SessionManager:
    """Manages guest sessions and transitions to authenticated users"""
    
    @staticmethod
    def get_or_create_session_id():
        """Get existing session ID or create a new one"""
        if 'session_id' not in session:
            session['session_id'] = str(uuid.uuid4())
            session.permanent = True  # Make session persist
        return session['session_id']
    
    @staticmethod
    def track_guest_interaction(product_id, interaction_type):
        """Track interactions for guest users"""
        session_id = SessionManager.get_or_create_session_id()
        
        interaction = GuestInteraction(
            session_id=session_id,
            product_id=product_id,
            interaction_type=interaction_type,
            timestamp=datetime.now(timezone.utc)
        )
        db.session.add(interaction)
        db.session.commit()
        
        return interaction
    
    @staticmethod
    def get_or_create_cart(user=None):
        """Get or create cart for current session/user"""
        if user and user.is_authenticated:
            # For authenticated users
            cart = Cart.query.filter_by(user_id=user.id).first()
            if not cart:
                cart = Cart(user_id=user.id)
                db.session.add(cart)
                db.session.commit()
        else:
            # For guest users
            session_id = SessionManager.get_or_create_session_id()
            cart = Cart.query.filter_by(session_id=session_id).first()
            if not cart:
                cart = Cart(session_id=session_id)
                db.session.add(cart)
                db.session.commit()
        
        return cart
    
    @staticmethod
    def merge_guest_data_to_user(user_id):
        """Merge guest session data when user logs in"""
        session_id = session.get('session_id')
        if not session_id:
            return
        
        # Merge guest interactions
        guest_interactions = GuestInteraction.query.filter_by(session_id=session_id).all()
        for gi in guest_interactions:
            # Check if user already has this interaction
            existing = UserInteraction.query.filter_by(
                user_id=user_id,
                product_id=gi.product_id,
                interaction_type=gi.interaction_type
            ).first()
            
            if not existing:
                # Convert guest interaction to user interaction
                from .models import UserInteraction
                user_interaction = UserInteraction(
                    user_id=user_id,
                    product_id=gi.product_id,
                    interaction_type=gi.interaction_type,
                    timestamp=gi.timestamp
                )
                db.session.add(user_interaction)
        
        # Merge guest cart
        guest_cart = Cart.query.filter_by(session_id=session_id).first()
        user_cart = Cart.query.filter_by(user_id=user_id).first()
        
        if guest_cart and guest_cart.items.count() > 0:
            if not user_cart:
                # Simply assign the guest cart to the user
                guest_cart.user_id = user_id
                guest_cart.session_id = None
            else:
                # Merge items from guest cart to user cart
                for guest_item in guest_cart.items:
                    # Check if product already in user cart
                    existing_item = user_cart.items.filter_by(
                        product_id=guest_item.product_id
                    ).first()
                    
                    if existing_item:
                        # Update quantity
                        existing_item.quantity += guest_item.quantity
                    else:
                        # Move item to user cart
                        guest_item.cart_id = user_cart.id
                
                # Delete empty guest cart
                db.session.delete(guest_cart)
        
        # Delete guest interactions after merge
        for gi in guest_interactions:
            db.session.delete(gi)
        
        db.session.commit()
        
        # Clear session ID to prevent re-merge
        session.pop('session_id', None)