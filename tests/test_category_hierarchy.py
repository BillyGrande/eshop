"""
Tests for product category hierarchy functionality
"""

import pytest
from eshop.models import db, Product, Category


@pytest.fixture(autouse=True)
def clean_db(app):
    """Clean up database before each test"""
    with app.app_context():
        # Clean up existing data
        Product.query.delete()
        Category.query.delete()
        db.session.commit()
        yield
        # Cleanup after test
        Product.query.delete()
        Category.query.delete()
        db.session.commit()


class TestCategoryHierarchy:
    """Test category hierarchy implementation"""
    
    def test_create_main_category(self, app):
        """Test creating a main category"""
        with app.app_context():
            category = Category(name="Electronics", slug="electronics")
            db.session.add(category)
            db.session.commit()
            
            assert category.id is not None
            assert category.name == "Electronics"
            assert category.slug == "electronics"
            assert category.parent_id is None
            assert category.is_main_category() is True
    
    def test_create_subcategory(self, app):
        """Test creating a subcategory with parent"""
        with app.app_context():
            # Create parent category
            parent = Category(name="Electronics", slug="electronics")
            db.session.add(parent)
            db.session.commit()
            
            # Create subcategory
            subcategory = Category(
                name="Smartphones",
                slug="smartphones",
                parent_id=parent.id
            )
            db.session.add(subcategory)
            db.session.commit()
            
            assert subcategory.parent_id == parent.id
            assert subcategory.parent.name == "Electronics"
            assert subcategory.is_main_category() is False
            assert subcategory.id in [c.id for c in parent.children]
    
    def test_category_path(self, app):
        """Test getting full category path"""
        with app.app_context():
            # Create hierarchy: Electronics > Smartphones > Android
            electronics = Category(name="Electronics", slug="electronics")
            db.session.add(electronics)
            db.session.commit()
            
            smartphones = Category(
                name="Smartphones",
                slug="smartphones",
                parent_id=electronics.id
            )
            db.session.add(smartphones)
            db.session.commit()
            
            android = Category(
                name="Android",
                slug="android",
                parent_id=smartphones.id
            )
            db.session.add(android)
            db.session.commit()
            
            path = android.get_path()
            assert len(path) == 3
            assert path[0].name == "Electronics"
            assert path[1].name == "Smartphones"
            assert path[2].name == "Android"
            
            breadcrumb = android.get_breadcrumb()
            assert breadcrumb == "Electronics > Smartphones > Android"
    
    def test_category_products(self, app):
        """Test products association with categories"""
        with app.app_context():
            category = Category(name="Electronics", slug="electronics")
            db.session.add(category)
            db.session.commit()
            
            product = Product(
                name="Test Phone",
                price=599.99,
                category_id=category.id,
                description="Test product"
            )
            db.session.add(product)
            db.session.commit()
            
            assert product.category_id == category.id
            assert product.category.name == "Electronics"
            assert product in category.products.all()
    
    def test_category_all_products(self, app):
        """Test getting all products including from subcategories"""
        with app.app_context():
            # Create categories
            electronics = Category(name="Electronics", slug="electronics")
            db.session.add(electronics)
            db.session.commit()
            
            phones = Category(
                name="Phones",
                slug="phones",
                parent_id=electronics.id
            )
            db.session.add(phones)
            db.session.commit()
            
            # Add products
            laptop = Product(
                name="Laptop",
                price=999.99,
                category_id=electronics.id,
                description="Test laptop"
            )
            phone = Product(
                name="Phone",
                price=599.99,
                category_id=phones.id,
                description="Test phone"
            )
            db.session.add_all([laptop, phone])
            db.session.commit()
            
            # Get all products from electronics (including subcategories)
            all_products = electronics.get_all_products()
            assert len(all_products) == 2
            assert laptop in all_products
            assert phone in all_products
    
    def test_category_unique_slug(self, app):
        """Test that category slugs must be unique"""
        with app.app_context():
            cat1 = Category(name="Electronics", slug="electronics")
            db.session.add(cat1)
            db.session.commit()
            
            # Try to create another category with same slug
            cat2 = Category(name="Electronic Devices", slug="electronics")
            db.session.add(cat2)
            
            with pytest.raises(Exception):  # IntegrityError
                db.session.commit()
    
    def test_category_depth_limit(self, app):
        """Test category depth validation"""
        with app.app_context():
            # Create a chain of categories
            parent = None
            for i in range(4):  # Try to create 4 levels
                cat = Category(
                    name=f"Level {i}",
                    slug=f"level-{i}",
                    parent_id=parent.id if parent else None
                )
                db.session.add(cat)
                db.session.commit()
                parent = cat
            
            # Verify we can check depth
            assert parent.get_depth() == 3  # 0-indexed
            
            # Try to add one more level (should fail if we enforce max depth of 3)
            # This test assumes we implement a max depth check
            deep_cat = Category(
                name="Too Deep",
                slug="too-deep",
                parent_id=parent.id
            )
            
            # Should validate depth in the model
            # Note: validate_depth should be called before saving
            deep_cat.parent_id = parent.id
            with pytest.raises(ValueError, match="maximum depth"):
                deep_cat.validate_depth()
    
    def test_get_main_categories(self, app):
        """Test fetching only main categories"""
        with app.app_context():
            # Create main categories
            electronics = Category(name="Electronics", slug="electronics")
            clothing = Category(name="Clothing", slug="clothing")
            
            # Create subcategories
            phones = Category(name="Phones", slug="phones")
            phones.parent = electronics
            
            db.session.add_all([electronics, clothing, phones])
            db.session.commit()
            
            main_categories = Category.get_main_categories()
            assert len(main_categories) == 2
            assert electronics in main_categories
            assert clothing in main_categories
            assert phones not in main_categories
    
    def test_category_product_count(self, app):
        """Test counting products in category and subcategories"""
        with app.app_context():
            # Create categories
            electronics = Category(name="Electronics", slug="electronics")
            phones = Category(name="Phones", slug="phones")
            phones.parent = electronics
            
            db.session.add_all([electronics, phones])
            db.session.commit()
            
            # Add products
            laptop = Product(
                name="Laptop",
                price=999.99,
                category_id=electronics.id,
                description="Test laptop"
            )
            phone1 = Product(
                name="Phone 1",
                price=599.99,
                category_id=phones.id,
                description="Test phone 1"
            )
            phone2 = Product(
                name="Phone 2",
                price=699.99,
                category_id=phones.id,
                description="Test phone 2"
            )
            
            db.session.add_all([laptop, phone1, phone2])
            db.session.commit()
            
            # Test counts
            assert phones.get_product_count() == 2
            assert electronics.get_product_count() == 1
            assert electronics.get_product_count(include_subcategories=True) == 3