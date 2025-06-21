#!/usr/bin/env python3
"""
Diagnose recommendation issues
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eshop import create_app
from eshop.recommender import Recommender
from eshop.analytics import AnalyticsEngine
from eshop.models import db, Product, BestSeller, TrendingProduct

def diagnose():
    app = create_app()
    
    with app.app_context():
        print("=== Recommendation System Diagnosis ===\n")
        
        # Check product count
        product_count = Product.query.count()
        print(f"1. Total products in database: {product_count}")
        
        # Check analytics data
        bs_overall = BestSeller.query.filter_by(category=None, time_window='30d').count()
        tp_overall = TrendingProduct.query.filter_by(category=None).count()
        print(f"\n2. Analytics data:")
        print(f"   - Best sellers (30d, overall): {bs_overall}")
        print(f"   - Trending products (overall): {tp_overall}")
        
        # Test best sellers retrieval
        print("\n3. Testing best sellers retrieval:")
        best_sellers = AnalyticsEngine.get_best_sellers(time_window='30d', limit=4)
        print(f"   - Requested 4, got {len(best_sellers)} best sellers")
        for i, p in enumerate(best_sellers):
            print(f"     {i+1}. {p.name} (ID: {p.id})")
        
        # Test trending retrieval
        print("\n4. Testing trending products retrieval:")
        trending = AnalyticsEngine.get_trending_products(limit=4)
        print(f"   - Requested 4, got {len(trending)} trending products")
        for i, p in enumerate(trending):
            print(f"     {i+1}. {p.name} (ID: {p.id})")
        
        # Test guest recommendations (new guest)
        print("\n5. Testing guest recommendations (new guest):")
        test_session = "test_diagnosis_session"
        recs = Recommender.get_recommendations_for_guest(test_session, limit=4)
        print(f"   - Requested 4, got {len(recs)} recommendations")
        for i, p in enumerate(recs):
            if p:
                print(f"     {i+1}. {p.name} (ID: {p.id}, Category: {p.category})")
            else:
                print(f"     {i+1}. None (This is the problem!)")
        
        # Check for None values
        print("\n6. Checking for data issues:")
        # Check best sellers with no product
        orphan_bs = db.session.query(BestSeller).filter(
            ~BestSeller.product_id.in_(db.session.query(Product.id))
        ).count()
        print(f"   - Orphaned best sellers (no matching product): {orphan_bs}")
        
        # Check trending with no product
        orphan_tp = db.session.query(TrendingProduct).filter(
            ~TrendingProduct.product_id.in_(db.session.query(Product.id))
        ).count()
        print(f"   - Orphaned trending products (no matching product): {orphan_tp}")
        
        # If there are issues, fix them
        if orphan_bs > 0 or orphan_tp > 0:
            print("\n7. Found data integrity issues. Cleaning up...")
            # Remove orphaned records
            BestSeller.query.filter(
                ~BestSeller.product_id.in_(db.session.query(Product.id))
            ).delete(synchronize_session=False)
            TrendingProduct.query.filter(
                ~TrendingProduct.product_id.in_(db.session.query(Product.id))
            ).delete(synchronize_session=False)
            db.session.commit()
            
            print("   - Cleaned up orphaned records")
            print("   - Re-running analytics update...")
            AnalyticsEngine.update_analytics()
            print("   - Analytics updated!")
            
            # Test again
            print("\n8. Testing after cleanup:")
            recs = Recommender.get_recommendations_for_guest("test_after_cleanup", limit=4)
            print(f"   - Requested 4, got {len(recs)} recommendations")
            for i, p in enumerate(recs):
                if p:
                    print(f"     {i+1}. {p.name}")
                else:
                    print(f"     {i+1}. None (Still a problem!)")

if __name__ == '__main__':
    diagnose()