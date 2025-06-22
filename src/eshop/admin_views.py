from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from functools import wraps
from .models import db, Product, Category, User, Order
from .forms import ProductForm
import os
from werkzeug.utils import secure_filename

admin = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            flash('Access denied. Admin privileges required.', 'error')
            return redirect(url_for('main.home'))
        return f(*args, **kwargs)
    return decorated_function

@admin.route('/')
@admin_required
def dashboard():
    stats = {
        'total_products': Product.query.count(),
        'total_users': User.query.count(),
        'total_orders': Order.query.count(),
        'total_categories': Category.query.count()
    }
    return render_template('admin/dashboard.html', stats=stats)

@admin.route('/products')
@admin_required
def products():
    page = request.args.get('page', 1, type=int)
    products = Product.query.paginate(page=page, per_page=20, error_out=False)
    return render_template('admin/products.html', products=products)

@admin.route('/products/add', methods=['GET', 'POST'])
@admin_required
def add_product():
    form = ProductForm()
    form.category_id.choices = [(c.id, c.get_breadcrumb()) for c in Category.query.order_by(Category.name).all()]
    
    if form.validate_on_submit():
        product = Product(
            name=form.name.data,
            price=form.price.data,
            category_id=form.category_id.data,
            description=form.description.data,
            brand=form.brand.data,
            tags=form.tags.data,
            stock_quantity=form.stock_quantity.data,
            discount_percentage=form.discount_percentage.data
        )
        
        # Handle image upload
        if form.image.data:
            filename = secure_filename(form.image.data.filename)
            # Create upload directory if it doesn't exist
            upload_path = os.path.join(current_app.root_path, 'static', 'uploads', 'products')
            os.makedirs(upload_path, exist_ok=True)
            
            # Save the file
            filepath = os.path.join(upload_path, filename)
            form.image.data.save(filepath)
            product.image = f'uploads/products/{filename}'
        else:
            product.image = 'placeholder.jpg'
        
        db.session.add(product)
        db.session.commit()
        
        flash(f'Product "{product.name}" has been added successfully!', 'success')
        return redirect(url_for('admin.products'))
    
    return render_template('admin/product_form.html', form=form, title='Add Product')

@admin.route('/products/edit/<int:id>', methods=['GET', 'POST'])
@admin_required
def edit_product(id):
    product = Product.query.get_or_404(id)
    form = ProductForm(obj=product)
    form.category_id.choices = [(c.id, c.get_breadcrumb()) for c in Category.query.order_by(Category.name).all()]
    
    if form.validate_on_submit():
        product.name = form.name.data
        product.price = form.price.data
        product.category_id = form.category_id.data
        product.description = form.description.data
        product.brand = form.brand.data
        product.tags = form.tags.data
        product.stock_quantity = form.stock_quantity.data
        product.discount_percentage = form.discount_percentage.data
        
        # Handle image upload
        if form.image.data:
            filename = secure_filename(form.image.data.filename)
            upload_path = os.path.join(current_app.root_path, 'static', 'uploads', 'products')
            os.makedirs(upload_path, exist_ok=True)
            
            filepath = os.path.join(upload_path, filename)
            form.image.data.save(filepath)
            product.image = f'uploads/products/{filename}'
        
        db.session.commit()
        flash(f'Product "{product.name}" has been updated successfully!', 'success')
        return redirect(url_for('admin.products'))
    
    return render_template('admin/product_form.html', form=form, title='Edit Product', product=product)

@admin.route('/products/delete/<int:id>', methods=['POST'])
@admin_required
def delete_product(id):
    product = Product.query.get_or_404(id)
    product_name = product.name
    
    db.session.delete(product)
    db.session.commit()
    
    flash(f'Product "{product_name}" has been deleted successfully!', 'success')
    return redirect(url_for('admin.products'))

@admin.route('/categories')
@admin_required
def categories():
    categories = Category.query.order_by(Category.name).all()
    return render_template('admin/categories.html', categories=categories)

@admin.route('/users')
@admin_required
def users():
    page = request.args.get('page', 1, type=int)
    users = User.query.paginate(page=page, per_page=20, error_out=False)
    return render_template('admin/users.html', users=users)

@admin.route('/orders')
@admin_required
def orders():
    page = request.args.get('page', 1, type=int)
    orders = Order.query.order_by(Order.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template('admin/orders.html', orders=orders)