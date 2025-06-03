from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False, unique=True)
    email = db.Column(db.String(150), nullable=False, unique=True)
    password = db.Column(db.String(256), nullable=False)

    def __repr__(self):
        return f"<User {self.username}>"

class Favorite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    book_id = db.Column(db.String(100), nullable=False)  # Google/OpenLibrary kitap id'si
    title = db.Column(db.String(255))
    authors = db.Column(db.String(255))
    thumbnail = db.Column(db.String(255))

    user = db.relationship('User', backref=db.backref('favorites', lazy='dynamic'))