import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from app.models import db, User

def create_app():
    app = Flask(__name__, instance_relative_config=True)

    # Gizli anahtar ve veritabanı konfigürasyonu
    app.config['SECRET_KEY'] = 'gizli-bir-anahtar'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Veritabanı başlatma
    db.init_app(app)
    migrate = Migrate(app, db)

    # Login manager ayarları
    login_manager = LoginManager()
    login_manager.login_view = 'main.login'  # Blueprint ile login sayfası adresi
    login_manager.init_app(app)

    # Kullanıcı yükleyici fonksiyon
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Blueprint import ve kayıt
    from app.routes import bp as routes_bp
    app.register_blueprint(routes_bp)

    return app