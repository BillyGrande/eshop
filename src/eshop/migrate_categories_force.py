#!/usr/bin/env python3
"""
Non-interactive version of category migration script
"""

from eshop import create_app, db
from eshop.models import Category, Product

def create_categories():
    """Create category hierarchy with main categories and subcategories"""
    category_map = {}
    
    # Main categories with their subcategories
    categories_structure = {
        'Electronics': [
            'Smartphones & Tablets',
            'Laptops & Computers',
            'Audio & Headphones',
            'Gaming & Consoles',
            'Cameras & Photography',
            'Smart Home & IoT'
        ],
        'Fashion': [
            'Men\'s Clothing',
            'Women\'s Clothing',
            'Shoes & Footwear',
            'Bags & Accessories',
            'Jewelry & Watches',
            'Sportswear & Activewear'
        ],
        'Home & Living': [
            'Furniture',
            'Kitchen & Dining',
            'Bedding & Bath',
            'Home Decor',
            'Garden & Outdoor',
            'Storage & Organization'
        ],
        'Beauty & Health': [
            'Skincare',
            'Makeup & Cosmetics',
            'Hair Care',
            'Fragrances',
            'Health & Wellness',
            'Personal Care'
        ],
        'Sports & Outdoors': [
            'Exercise & Fitness',
            'Outdoor Recreation',
            'Sports Equipment',
            'Cycling',
            'Water Sports',
            'Winter Sports'
        ],
        'Books & Media': [
            'Books',
            'E-books & Audiobooks',
            'Movies & TV',
            'Music',
            'Video Games',
            'Magazines & Comics'
        ],
        'Toys & Kids': [
            'Baby & Toddler',
            'Toys & Games',
            'Kids Clothing',
            'School & Education',
            'Kids Room & Nursery',
            'Outdoor Play'
        ],
        'Food & Grocery': [
            'Fresh Produce',
            'Beverages',
            'Snacks & Sweets',
            'Pantry Staples',
            'Organic & Natural',
            'International Foods'
        ]
    }
    
    # Create categories
    for main_cat_name, subcategories in categories_structure.items():
        # Create main category
        main_cat = Category(
            name=main_cat_name,
            slug=main_cat_name.lower().replace(' & ', '-').replace(' ', '-'),
            description=f"Browse our {main_cat_name} collection"
        )
        db.session.add(main_cat)
        db.session.flush()  # To get the ID
        
        # Map old category names to new category objects
        category_map[main_cat_name.lower()] = main_cat
        
        # Create subcategories
        for subcat_name in subcategories:
            subcat = Category(
                name=subcat_name,
                slug=subcat_name.lower().replace(' & ', '-').replace(' ', '-').replace('\'', ''),
                parent_id=main_cat.id,
                description=f"{subcat_name} in {main_cat_name}"
            )
            db.session.add(subcat)
            
            # Add various mappings for flexibility
            category_map[subcat_name.lower()] = subcat
            # Also map without special characters for better matching
            simple_name = subcat_name.lower().replace('&', 'and').replace('\'', '')
            category_map[simple_name] = subcat
    
    db.session.commit()
    return category_map

def migrate_products(category_map):
    """Migrate products to use category_id instead of category string"""
    
    # Category name mappings for better matching
    manual_mappings = {
        'technology': 'electronics',
        'clothes': 'fashion',
        'clothing': 'fashion',
        'home': 'home & living',
        'house': 'home & living',
        'beauty': 'beauty & health',
        'health': 'beauty & health',
        'sport': 'sports & outdoors',
        'sports': 'sports & outdoors',
        'book': 'books & media',
        'books': 'books & media',
        'media': 'books & media',
        'toys': 'toys & kids',
        'kids': 'toys & kids',
        'children': 'toys & kids',
        'food': 'food & grocery',
        'grocery': 'food & grocery',
        'groceries': 'food & grocery'
    }
    
    # Get all products
    products = Product.query.all()
    migrated_count = 0
    
    for product in products:
        if product.category and not product.category_id:
            # Try to find matching category
            cat_lower = product.category.lower().strip()
            
            # First try direct match
            if cat_lower in category_map:
                product.category_id = category_map[cat_lower].id
                migrated_count += 1
            # Then try manual mappings
            elif cat_lower in manual_mappings:
                mapped_name = manual_mappings[cat_lower]
                if mapped_name in category_map:
                    product.category_id = category_map[mapped_name].id
                    migrated_count += 1
            else:
                # Try partial matching for main categories
                for key, category in category_map.items():
                    if category.is_main_category() and (key in cat_lower or cat_lower in key):
                        product.category_id = category.id
                        migrated_count += 1
                        break
                else:
                    # Default to first main category if no match found
                    print(f"Warning: No category match for '{product.category}' on product '{product.name}'")
                    main_categories = Category.get_main_categories()
                    if main_categories:
                        product.category_id = main_categories[0].id
                        migrated_count += 1
    
    db.session.commit()
    return migrated_count

def main():
    app = create_app()
    
    with app.app_context():
        print("Starting category migration (force mode)...")
        
        # Check if categories already exist
        existing_categories = Category.query.count()
        if existing_categories > 0:
            print(f"Found {existing_categories} existing categories. Deleting and recreating...")
            # Delete existing categories
            Category.query.delete()
            db.session.commit()
        
        # Create new categories
        print("Creating category hierarchy...")
        category_map = create_categories()
        print(f"Created {len(category_map)} category mappings")
        
        # Migrate products
        print("Migrating products to new categories...")
        product_count = migrate_products(category_map)
        print(f"Migrated {product_count} products")
        
        # Verify migration
        categories = Category.query.all()
        main_categories = Category.get_main_categories()
        
        print(f"\nMigration complete!")
        print(f"Total categories: {len(categories)}")
        print(f"Main categories: {len(main_categories)}")
        
        # Show category tree
        print("\nCategory hierarchy:")
        for main_cat in main_categories:
            print(f"- {main_cat.name} ({main_cat.get_product_count(include_subcategories=True)} products)")
            for sub_cat in main_cat.children:
                print(f"  - {sub_cat.name} ({sub_cat.get_product_count()} products)")

if __name__ == '__main__':
    main()