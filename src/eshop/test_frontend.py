#!/usr/bin/env python3
"""
Test the frontend rendering with a controlled set of recommendations
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import render_template_string
from eshop import create_app
from eshop.models import Product

# Simplified test template
TEST_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Test Recommendations</title>
    <style>
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        .product-grid { 
            display: grid; 
            grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); 
            gap: 20px; 
            border: 2px solid red; /* Debug border */
        }
        .product-card { 
            border: 1px solid #ddd; 
            padding: 15px; 
            background: #f9f9f9;
        }
        .debug-info {
            background: #fffacd;
            padding: 10px;
            margin: 20px 0;
            border: 1px solid #ddd;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Recommendation Test</h1>
        
        <div class="debug-info">
            <strong>Debug Info:</strong><br>
            Total recommendations: {{ recommended_products|length }}<br>
            Product IDs: {% for p in recommended_products %}{{ p.id }}{% if not loop.last %}, {% endif %}{% endfor %}
        </div>
        
        <h2>Recommended Products:</h2>
        <div class="product-grid">
            {% for product in recommended_products %}
            <div class="product-card">
                <h3>{{ loop.index }}. {{ product.name }}</h3>
                <p>Category: {{ product.category }}</p>
                <p>Price: ${{ "%.2f"|format(product.price) }}</p>
                <p>ID: {{ product.id }}</p>
            </div>
            {% endfor %}
        </div>
        
        {% if recommended_products|length == 0 %}
        <p style="color: red;">No recommendations found!</p>
        {% endif %}
    </div>
</body>
</html>
'''

def test_frontend():
    app = create_app()
    
    with app.app_context():
        # Get 4 products directly
        products = Product.query.limit(4).all()
        
        print(f"Testing with {len(products)} products")
        
        # Create a test route
        @app.route('/test-recommendations')
        def test_recommendations():
            return render_template_string(TEST_TEMPLATE, recommended_products=products)
        
        print("\nTest server ready!")
        print("Visit: http://localhost:5000/test-recommendations")
        print("\nAlso check the main page for comparison")
        print("Visit: http://localhost:5000")
        print("\nDebug endpoint:")
        print("Visit: http://localhost:5000/debug/recommendations")
        
        # Run the test server
        app.run(debug=True, port=5000)

if __name__ == '__main__':
    test_frontend()