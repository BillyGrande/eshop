from flask import Flask
from flask_login import LoginManager
from .config import Config
from .models import db, User

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    db.init_app(app)
    
    login_manager = LoginManager(app)
    login_manager.login_view = 'auth.login'
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    from .auth import auth
    app.register_blueprint(auth)
    
    from .views import main
    app.register_blueprint(main)
    
    from .cart import cart
    app.register_blueprint(cart)
    
    from .checkout import checkout
    app.register_blueprint(checkout)
    
    with app.app_context():
        db.create_all()
    
    return app

app = create_app()
