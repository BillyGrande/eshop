from datetime import datetime, timedelta
from sqlalchemy import and_, not_, exists
from .models import db, PersonalizedOffer, Product, UserInteraction, Order, OrderItem
from .recommender import Recommender

class OfferGenerator:
    """Generate personalized offers for users based on their behavior and preferences"""
    
    def __init__(self, offer_duration_days=7, discount_percentage=10.0):
        self.offer_duration_days = offer_duration_days
        self.discount_percentage = discount_percentage
        self.recommender = Recommender()
    
    def generate_offers_for_user(self, user_id, num_offers=4):
        """
        Generate personalized offers for a user
        
        Args:
            user_id: The user to generate offers for
            num_offers: Number of offers to generate (default 4)
            
        Returns:
            List of PersonalizedOffer objects
        """
        # Get products that don't already have offers for this user
        existing_offers_subquery = db.session.query(PersonalizedOffer.product_id).filter(
            PersonalizedOffer.user_id == user_id
        ).subquery()
        
        # Get products that the user hasn't purchased
        purchased_products_subquery = db.session.query(OrderItem.product_id).join(Order).filter(
            Order.user_id == user_id
        ).subquery()
        
        # Get recommended products excluding existing offers and purchased items
        recommended_products = Recommender.get_recommendations_for_user(
            user_id=user_id,
            limit=num_offers * 3  # Get extra to account for filtering
        )
        
        # Filter out products with existing offers or that were purchased
        eligible_products = []
        for product in recommended_products:
            if (not db.session.query(exists().where(
                and_(
                    PersonalizedOffer.user_id == user_id,
                    PersonalizedOffer.product_id == product.id
                )
            )).scalar() and
                not db.session.query(exists().where(
                    and_(
                        OrderItem.product_id == product.id,
                        Order.id == OrderItem.order_id,
                        Order.user_id == user_id
                    )
                )).scalar()):
                eligible_products.append(product)
                if len(eligible_products) >= num_offers:
                    break
        
        # Create offers for eligible products
        offers = []
        expires_at = datetime.utcnow() + timedelta(days=self.offer_duration_days)
        
        for product in eligible_products:
            offer = PersonalizedOffer(
                user_id=user_id,
                product_id=product.id,
                discount_percentage=self.discount_percentage,
                expires_at=expires_at
            )
            db.session.add(offer)
            offers.append(offer)
        
        if offers:
            db.session.commit()
        
        return offers
    
    def get_active_offers_for_user(self, user_id):
        """
        Get all active (valid) offers for a user
        
        Args:
            user_id: The user ID
            
        Returns:
            List of PersonalizedOffer objects with product relationship loaded
        """
        return PersonalizedOffer.query.join(Product).filter(
            PersonalizedOffer.user_id == user_id,
            PersonalizedOffer.is_used == False,
            PersonalizedOffer.expires_at > datetime.utcnow()
        ).options(db.joinedload(PersonalizedOffer.product)).all()
    
    def get_active_offers(self, user_id):
        """
        Alias for get_active_offers_for_user for compatibility
        """
        return self.get_active_offers_for_user(user_id)
    
    def apply_offer_to_product_price(self, product, user_id):
        """
        Apply any active offer to a product's price for a specific user
        
        Args:
            product: Product object
            user_id: User ID
            
        Returns:
            Tuple of (final_price, offer_applied)
        """
        # Check if there's an active offer for this product and user
        offer = PersonalizedOffer.query.filter(
            PersonalizedOffer.user_id == user_id,
            PersonalizedOffer.product_id == product.id,
            PersonalizedOffer.is_used == False,
            PersonalizedOffer.expires_at > datetime.utcnow()
        ).first()
        
        if offer:
            # Apply personalized offer discount on top of any existing product discount
            base_price = product.get_discounted_price()
            offer_discount = base_price * (offer.discount_percentage / 100)
            final_price = base_price - offer_discount
            return final_price, offer
        
        return product.get_discounted_price(), None
    
    def cleanup_expired_offers(self):
        """Remove expired offers from the database"""
        expired_offers = PersonalizedOffer.query.filter(
            PersonalizedOffer.expires_at <= datetime.utcnow(),
            PersonalizedOffer.is_used == False
        ).all()
        
        for offer in expired_offers:
            db.session.delete(offer)
        
        db.session.commit()
        return len(expired_offers)
    
    def refresh_user_offers(self, user_id, num_offers=4):
        """
        Refresh offers for a user by generating new ones if they have less than the target number
        
        Args:
            user_id: User ID
            num_offers: Target number of active offers
            
        Returns:
            List of all active offers for the user
        """
        # Get current active offers
        active_offers = self.get_active_offers_for_user(user_id)
        
        # Generate new offers if needed
        current_count = len(active_offers)
        if current_count < num_offers:
            new_offers_needed = num_offers - current_count
            self.generate_offers_for_user(user_id, new_offers_needed)
            
            # Refresh the list
            active_offers = self.get_active_offers_for_user(user_id)
        
        return active_offers