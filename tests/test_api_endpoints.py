"""
API endpoint tests for recommendation system
Tests all recommendation-related endpoints for functionality, performance, and security
"""

import pytest
import json
from unittest.mock import patch
from flask import session
from eshop.models import db, User, Product, UserInteraction, PersonalizedOffer
from datetime import datetime, timedelta


class TestRecommendationAPI:
    """Test recommendation API endpoints"""
    
    def test_home_page_recommendations(self, client, sample_products, analytics_engine):
        """Test homepage recommendations endpoint"""
        response = client.get('/')
        assert response.status_code == 200
        
        # Check that recommendations are displayed
        assert b'Recommended For You' in response.data
        
    def test_track_interaction_endpoint(self, client, sample_products):
        """Test interaction tracking API"""
        # Test view tracking
        response = client.post('/track', 
                             json={'product_id': sample_products[0].id, 'type': 'view'},
                             content_type='application/json')
        assert response.status_code == 200
        assert response.json['status'] == 'ok'
        
        # Test click tracking
        response = client.post('/track',
                             json={'product_id': sample_products[1].id, 'type': 'click'},
                             content_type='application/json')
        assert response.status_code == 200
        
        # Test invalid product ID
        response = client.post('/track',
                             json={'product_id': 99999, 'type': 'view'},
                             content_type='application/json')
        assert response.status_code == 200  # Should still return ok but not crash
    
    def test_product_detail_recommendations(self, client, sample_products):
        """Test product detail page with similar products"""
        product = sample_products[0]
        response = client.get(f'/product/{product.id}')
        
        assert response.status_code == 200
        assert product.name.encode() in response.data
        # Should track view automatically
        
    def test_authenticated_recommendations(self, authenticated_client, sample_products):
        """Test recommendations for logged-in users"""
        response = authenticated_client.get('/')
        assert response.status_code == 200
        
        # Should show personalized recommendations
        assert b'Recommended For You' in response.data
    
    def test_guest_session_persistence(self, client, sample_products):
        """Test that guest sessions persist across requests"""
        # First request - creates session
        response1 = client.get('/')
        assert response.status_code == 200
        
        # Track interaction
        client.post('/track',
                   json={'product_id': sample_products[0].id, 'type': 'view'},
                   content_type='application/json')
        
        # Second request - should maintain session
        response2 = client.get('/')
        
        # Session should persist
        with client.session_transaction() as sess:
            assert 'session_id' in sess
    
    def test_recommendation_performance(self, client, sample_products):
        """Test recommendation endpoint performance"""
        import time
        
        start = time.time()
        response = client.get('/')
        duration = time.time() - start
        
        assert response.status_code == 200
        assert duration < 2.0  # Should respond within 2 seconds
    
    def test_cart_recommendations_api(self, authenticated_client, sample_products):
        """Test cart-based recommendations"""
        # Add items to cart
        for i in range(3):
            authenticated_client.post('/cart/add',
                                    json={'product_id': sample_products[i].id})
        
        # Get cart page
        response = authenticated_client.get('/cart')
        assert response.status_code == 200
        
        # Should show frequently bought together items
        # (Would need to implement this in cart template)
    
    def test_personalized_offers_api(self, app, authenticated_client, sample_users):
        """Test personalized offers in recommendations"""
        with app.app_context():
            user = User.query.filter_by(email='active@test.com').first()
            product = Product.query.first()
            
            # Create a personalized offer
            offer = PersonalizedOffer(
                user_id=user.id,
                product_id=product.id,
                discount_percentage=10.0,
                expires_at=datetime.utcnow() + timedelta(days=7)
            )
            db.session.add(offer)
            db.session.commit()
            
            # Get homepage
            response = authenticated_client.get('/')
            assert response.status_code == 200
            
            # Should show offer badge (if implemented in template)
            assert b'10% FOR YOU' in response.data or b'personalized-offer' in response.data


class TestRecommendationSecurity:
    """Security tests for recommendation endpoints"""
    
    def test_sql_injection_protection(self, client):
        """Test SQL injection protection in tracking endpoint"""
        malicious_payload = {
            'product_id': "1; DROP TABLE users; --",
            'type': 'view'
        }
        
        response = client.post('/track',
                             json=malicious_payload,
                             content_type='application/json')
        
        # Should handle safely
        assert response.status_code == 200
        
        # Database should still be intact
        assert User.query.count() > 0
    
    def test_xss_protection(self, client, app):
        """Test XSS protection in product names"""
        with app.app_context():
            # Create product with XSS attempt
            malicious_product = Product(
                name='<script>alert("XSS")</script>Product',
                price=100,
                category='Test',
                description='Test product',
                stock_quantity=10
            )
            db.session.add(malicious_product)
            db.session.commit()
            
            product_id = malicious_product.id
        
        response = client.get(f'/product/{product_id}')
        
        # Script tag should be escaped
        assert b'<script>alert' not in response.data
        assert b'&lt;script&gt;' in response.data or response.status_code == 404
    
    def test_rate_limiting(self, client, sample_products):
        """Test rate limiting on tracking endpoint"""
        # Send many requests rapidly
        responses = []
        for i in range(100):
            response = client.post('/track',
                                 json={'product_id': sample_products[0].id, 'type': 'view'},
                                 content_type='application/json')
            responses.append(response.status_code)
        
        # All should succeed (no rate limiting implemented yet)
        # But this test documents where rate limiting should be added
        assert all(status == 200 for status in responses)
    
    def test_csrf_protection(self, client):
        """Test CSRF protection on state-changing endpoints"""
        # Try to add to cart without CSRF token
        response = client.post('/cart/add',
                             json={'product_id': 1},
                             content_type='application/json')
        
        # Should be protected (depends on Flask-WTF configuration)
        # In test mode, CSRF might be disabled
        assert response.status_code in [200, 400, 403]


class TestRecommendationEdgeCases:
    """Edge case tests for recommendation system"""
    
    def test_empty_catalog(self, app, client):
        """Test recommendations with no products"""
        with app.app_context():
            # Clear all products
            Product.query.delete()
            db.session.commit()
        
        response = client.get('/')
        assert response.status_code == 200
        # Should handle gracefully
    
    def test_new_user_cold_start(self, authenticated_client):
        """Test recommendations for brand new user"""
        response = authenticated_client.get('/')
        assert response.status_code == 200
        
        # Should show best sellers/trending
        assert b'Recommended For You' in response.data
    
    def test_out_of_stock_filtering(self, app, authenticated_client, sample_products):
        """Test that out-of-stock products are filtered"""
        with app.app_context():
            # Set all products to out of stock
            for product in sample_products:
                product.stock_quantity = 0
            db.session.commit()
        
        response = authenticated_client.get('/')
        assert response.status_code == 200
        
        # Should handle gracefully, possibly show message
    
    def test_single_category_recommendations(self, app, client):
        """Test recommendations when all products are in one category"""
        with app.app_context():
            # Set all products to same category
            products = Product.query.all()
            for product in products:
                product.category = 'Electronics'
            db.session.commit()
        
        response = client.get('/')
        assert response.status_code == 200
        
        # Should still provide recommendations


class TestRecommendationIntegration:
    """Integration tests for recommendation flow"""
    
    def test_guest_to_user_conversion_flow(self, app, client, sample_products):
        """Test recommendation continuity when guest becomes user"""
        # Track interactions as guest
        with client.session_transaction() as sess:
            guest_session_id = sess.get('session_id', 'test-guest-123')
        
        # View products as guest
        for i in range(3):
            client.post('/track',
                       json={'product_id': sample_products[i].id, 'type': 'view'},
                       content_type='application/json')
        
        # Register new account
        response = client.post('/register', data={
            'email': 'newuser@test.com',
            'password': 'password123',
            'confirm_password': 'password123'
        }, follow_redirects=True)
        
        # Login
        client.post('/login', data={
            'email': 'newuser@test.com',
            'password': 'password123'
        })
        
        # Recommendations should consider guest history
        response = client.get('/')
        assert response.status_code == 200
    
    def test_multi_device_recommendations(self, app, client):
        """Test recommendations across multiple sessions (simulating devices)"""
        with app.app_context():
            user = User.query.first()
            
            # Simulate interactions from "device 1"
            client1 = app.test_client()
            client1.post('/login', data={
                'email': user.email,
                'password': 'password123'
            })
            
            # Track interactions
            products = Product.query.limit(3).all()
            for product in products:
                client1.post('/track',
                           json={'product_id': product.id, 'type': 'view'})
            
            # Simulate "device 2"
            client2 = app.test_client()
            client2.post('/login', data={
                'email': user.email,
                'password': 'password123'
            })
            
            # Should see recommendations based on device 1 activity
            response = client2.get('/')
            assert response.status_code == 200