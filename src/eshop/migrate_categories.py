"""
Migration script to add category hierarchy to the database
"""

from eshop import create_app
from eshop.models import db, Category, Product

def create_categories():
    """Create category hierarchy from existing product categories"""
    
    # Define category hierarchy
    category_hierarchy = {
        "Electronics": {
            "slug": "electronics",
            "subcategories": {
                "Smartphones": "smartphones",
                "Laptops": "laptops",
                "Tablets": "tablets",
                "Accessories": "accessories",
                "Audio": "audio",
                "Wearables": "wearables"
            }
        },
        "Clothing": {
            "slug": "clothing",
            "subcategories": {
                "Men's Clothing": "mens-clothing",
                "Women's Clothing": "womens-clothing",
                "Kids' Clothing": "kids-clothing",
                "Shoes": "shoes",
                "Accessories": "clothing-accessories"
            }
        },
        "Home & Garden": {
            "slug": "home-garden",
            "subcategories": {
                "Furniture": "furniture",
                "Kitchen": "kitchen",
                "Bedding": "bedding",
                "Decor": "decor",
                "Garden": "garden"
            }
        },
        "Sports & Outdoors": {
            "slug": "sports-outdoors",
            "subcategories": {
                "Exercise Equipment": "exercise-equipment",
                "Outdoor Gear": "outdoor-gear",
                "Sports Clothing": "sports-clothing",
                "Team Sports": "team-sports"
            }
        },
        "Books & Media": {
            "slug": "books-media",
            "subcategories": {
                "Books": "books",
                "E-books": "ebooks",
                "Movies": "movies",
                "Music": "music"
            }
        },
        "Beauty & Health": {
            "slug": "beauty-health",
            "subcategories": {
                "Skincare": "skincare",
                "Makeup": "makeup",
                "Health Supplements": "supplements",
                "Personal Care": "personal-care"
            }
        },
        "Toys & Games": {
            "slug": "toys-games",
            "subcategories": {
                "Action Figures": "action-figures",
                "Board Games": "board-games",
                "Educational Toys": "educational-toys",
                "Video Games": "video-games"
            }
        },
        "Food & Grocery": {
            "slug": "food-grocery",
            "subcategories": {
                "Snacks": "snacks",
                "Beverages": "beverages",
                "Organic Food": "organic",
                "Gourmet": "gourmet"
            }
        }
    }
    
    # Create main categories and subcategories
    category_map = {}  # Map old category names to new Category objects
    
    for main_name, main_data in category_hierarchy.items():
        # Create main category
        main_category = Category(
            name=main_name,
            slug=main_data["slug"],
            description=f"Browse our {main_name} collection"
        )
        db.session.add(main_category)
        db.session.flush()  # Get the ID
        
        # Map variations of the main category name
        category_map[main_name.lower()] = main_category
        category_map[main_data["slug"]] = main_category
        
        # Create subcategories
        for sub_name, sub_slug in main_data["subcategories"].items():
            sub_category = Category(
                name=sub_name,
                slug=sub_slug,
                parent_id=main_category.id,
                description=f"{sub_name} in {main_name}"
            )
            db.session.add(sub_category)
            db.session.flush()
            
            # Map variations of subcategory names
            category_map[sub_name.lower()] = sub_category
            category_map[sub_slug] = sub_category
            # Also map without apostrophes and spaces
            clean_name = sub_name.lower().replace("'", "").replace(" ", "")
            category_map[clean_name] = sub_category
    
    db.session.commit()
    return category_map


def migrate_products(category_map):
    """Migrate products to use new category IDs"""
    
    # Get all products
    products = Product.query.all()
    unmapped_categories = set()
    
    for product in products:
        if product.category:
            # Try to find matching category
            category_key = product.category.lower().strip()
            
            # Try exact match first
            if category_key in category_map:
                product.category_id = category_map[category_key].id
            else:
                # Try to find partial matches
                found = False
                for key, category in category_map.items():
                    if category_key in key or key in category_key:
                        product.category_id = category.id
                        found = True
                        break
                
                if not found:
                    # Default to a general category based on keywords
                    if any(word in category_key for word in ['phone', 'laptop', 'tablet', 'computer', 'tech']):
                        product.category_id = category_map['electronics'].id
                    elif any(word in category_key for word in ['shirt', 'pants', 'dress', 'clothes']):
                        product.category_id = category_map['clothing'].id
                    elif any(word in category_key for word in ['book', 'novel', 'media']):
                        product.category_id = category_map['books-media'].id
                    elif any(word in category_key for word in ['toy', 'game', 'puzzle']):
                        product.category_id = category_map['toys-games'].id
                    elif any(word in category_key for word in ['food', 'snack', 'drink']):
                        product.category_id = category_map['food-grocery'].id
                    elif any(word in category_key for word in ['beauty', 'health', 'cosmetic']):
                        product.category_id = category_map['beauty-health'].id
                    elif any(word in category_key for word in ['sport', 'fitness', 'outdoor']):
                        product.category_id = category_map['sports-outdoors'].id
                    elif any(word in category_key for word in ['home', 'furniture', 'kitchen']):
                        product.category_id = category_map['home-garden'].id
                    else:
                        # Default to Electronics if can't determine
                        product.category_id = category_map['electronics'].id
                        unmapped_categories.add(product.category)
    
    db.session.commit()
    
    if unmapped_categories:
        print(f"Warning: The following categories couldn't be mapped precisely: {unmapped_categories}")
        print("They were assigned to default categories based on keywords.")
    
    return len(products)


def main():
    """Run the migration"""
    app = create_app()
    
    with app.app_context():
        print("Starting category migration...")
        
        # Check if categories already exist
        existing_categories = Category.query.count()
        if existing_categories > 0:
            response = input(f"Found {existing_categories} existing categories. Delete and recreate? (y/n): ")
            if response.lower() != 'y':
                print("Migration cancelled.")
                return
            
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


if __name__ == "__main__":
    main()