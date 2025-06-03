
import requests
from flask import Blueprint, render_template, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from app.models import db, User, Favorite

bp = Blueprint('main', __name__)

@bp.route('/')
def home():
    return render_template('home.html')

@bp.route('/recommend', methods=['GET', 'POST'])
@login_required
def recommend():
    books = []
    genre = ''
    author = ''
    title = ''
    query = ''

    if request.method == 'POST':
        genre = request.form.get('genre', '').strip()
        author = request.form.get('author', '').strip()
        title = request.form.get('title', '').strip()

        query_parts = []
        if title:
            query_parts.append(f'intitle:{title}')
        if author:
            query_parts.append(f'author:{author}')
        if genre:
            query_parts.append(f'subject:{genre}')

        query = ' '.join(query_parts) if query_parts else ''

        url = f'https://openlibrary.org/search.json?q={query}&limit=40'

        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            for doc in data.get('docs', []):
                cover_id = doc.get('cover_i')
                if not cover_id:
                    continue  # Kapak resmi yoksa ekleme

                books.append({
                    'id': doc.get('key').split('/')[-1],  # OpenLibrary kitap id
                    'title': doc.get('title', 'Başlık yok'),
                    'authors': ', '.join(doc.get('author_name', ['Bilinmeyen'])),
                    'thumbnail': f"http://covers.openlibrary.org/b/id/{cover_id}-M.jpg",
                })
        else:
            flash('Kitap verileri alınamadı. Lütfen daha sonra tekrar deneyin.')

    return render_template('recommend.html', books=books, genre=genre, author=author, title=title, query=query)


@bp.route('/favorite/add/<book_id>', methods=['POST'])
@login_required
def add_favorite(book_id):
    title = request.form.get('title')
    authors = request.form.get('authors')
    thumbnail = request.form.get('thumbnail')

    if not all([title, authors, thumbnail]):
        flash("Favori eklemek için kitap başlığı, yazar ve kapak resmi gereklidir.")
        return redirect(url_for('main.recommend'))

    existing = Favorite.query.filter_by(user_id=current_user.id, book_id=book_id).first()
    if existing:
        flash("Bu kitap zaten favorilerinizde.")
        return redirect(url_for('main.recommend'))

    favorite = Favorite(user_id=current_user.id, book_id=book_id, title=title, authors=authors, thumbnail=thumbnail)
    db.session.add(favorite)
    db.session.commit()
    flash(f"'{title}' favorilere eklendi.")
    return redirect(url_for('main.recommend'))


@bp.route('/favorite/remove/<book_id>', methods=['POST'])
@login_required
def remove_favorite(book_id):
    favorite = Favorite.query.filter_by(user_id=current_user.id, book_id=book_id).first()
    if favorite:
        db.session.delete(favorite)
        db.session.commit()
        flash("Favorilerden kaldırıldı.")
    else:
        flash("Kitap favorilerinizde bulunamadı.")
    return redirect(url_for('main.favorites'))


@bp.route('/favorites')
@login_required
def favorites():
    favs = Favorite.query.filter_by(user_id=current_user.id).all()
    return render_template('favorites.html', favorites=favs)


@bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Bu e-posta ile kayıtlı bir kullanıcı zaten var.')
            return redirect(url_for('main.register'))

        hashed_password = generate_password_hash(password)
        new_user = User(username=username, email=email, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash('Kayıt başarılı! Giriş yapabilirsiniz.')
        return redirect(url_for('main.login'))

    return render_template('register.html')


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('Başarıyla giriş yaptınız.')
            return redirect(url_for('main.home'))
        else:
            flash('Geçersiz e-posta veya şifre.')
    return render_template('login.html')


@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Çıkış yapıldı.')
    return redirect(url_for('main.home'))