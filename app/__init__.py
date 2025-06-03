import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from app.models import db, User

def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config['SECRET_KEY'] = 'gizli-bir-anahtar'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.instance_path, 'site.db')

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = 'main.login'  # Blueprint ile 'main.login' kullan
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from app.routes import bp as routes_bp  # Bu satır hata veriyorsa dosya yolu yanlış veya dosya okunamıyor
    app.register_blueprint(routes_bp)

    return app