from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False, index=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Self-referential relationship
    parent = db.relationship('Category', remote_side=[id], backref='children')
    products = db.relationship('Product', backref='category_obj', lazy='dynamic')
    
    def is_main_category(self):
        """Check if this is a main category (no parent)"""
        return self.parent_id is None
    
    def get_path(self):
        """Get the full path from root to this category"""
        path = []
        current = self
        while current:
            path.insert(0, current)
            current = current.parent
        return path
    
    def get_breadcrumb(self):
        """Get breadcrumb string for display"""
        path = self.get_path()
        return " > ".join([cat.name for cat in path])
    
    def get_depth(self):
        """Get the depth of this category in the hierarchy"""
        depth = 0
        current = self
        while current.parent:
            depth += 1
            current = current.parent
        return depth
    
    def validate_depth(self, max_depth=3):
        """Validate that category depth doesn't exceed maximum"""
        if self.parent_id:
            # Calculate depth including this new category
            parent = Category.query.get(self.parent_id)
            if parent and parent.get_depth() >= max_depth - 1:
                raise ValueError(f"Category depth cannot exceed maximum depth of {max_depth}")
    
    def get_all_products(self, include_subcategories=True):
        """Get all products in this category and optionally its subcategories"""
        if not include_subcategories:
            return self.products.all()
        
        # Collect all descendant category IDs
        category_ids = [self.id]
        to_process = list(self.children)
        
        while to_process:
            child = to_process.pop(0)
            category_ids.append(child.id)
            to_process.extend(child.children)
        
        # Get all products from these categories
        return Product.query.filter(Product.category_id.in_(category_ids)).all()
    
    def get_product_count(self, include_subcategories=False):
        """Get count of products in this category"""
        if not include_subcategories:
            return self.products.count()
        return len(self.get_all_products(include_subcategories=True))
    
    @classmethod
    def get_main_categories(cls):
        """Get all main categories (no parent)"""
        return cls.query.filter_by(parent_id=None).order_by(cls.name).all()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(200))
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    orders = db.relationship('Order', backref='customer', lazy='dynamic')
    interactions = db.relationship('UserInteraction', backref='user', lazy='dynamic')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    category = db.Column(db.String(50), nullable=True, index=True)  # Keep for backward compatibility during migration
    description = db.Column(db.Text)
    image = db.Column(db.String(200))
    brand = db.Column(db.String(50))
    tags = db.Column(db.String(500))  # Comma-separated tags
    stock_quantity = db.Column(db.Integer, default=0)
    discount_percentage = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    order_items = db.relationship('OrderItem', backref='product', lazy='dynamic')
    interactions = db.relationship('UserInteraction', backref='product', lazy='dynamic')
    
    def get_tags_list(self):
        """Return tags as a list"""
        return [tag.strip() for tag in self.tags.split(',')] if self.tags else []
    
    def get_discounted_price(self):
        """Calculate price after discount"""
        if self.discount_percentage > 0:
            return self.price * (1 - self.discount_percentage / 100)
        return self.price

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    total = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    items = db.relationship('OrderItem', backref='order', lazy='dynamic')

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    price = db.Column(db.Float, nullable=False)

class UserInteraction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    interaction_type = db.Column(db.String(20), nullable=False)  # view, click, purchase
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)

class GuestInteraction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    interaction_type = db.Column(db.String(20), nullable=False)  # view, click, add_to_cart
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    product = db.relationship('Product', backref='guest_interactions')

class Cart(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    session_id = db.Column(db.String(100), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    items = db.relationship('CartItem', backref='cart', lazy='dynamic', cascade='all, delete-orphan')
    user = db.relationship('User', backref='cart')
    
    def get_total(self):
        """Calculate total cart value"""
        return sum(item.get_subtotal() for item in self.items)
    
    def get_item_count(self):
        """Get total number of items in cart"""
        return sum(item.quantity for item in self.items)

class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cart_id = db.Column(db.Integer, db.ForeignKey('cart.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    product = db.relationship('Product', backref='cart_items')
    
    def get_subtotal(self):
        """Calculate subtotal for this cart item"""
        return self.product.get_discounted_price() * self.quantity

class BestSeller(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    category = db.Column(db.String(50), nullable=True, index=True)  # NULL for overall, category for category-specific
    time_window = db.Column(db.String(20), nullable=False)  # '7d', '30d', '90d', 'all'
    sales_count = db.Column(db.Integer, default=0)
    revenue = db.Column(db.Float, default=0.0)
    rank = db.Column(db.Integer)
    last_calculated = db.Column(db.DateTime, default=datetime.utcnow)
    
    product = db.relationship('Product', backref='best_seller_entries')
    
    __table_args__ = (
        db.UniqueConstraint('product_id', 'category', 'time_window', name='_product_category_window_uc'),
        db.Index('idx_bestseller_lookup', 'time_window', 'category', 'rank'),
    )

class TrendingProduct(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    category = db.Column(db.String(50), nullable=True, index=True)  # NULL for overall, category for category-specific
    trending_score = db.Column(db.Float, default=0.0)
    view_velocity = db.Column(db.Float, default=0.0)  # views per hour
    purchase_velocity = db.Column(db.Float, default=0.0)  # purchases per hour
    cart_velocity = db.Column(db.Float, default=0.0)  # cart additions per hour
    rank = db.Column(db.Integer)
    last_calculated = db.Column(db.DateTime, default=datetime.utcnow)
    
    product = db.relationship('Product', backref='trending_entries')
    
    __table_args__ = (
        db.UniqueConstraint('product_id', 'category', name='_product_category_trending_uc'),
        db.Index('idx_trending_lookup', 'category', 'rank'),
    )

class PersonalizedOffer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    discount_percentage = db.Column(db.Float, default=10.0)  # Default 10% discount
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    is_used = db.Column(db.Boolean, default=False)
    used_at = db.Column(db.DateTime, nullable=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=True)
    
    # Relationships
    user = db.relationship('User', backref='personalized_offers')
    product = db.relationship('Product', backref='personalized_offers')
    order = db.relationship('Order', backref='personalized_offers')
    
    # Constraints to ensure one offer per product per user
    __table_args__ = (
        db.UniqueConstraint('user_id', 'product_id', name='_user_product_offer_uc'),
        db.Index('idx_offer_user_active', 'user_id', 'is_used', 'expires_at'),
    )
    
    def is_valid(self):
        """Check if offer is still valid (not used and not expired)"""
        return not self.is_used and datetime.utcnow() < self.expires_at
    
    def apply_to_order(self, order_id):
        """Mark offer as used when applied to an order"""
        self.is_used = True
        self.used_at = datetime.utcnow()
        self.order_id = order_id