import random
from datetime import datetime, timedelta, timezone
from eshop import create_app
from eshop.models import db, Product, Category

# Map old category names to new category structure
# Format: "old_category": ("main_category", "subcategory")
CATEGORY_MAPPING = {
    "Electronics": [
        ("Electronics", "Smartphones & Tablets"),
        ("Electronics", "Laptops & Computers"),
        ("Electronics", "Audio & Headphones"),
        ("Electronics", "Gaming & Consoles"),
        ("Electronics", "Cameras & Photography"),
        ("Electronics", "Smart Home & IoT"),
    ],
    "Clothing": [
        ("Fashion", "Men's Clothing"),
        ("Fashion", "Women's Clothing"),
        ("Fashion", "Shoes & Footwear"),
        ("Fashion", "Sportswear & Activewear"),
    ],
    "Home & Garden": [
        ("Home & Living", "Kitchen & Dining"),
        ("Home & Living", "Home Decor"),
        ("Home & Living", "Garden & Outdoor"),
        ("Home & Living", "Furniture"),
    ],
    "Beauty & Personal Care": [
        ("Beauty & Health", "Personal Care"),
        ("Beauty & Health", "Hair Care"),
        ("Beauty & Health", "Skincare"),
        ("Beauty & Health", "Fragrances"),
        ("Beauty & Health", "Makeup & Cosmetics"),
    ],
    "Sports & Outdoors": [
        ("Sports & Outdoors", "Exercise & Fitness"),
        ("Sports & Outdoors", "Sports Equipment"),
        ("Sports & Outdoors", "Outdoor Recreation"),
    ],
    "Books & Media": [
        ("Books & Media", "Books"),
        ("Books & Media", "Video Games"),
        ("Books & Media", "Movies & TV"),
    ],
    "Toys & Games": [
        ("Toys & Kids", "Toys & Games"),
        ("Toys & Kids", "Kids Room & Nursery"),
    ],
    "Food & Beverage": [
        ("Food & Grocery", "Beverages"),
        ("Food & Grocery", "Snacks & Sweets"),
        ("Food & Grocery", "Organic & Natural"),
    ]
}

# Categories and their associated products
PRODUCT_DATA = {
    "Electronics": [
        {"name": "Wireless Noise-Canceling Headphones", "brands": ["Sony", "Bose", "Apple", "Sennheiser"], "price_range": (150, 350), "tags": "audio,wireless,bluetooth,noise-canceling", "subcategory": "Audio & Headphones"},
        {"name": "Smartphone", "brands": ["Apple", "Samsung", "Google", "OnePlus"], "price_range": (400, 1200), "tags": "mobile,5G,camera,smartphone", "subcategory": "Smartphones & Tablets"},
        {"name": "Laptop", "brands": ["Apple", "Dell", "HP", "Lenovo", "ASUS"], "price_range": (500, 2500), "tags": "computer,portable,work,productivity", "subcategory": "Laptops & Computers"},
        {"name": "Tablet", "brands": ["Apple", "Samsung", "Microsoft", "Amazon"], "price_range": (200, 1000), "tags": "tablet,portable,touchscreen,media", "subcategory": "Smartphones & Tablets"},
        {"name": "Smart Watch", "brands": ["Apple", "Samsung", "Garmin", "Fitbit"], "price_range": (150, 800), "tags": "wearable,fitness,health,smart", "subcategory": "Smart Home & IoT"},
        {"name": "Wireless Earbuds", "brands": ["Apple", "Samsung", "Sony", "Jabra"], "price_range": (50, 300), "tags": "audio,wireless,portable,earbuds", "subcategory": "Audio & Headphones"},
        {"name": "4K Smart TV", "brands": ["Samsung", "LG", "Sony", "TCL"], "price_range": (300, 2000), "tags": "tv,4k,smart,entertainment", "subcategory": "Smart Home & IoT"},
        {"name": "Gaming Console", "brands": ["Sony", "Microsoft", "Nintendo"], "price_range": (300, 500), "tags": "gaming,console,entertainment", "subcategory": "Gaming & Consoles"},
        {"name": "Digital Camera", "brands": ["Canon", "Nikon", "Sony", "Fujifilm"], "price_range": (400, 3000), "tags": "camera,photography,digital,professional", "subcategory": "Cameras & Photography"},
        {"name": "Bluetooth Speaker", "brands": ["JBL", "Bose", "Sony", "Ultimate Ears"], "price_range": (30, 300), "tags": "audio,bluetooth,portable,speaker", "subcategory": "Audio & Headphones"},
    ],
    "Clothing": [
        {"name": "T-Shirt", "brands": ["Nike", "Adidas", "Puma", "Under Armour"], "price_range": (15, 50), "tags": "casual,comfort,everyday,cotton", "subcategory": "Men's Clothing"},
        {"name": "Jeans", "brands": ["Levi's", "Gap", "Diesel", "Calvin Klein"], "price_range": (40, 150), "tags": "denim,casual,pants,fashion", "subcategory": "Men's Clothing"},
        {"name": "Running Shoes", "brands": ["Nike", "Adidas", "New Balance", "ASICS"], "price_range": (60, 200), "tags": "footwear,sports,running,athletic", "subcategory": "Shoes & Footwear"},
        {"name": "Winter Jacket", "brands": ["North Face", "Columbia", "Patagonia", "Arc'teryx"], "price_range": (100, 500), "tags": "outerwear,winter,warm,waterproof", "subcategory": "Men's Clothing"},
        {"name": "Dress Shirt", "brands": ["Ralph Lauren", "Tommy Hilfiger", "Calvin Klein", "Brooks Brothers"], "price_range": (40, 150), "tags": "formal,business,cotton,professional", "subcategory": "Men's Clothing"},
        {"name": "Yoga Pants", "brands": ["Lululemon", "Nike", "Athleta", "Fabletics"], "price_range": (50, 120), "tags": "athletic,yoga,comfort,stretchy", "subcategory": "Sportswear & Activewear"},
        {"name": "Hoodie", "brands": ["Nike", "Adidas", "Champion", "Under Armour"], "price_range": (30, 80), "tags": "casual,comfort,warm,sportswear", "subcategory": "Sportswear & Activewear"},
        {"name": "Sneakers", "brands": ["Nike", "Adidas", "Vans", "Converse"], "price_range": (50, 150), "tags": "footwear,casual,street,fashion", "subcategory": "Shoes & Footwear"},
    ],
    "Home & Garden": [
        {"name": "Coffee Maker", "brands": ["Keurig", "Nespresso", "Breville", "Cuisinart"], "price_range": (50, 300), "tags": "kitchen,coffee,appliance,morning", "subcategory": "Kitchen & Dining"},
        {"name": "Robot Vacuum", "brands": ["iRobot", "Eufy", "Shark", "Dyson"], "price_range": (200, 800), "tags": "cleaning,smart,automated,vacuum", "subcategory": "Home Decor"},
        {"name": "Air Purifier", "brands": ["Dyson", "Levoit", "Honeywell", "Blueair"], "price_range": (100, 600), "tags": "air,health,filter,home", "subcategory": "Home Decor"},
        {"name": "Smart Thermostat", "brands": ["Nest", "Ecobee", "Honeywell", "Emerson"], "price_range": (150, 300), "tags": "smart,home,temperature,energy", "subcategory": "Home Decor"},
        {"name": "Instant Pot", "brands": ["Instant Pot", "Ninja", "Cuisinart", "Crock-Pot"], "price_range": (60, 200), "tags": "kitchen,cooking,pressure-cooker,multi-use", "subcategory": "Kitchen & Dining"},
        {"name": "Standing Desk", "brands": ["FlexiSpot", "UPLIFT", "Autonomous", "IKEA"], "price_range": (200, 800), "tags": "furniture,office,ergonomic,adjustable", "subcategory": "Furniture"},
        {"name": "Indoor Plants Set", "brands": ["The Sill", "Bloomscape", "Costa Farms"], "price_range": (30, 150), "tags": "plants,indoor,decor,air-purifying", "subcategory": "Garden & Outdoor"},
        {"name": "Smart Door Lock", "brands": ["August", "Yale", "Schlage", "Kwikset"], "price_range": (150, 400), "tags": "security,smart,home,keyless", "subcategory": "Home Decor"},
    ],
    "Beauty & Personal Care": [
        {"name": "Electric Toothbrush", "brands": ["Oral-B", "Philips Sonicare", "Quip", "Colgate"], "price_range": (30, 200), "tags": "oral-care,electric,hygiene,health", "subcategory": "Personal Care"},
        {"name": "Hair Dryer", "brands": ["Dyson", "BaByliss", "Revlon", "Conair"], "price_range": (30, 400), "tags": "hair-care,styling,beauty,electric", "subcategory": "Hair Care"},
        {"name": "Skincare Set", "brands": ["Clinique", "Estée Lauder", "L'Oréal", "Olay"], "price_range": (40, 200), "tags": "skincare,beauty,anti-aging,moisturizer", "subcategory": "Skincare"},
        {"name": "Perfume", "brands": ["Chanel", "Dior", "Tom Ford", "Calvin Klein"], "price_range": (50, 300), "tags": "fragrance,luxury,scent,gift", "subcategory": "Fragrances"},
        {"name": "Makeup Palette", "brands": ["Urban Decay", "MAC", "Too Faced", "Charlotte Tilbury"], "price_range": (30, 100), "tags": "makeup,cosmetics,eyeshadow,beauty", "subcategory": "Makeup & Cosmetics"},
        {"name": "Beard Trimmer", "brands": ["Philips", "Braun", "Wahl", "Panasonic"], "price_range": (30, 150), "tags": "grooming,men,electric,trimmer", "subcategory": "Personal Care"},
    ],
    "Sports & Outdoors": [
        {"name": "Yoga Mat", "brands": ["Manduka", "Liforme", "Jade", "Gaiam"], "price_range": (20, 150), "tags": "yoga,fitness,exercise,mat", "subcategory": "Exercise & Fitness"},
        {"name": "Dumbbell Set", "brands": ["Bowflex", "CAP", "NordicTrack", "PowerBlock"], "price_range": (50, 500), "tags": "weights,fitness,strength,home-gym", "subcategory": "Exercise & Fitness"},
        {"name": "Treadmill", "brands": ["NordicTrack", "ProForm", "Sole", "Horizon"], "price_range": (500, 3000), "tags": "cardio,running,fitness,home-gym", "subcategory": "Exercise & Fitness"},
        {"name": "Camping Tent", "brands": ["Coleman", "REI", "North Face", "MSR"], "price_range": (100, 500), "tags": "camping,outdoor,shelter,adventure", "subcategory": "Outdoor Recreation"},
        {"name": "Mountain Bike", "brands": ["Trek", "Specialized", "Giant", "Cannondale"], "price_range": (300, 3000), "tags": "cycling,outdoor,fitness,adventure", "subcategory": "Outdoor Recreation"},
        {"name": "Tennis Racket", "brands": ["Wilson", "Babolat", "Head", "Prince"], "price_range": (50, 300), "tags": "tennis,sports,racket,competition", "subcategory": "Sports Equipment"},
        {"name": "Golf Club Set", "brands": ["Callaway", "TaylorMade", "Titleist", "Ping"], "price_range": (200, 2000), "tags": "golf,sports,clubs,outdoor", "subcategory": "Sports Equipment"},
    ],
    "Books & Media": [
        {"name": "Bestseller Novel", "brands": [""], "price_range": (10, 30), "tags": "fiction,reading,entertainment,bestseller", "subcategory": "Books"},
        {"name": "Educational Textbook", "brands": [""], "price_range": (30, 150), "tags": "education,learning,academic,reference", "subcategory": "Books"},
        {"name": "Video Game", "brands": ["Sony", "Microsoft", "Nintendo", "EA"], "price_range": (30, 70), "tags": "gaming,entertainment,console,adventure", "subcategory": "Video Games"},
        {"name": "Blu-ray Movie Collection", "brands": [""], "price_range": (15, 50), "tags": "movies,entertainment,collection,blu-ray", "subcategory": "Movies & TV"},
    ],
    "Toys & Games": [
        {"name": "LEGO Building Set", "brands": ["LEGO"], "price_range": (20, 300), "tags": "building,creative,educational,toys", "subcategory": "Toys & Games"},
        {"name": "Board Game", "brands": ["Hasbro", "Mattel", "Ravensburger"], "price_range": (15, 60), "tags": "family,fun,strategy,entertainment", "subcategory": "Toys & Games"},
        {"name": "Educational Toy Set", "brands": ["Melissa & Doug", "VTech", "LeapFrog"], "price_range": (20, 100), "tags": "educational,learning,development,kids", "subcategory": "Toys & Games"},
        {"name": "Remote Control Car", "brands": ["Traxxas", "Redcat", "ARRMA"], "price_range": (50, 500), "tags": "rc,remote-control,outdoor,toys", "subcategory": "Toys & Games"},
    ],
    "Food & Beverage": [
        {"name": "Gourmet Coffee Beans", "brands": ["Starbucks", "Lavazza", "Blue Bottle", "Death Wish"], "price_range": (10, 40), "tags": "coffee,beans,morning,gourmet", "subcategory": "Beverages"},
        {"name": "Organic Tea Collection", "brands": ["Twinings", "Celestial", "Harney & Sons", "Tazo"], "price_range": (5, 30), "tags": "tea,organic,healthy,beverage", "subcategory": "Beverages"},
        {"name": "Protein Powder", "brands": ["Optimum Nutrition", "Dymatize", "BSN", "MuscleTech"], "price_range": (20, 80), "tags": "protein,fitness,supplement,health", "subcategory": "Organic & Natural"},
        {"name": "Gourmet Chocolate Box", "brands": ["Godiva", "Lindt", "Ghirardelli", "Ferrero"], "price_range": (15, 60), "tags": "chocolate,gift,luxury,sweet", "subcategory": "Snacks & Sweets"},
        {"name": "Organic Snack Box", "brands": ["KIND", "RXBAR", "Nature Valley", "Cliff Bar"], "price_range": (20, 50), "tags": "snacks,healthy,organic,variety", "subcategory": "Snacks & Sweets"},
    ]
}

def generate_description(product_name, brand, category):
    """Generate a product description"""
    descriptions = {
        "Electronics": f"Experience cutting-edge technology with the {brand} {product_name}. Designed for modern life, this product combines innovation with reliability.",
        "Clothing": f"Elevate your style with the {brand} {product_name}. Crafted with premium materials for comfort and durability.",
        "Home & Garden": f"Transform your living space with the {brand} {product_name}. Perfect for modern homes seeking functionality and style.",
        "Beauty & Personal Care": f"Enhance your daily routine with the {brand} {product_name}. Professional-grade quality for personal care excellence.",
        "Sports & Outdoors": f"Achieve your fitness goals with the {brand} {product_name}. Built for performance and designed for champions.",
        "Books & Media": f"Expand your horizons with the {product_name}. Quality content for entertainment and education.",
        "Toys & Games": f"Create lasting memories with the {brand} {product_name}. Fun and engaging for all ages.",
        "Food & Beverage": f"Indulge in the premium quality of {brand} {product_name}. Carefully selected for discerning tastes."
    }
    return descriptions.get(category, f"Discover the excellence of {brand} {product_name}. Quality you can trust.")

def get_category_id(main_category_name, subcategory_name):
    """Get the category ID for a given main category and subcategory"""
    # First try to find the subcategory
    subcategory = Category.query.filter_by(name=subcategory_name).first()
    if subcategory and not subcategory.is_main_category():
        return subcategory.id
    
    # If subcategory not found, fall back to main category
    main_category = Category.query.filter_by(name=main_category_name).first()
    if main_category and main_category.is_main_category():
        return main_category.id
    
    # If nothing found, return None (will need to handle this)
    return None

def seed_products():
    """Seed the database with product data"""
    app = create_app()
    
    with app.app_context():
        # Clear existing products
        Product.query.delete()
        db.session.commit()
        
        products_created = 0
        
        for category, products in PRODUCT_DATA.items():
            for product_template in products:
                # Get the appropriate category mapping
                if category in CATEGORY_MAPPING:
                    category_options = CATEGORY_MAPPING[category]
                else:
                    print(f"Warning: No category mapping for {category}")
                    continue
                
                # Create multiple variants with different brands
                for brand in product_template["brands"]:
                    if not brand:  # Skip empty brands
                        brand = "Generic"
                    
                    # Determine which category to use based on subcategory hint
                    category_id = None
                    if "subcategory" in product_template:
                        # Find the matching main category for this subcategory
                        for main_cat, sub_cat in category_options:
                            if sub_cat == product_template["subcategory"]:
                                category_id = get_category_id(main_cat, sub_cat)
                                break
                    
                    if not category_id:
                        # Use random category from options
                        main_cat, sub_cat = random.choice(category_options)
                        category_id = get_category_id(main_cat, sub_cat)
                    
                    if not category_id:
                        print(f"Warning: Could not find category for {product_template['name']}")
                        continue
                    
                    # Generate price
                    min_price, max_price = product_template["price_range"]
                    price = round(random.uniform(min_price, max_price), 2)
                    
                    # Generate stock quantity (some items might be low stock)
                    stock = random.choices(
                        [random.randint(0, 10), random.randint(11, 50), random.randint(51, 200)],
                        weights=[0.1, 0.3, 0.6]
                    )[0]
                    
                    # Generate discount (20% chance of having a discount)
                    discount = 0
                    if random.random() < 0.2:
                        discount = random.choice([5, 10, 15, 20, 25, 30])
                    
                    # Create product
                    product = Product(
                        name=f"{brand} {product_template['name']}",
                        price=price,
                        category_id=category_id,
                        category=category,  # Keep for backward compatibility
                        brand=brand,
                        tags=product_template["tags"],
                        description=generate_description(product_template['name'], brand, category),
                        stock_quantity=stock,
                        discount_percentage=discount,
                        created_at=datetime.now(timezone.utc) - timedelta(days=random.randint(0, 90))
                    )
                    
                    db.session.add(product)
                    products_created += 1
        
        db.session.commit()
        print(f"Successfully seeded {products_created} products!")

if __name__ == "__main__":
    seed_products()