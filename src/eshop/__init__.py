from flask import Flask
from flask_login import LoginManager
from .config import Config
from .models import db, User

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

import eshop.views

with app.app_context():
    db.create_all()
