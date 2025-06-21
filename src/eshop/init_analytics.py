#!/usr/bin/env python3
"""
Initialize analytics data (best sellers and trending products).
Run this script after seeding products to generate initial analytics.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eshop import create_app
from eshop.analytics import AnalyticsEngine

def init_analytics():
    """Initialize analytics data"""
    app = create_app()
    
    with app.app_context():
        print("Initializing analytics...")
        
        # Update all analytics
        AnalyticsEngine.update_analytics()
        
        print("Analytics initialization complete!")
        
        # Show some stats
        from eshop.models import BestSeller, TrendingProduct
        
        best_seller_count = BestSeller.query.count()
        trending_count = TrendingProduct.query.count()
        
        print(f"\nAnalytics summary:")
        print(f"- Best sellers entries: {best_seller_count}")
        print(f"- Trending products entries: {trending_count}")
        
        # Show top 5 overall best sellers
        print("\nTop 5 Best Sellers (30 days):")
        best_sellers = AnalyticsEngine.get_best_sellers(time_window='30d', limit=5)
        for i, product in enumerate(best_sellers, 1):
            print(f"{i}. {product.name} - ${product.price:.2f}")
        
        # Show top 5 trending products
        print("\nTop 5 Trending Products:")
        trending = AnalyticsEngine.get_trending_products(limit=5)
        for i, product in enumerate(trending, 1):
            print(f"{i}. {product.name} - ${product.price:.2f}")

if __name__ == '__main__':
    init_analytics()