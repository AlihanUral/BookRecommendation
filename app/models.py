from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), nullable=False, unique=True)
    email = db.Column(db.String(120), nullable=False, unique=True)
    password_hash = db.Column(db.String(128), nullable=False)
    playlists = db.relationship('Playlist', backref='user', lazy='dynamic')
    favorites = db.relationship('Favorite', backref='user', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<User {self.username}>"

    def get_favorite_count(self):
        return self.favorites.count()

    def get_playlist_count(self):
        return self.playlists.count()

class Favorite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    book_id = db.Column(db.String(100), nullable=False)  # Google Books kitap id'si
    title = db.Column(db.String(255))
    authors = db.Column(db.String(255))
    thumbnail = db.Column(db.String(255))
    description = db.Column(db.Text)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'book_id', name='unique_user_book'),
    )

    def __repr__(self):
        return f"<Favorite {self.title}>"

class Playlist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    books = db.relationship('PlaylistBook', backref='playlist', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Playlist {self.name}>"

    def get_book_count(self):
        return self.books.count()

    def get_source_books(self):
        return self.books.filter_by(is_source=True).all()

    def get_recommended_books(self):
        return self.books.filter_by(is_source=False).all()

class PlaylistBook(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    playlist_id = db.Column(db.Integer, db.ForeignKey('playlist.id'), nullable=False)
    book_id = db.Column(db.String(100), nullable=False)
    title = db.Column(db.String(255))
    authors = db.Column(db.String(255))
    thumbnail = db.Column(db.String(255))
    description = db.Column(db.Text)
    is_source = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f"<PlaylistBook {self.title}>"