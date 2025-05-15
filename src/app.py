from flask import Flask, render_template, send_from_directory
import os

app = Flask(__name__)

@app.route('/')
def home():
    # Sample data for product recommendations
    recommended_products = [
        {
            'id': 1,
            'name': 'Premium Wireless Headphones',
            'price': 129.99,
            'image': 'placeholder.jpg',
            'description': 'Noise-cancelling wireless headphones with premium sound quality.'
        },
        {
            'id': 2,
            'name': 'Smart Fitness Watch',
            'price': 89.99,
            'image': 'placeholder.jpg',
            'description': 'Track your fitness goals with this advanced smart watch.'
        },
        {
            'id': 3,
            'name': 'Portable Power Bank',
            'price': 49.99,
            'image': 'placeholder.jpg',
            'description': '20,000mAh power bank for all your charging needs on the go.'
        },
        {
            'id': 4,
            'name': 'Wireless Bluetooth Speaker',
            'price': 79.99,
            'image': 'placeholder.jpg',
            'description': 'Waterproof speaker with 360° sound and 12-hour battery life.'
        }
    ]
    
    return render_template('index.html', recommended_products=recommended_products)

@app.route('/static/images/<path:filename>')
def serve_placeholder(filename):
    # For simplicity, serve a placeholder for all image requests
    return send_from_directory(os.path.join(app.root_path, 'static'), 'style.css')

if __name__ == '__main__':
    app.run(debug=True)