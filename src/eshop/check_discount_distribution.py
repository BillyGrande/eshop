#!/usr/bin/env python3
"""
Check discount distribution in recommendations
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eshop import create_app
from eshop.recommender import Recommender
from eshop.analytics import AnalyticsEngine

app = create_app()
with app.app_context():
    # Check best sellers
    print('Top 10 Best Sellers with discounts:')
    best_sellers = AnalyticsEngine.get_best_sellers(time_window='30d', limit=10)
    for i, p in enumerate(best_sellers, 1):
        if p.discount_percentage > 0:
            print(f'  {i}. {p.name}: {int(p.discount_percentage)}% OFF - Was ${p.price:.2f}, Now ${p.get_discounted_price():.2f}')
        else:
            print(f'  {i}. {p.name}: ${p.price:.2f} (no discount)')
    
    print('\nTop 10 Trending Products with discounts:')
    trending = AnalyticsEngine.get_trending_products(limit=10)
    for i, p in enumerate(trending, 1):
        if p.discount_percentage > 0:
            print(f'  {i}. {p.name}: {int(p.discount_percentage)}% OFF - Was ${p.price:.2f}, Now ${p.get_discounted_price():.2f}')
        else:
            print(f'  {i}. {p.name}: ${p.price:.2f} (no discount)')
    
    print('\nSample Guest Recommendations:')
    recs = Recommender.get_recommendations_for_guest('new_guest_test', limit=4)
    for i, p in enumerate(recs, 1):
        if p.discount_percentage > 0:
            print(f'  {i}. {p.name}: {int(p.discount_percentage)}% OFF')
        else:
            print(f'  {i}. {p.name}: No discount')