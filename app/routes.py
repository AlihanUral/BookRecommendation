import requests
from flask import Blueprint, render_template, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from app.models import db, User, Favorite
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

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

        query = ' '.join(query_parts)
        url = f'https://openlibrary.org/search.json?q={query}&limit=40'

        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            for doc in data.get('docs', []):
                cover_id = doc.get('cover_i')
                if not cover_id:
                    continue
                books.append({
                    'id': doc.get('key').split('/')[-1],
                    'title': doc.get('title', 'Başlık yok'),
                    'authors': ', '.join(doc.get('author_name', ['Bilinmeyen'])),
                    'thumbnail': f"http://covers.openlibrary.org/b/id/{cover_id}-M.jpg",
                })
        else:
            flash('Kitap verileri alınamadı.')

    return render_template('recommend.html', books=books, genre=genre, author=author, title=title, message=None)

@bp.route('/favorite/add/<book_id>', methods=['POST'])
@login_required
def add_favorite(book_id):
    title = request.form.get('title')
    authors = request.form.get('authors')
    thumbnail = request.form.get('thumbnail')

    if not all([title, authors, thumbnail]):
        flash("Favori eklemek için tüm bilgiler gereklidir.")
        return redirect(url_for('main.recommend'))

    if Favorite.query.filter_by(user_id=current_user.id, book_id=book_id).first():
        flash("Bu kitap zaten favorilerde.")
        return redirect(url_for('main.recommend'))

    new_fav = Favorite(user_id=current_user.id, book_id=book_id, title=title, authors=authors, thumbnail=thumbnail)
    db.session.add(new_fav)
    db.session.commit()
    flash(f"'{title}' favorilere eklendi.")
    return redirect(url_for('main.recommend'))

@bp.route('/favorite/remove/<book_id>', methods=['POST'])
@login_required
def remove_favorite(book_id):
    fav = Favorite.query.filter_by(user_id=current_user.id, book_id=book_id).first()
    if fav:
        db.session.delete(fav)
        db.session.commit()
        flash("Favoriden kaldırıldı.")
    return redirect(url_for('main.favorites'))

@bp.route('/recommend/from_favorites')
@login_required
def recommend_from_favorites():
    favorites = Favorite.query.filter_by(user_id=current_user.id).all()
    if not favorites:
        flash("Favori kitap bulunamadı.")
        return redirect(url_for('main.recommend'))

    fav_descriptions = []
    for fav in favorites:
        book_id = fav.book_id
        url = f'https://openlibrary.org/works/{book_id}.json'
        res = requests.get(url)
        if res.status_code == 200:
            data = res.json()
            desc = data.get('description')
            if isinstance(desc, dict):
                desc = desc.get('value', '')
            elif isinstance(desc, str):
                desc = desc
            else:
                desc = ''
            fav_descriptions.append(desc)

    if not any(fav_descriptions):
        flash("Favori kitap açıklamaları eksik.")
        return redirect(url_for('main.recommend'))

    search_url = 'https://openlibrary.org/search.json?q=the&limit=50'
    res = requests.get(search_url)
    books = []

    if res.status_code == 200:
        data = res.json()
        for doc in data.get('docs', []):
            desc = doc.get('first_sentence') or ''
            if isinstance(desc, dict):
                desc = desc.get('value', '')
            cover_id = doc.get('cover_i')
            if not desc or not cover_id:
                continue
            books.append({
                'id': doc.get('key').split('/')[-1],
                'title': doc.get('title'),
                'authors': ', '.join(doc.get('author_name', ['Bilinmeyen'])),
                'thumbnail': f"http://covers.openlibrary.org/b/id/{cover_id}-M.jpg",
                'description': desc
            })

    if not books:
        flash("Önerilecek kitap bulunamadı.")
        return redirect(url_for('main.recommend'))

    corpus = fav_descriptions + [b['description'] for b in books]
    if not corpus:
        flash("Metin verisi eksik.")
        return redirect(url_for('main.recommend'))

    tfidf = TfidfVectorizer(stop_words='english')
    tfidf_matrix = tfidf.fit_transform(corpus)

    fav_vecs = tfidf_matrix[:len(fav_descriptions)]
    book_vecs = tfidf_matrix[len(fav_descriptions):]

    if fav_vecs.shape[0] == 0 or book_vecs.shape[0] == 0:
        flash("Vektörler oluşturulamadı.")
        return redirect(url_for('main.recommend'))

    sim_matrix = cosine_similarity(book_vecs, fav_vecs)
    max_sim = sim_matrix.max(axis=1)
    sorted_idx = max_sim.argsort()[::-1]

    recommended = [books[i] for i in sorted_idx[:10]]
    return render_template('recommend.html', books=recommended, genre='', author='', title='', message=None)

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
        if User.query.filter_by(email=email).first():
            flash("Bu e-posta zaten kayıtlı.")
            return redirect(url_for('main.register'))
        user = User(username=username, email=email, password=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        flash("Kayıt başarılı.")
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
            return redirect(url_for('main.home'))
        flash("Geçersiz giriş.")
    return render_template('login.html')

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Çıkış yapıldı.")
    return redirect(url_for('main.home'))