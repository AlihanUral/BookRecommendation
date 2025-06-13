import requests
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from app.models import db, User, Favorite, Playlist, PlaylistBook
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import os
import time
from functools import wraps
from datetime import datetime
import tempfile
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

bp = Blueprint('main', __name__)

# Google Books API configuration
GOOGLE_BOOKS_API_KEY = os.getenv('GOOGLE_BOOKS_API_KEY', '')
GOOGLE_BOOKS_API_URL = 'https://www.googleapis.com/books/v1/volumes'

# Rate limiting configuration
RATE_LIMIT_DELAY = 1  # seconds between API calls
last_api_call = 0

def rate_limit_api():
    """Rate limiting decorator for Google Books API calls"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            global last_api_call
            current_time = time.time()
            time_since_last_call = current_time - last_api_call
            
            if time_since_last_call < RATE_LIMIT_DELAY:
                time.sleep(RATE_LIMIT_DELAY - time_since_last_call)
            
            last_api_call = time.time()
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@rate_limit_api()
def fetch_book_details(book_id):
    """Fetch book details from Google Books API with error handling"""
    try:
        url = f'{GOOGLE_BOOKS_API_URL}/{book_id}?key={GOOGLE_BOOKS_API_KEY}'
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 429:  # Too Many Requests
            time.sleep(2)  # Wait longer on rate limit
            return fetch_book_details(book_id)  # Retry
        else:
            print(f"Error fetching book {book_id}: {response.status_code}")
            return None
    except Exception as e:
        print(f"Exception fetching book {book_id}: {str(e)}")
        return None

@rate_limit_api()
def search_books(query, max_results=10):
    """Search books from Google Books API with error handling"""
    try:
        url = f'{GOOGLE_BOOKS_API_URL}?q={query}&maxResults={max_results}&key={GOOGLE_BOOKS_API_KEY}'
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 429:  # Too Many Requests
            time.sleep(2)  # Wait longer on rate limit
            return search_books(query, max_results)  # Retry
        else:
            print(f"Error searching books: {response.status_code}")
            return None
    except Exception as e:
        print(f"Exception searching books: {str(e)}")
        return None

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
            query_parts.append(f'inauthor:{author}')
        if genre:
            query_parts.append(f'subject:{genre}')

        query = ' '.join(query_parts)
        url = f'{GOOGLE_BOOKS_API_URL}?q={query}&maxResults=40&key={GOOGLE_BOOKS_API_KEY}'

        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            for item in data.get('items', []):
                volume_info = item.get('volumeInfo', {})
                if not volume_info.get('imageLinks'):
                    continue
                
                books.append({
                    'id': item.get('id'),
                    'title': volume_info.get('title', 'Başlık yok'),
                    'authors': ', '.join(volume_info.get('authors', ['Bilinmeyen'])),
                    'thumbnail': volume_info.get('imageLinks', {}).get('thumbnail', ''),
                    'description': volume_info.get('description', ''),
                    'categories': volume_info.get('categories', []),
                    'averageRating': volume_info.get('averageRating', 0),
                    'ratingsCount': volume_info.get('ratingsCount', 0)
                })
        else:
            flash('Kitap verileri alınamadı.', 'danger')

    return render_template('recommend.html', books=books, genre=genre, author=author, title=title, message=None)

@bp.route('/favorite/add/<book_id>', methods=['POST'])
@login_required
def add_favorite(book_id):
    title = request.form.get('title')
    authors = request.form.get('authors')
    thumbnail = request.form.get('thumbnail')
    description = request.form.get('description', '')

    if not all([title, authors, thumbnail]):
        flash("Favori eklemek için tüm bilgiler gereklidir.", 'warning')
        return redirect(url_for('main.recommend'))

    if Favorite.query.filter_by(user_id=current_user.id, book_id=book_id).first():
        flash("Bu kitap zaten favorilerde.", 'info')
        return redirect(url_for('main.recommend'))

    new_fav = Favorite(
        user_id=current_user.id, 
        book_id=book_id, 
        title=title, 
        authors=authors, 
        thumbnail=thumbnail,
        description=description
    )
    db.session.add(new_fav)
    db.session.commit()
    flash(f"'{title}' favorilere eklendi.", 'success')
    return redirect(url_for('main.recommend'))

@bp.route('/favorite/remove/<book_id>', methods=['POST'])
@login_required
def remove_favorite(book_id):
    fav = Favorite.query.filter_by(user_id=current_user.id, book_id=book_id).first()
    if fav:
        db.session.delete(fav)
        db.session.commit()
        flash("Favoriden kaldırıldı.", 'success')
    return redirect(url_for('main.favorites'))

@bp.route('/favorites')
@login_required
def favorites():
    favs = Favorite.query.filter_by(user_id=current_user.id).all()
    return render_template('favorites.html', favorites=favs)

@bp.route('/playlist/create', methods=['GET', 'POST'])
@login_required
def create_playlist():
    print("Entering create_playlist route")
    if request.method == 'POST':
        print("Processing POST request")
        playlist_name = request.form.get('playlist_name')
        if not playlist_name:
            flash('Lütfen bir liste adı girin.', 'warning')
            return redirect(url_for('main.create_playlist'))
        
        # Get favorites and generate recommendations
        favorites = Favorite.query.filter_by(user_id=current_user.id).all()
        print(f"Found {len(favorites)} favorite books")
        
        if not favorites:
            flash('Liste oluşturmak için favori kitap eklemelisiniz.', 'info')
            return redirect(url_for('main.favorites'))
        
        try:
            # Create new playlist
            playlist = Playlist(user_id=current_user.id, name=playlist_name)
            db.session.add(playlist)
            db.session.flush()  # Get playlist ID
            print(f"Created playlist with ID: {playlist.id}")
            
            # Add source books to playlist
            for fav in favorites:
                playlist_book = PlaylistBook(
                    playlist_id=playlist.id,
                    book_id=fav.book_id,
                    title=fav.title,
                    authors=fav.authors,
                    thumbnail=fav.thumbnail,
                    description=fav.description,
                    is_source=True
                )
                db.session.add(playlist_book)
            print("Added source books to playlist")
            
            # Get recommendations
            print("Getting recommendations...")
            recommended_books = get_recommendations(favorites)
            print(f"Got {len(recommended_books)} recommendations")
            
            # Add recommended books to playlist
            for book in recommended_books:
                playlist_book = PlaylistBook(
                    playlist_id=playlist.id,
                    book_id=book['id'],
                    title=book['title'],
                    authors=book['authors'],
                    thumbnail=book['thumbnail'],
                    description=book.get('description', ''),
                    is_source=False
                )
                db.session.add(playlist_book)
            print("Added recommended books to playlist")
            
            # Clear favorites
            Favorite.query.filter_by(user_id=current_user.id).delete()
            print("Cleared favorites")
            
            db.session.commit()
            print("Committed changes to database")
            flash('Kitap listesi başarıyla oluşturuldu.', 'success')
            return redirect(url_for('main.playlists'))
            
        except Exception as e:
            db.session.rollback()
            print(f"Error creating playlist: {str(e)}")
            flash('Liste oluşturulurken bir hata oluştu. Lütfen daha sonra tekrar deneyin.', 'danger')
            return redirect(url_for('main.favorites'))
    
    # GET request - show create playlist form
    print("Processing GET request")
    favorites = Favorite.query.filter_by(user_id=current_user.id).all()
    if not favorites:
        flash('Liste oluşturmak için favori kitap eklemelisiniz.', 'info')
        return redirect(url_for('main.favorites'))
    
    try:
        print("Getting recommendations for preview...")
        recommended_books = get_recommendations(favorites)
        print(f"Got {len(recommended_books)} recommendations for preview")
        return render_template('create_playlist.html', 
                            source_books=favorites,
                            recommended_books=recommended_books)
    except Exception as e:
        print(f"Error getting recommendations for preview: {str(e)}")
        flash('Öneriler yüklenirken bir hata oluştu. Lütfen daha sonra tekrar deneyin.', 'danger')
        return redirect(url_for('main.favorites'))

@bp.route('/playlists')
@login_required
def playlists():
    user_playlists = Playlist.query.filter_by(user_id=current_user.id).order_by(Playlist.created_at.desc()).all()
    return render_template('playlists.html', playlists=user_playlists)

@bp.route('/playlist/delete/<int:playlist_id>', methods=['POST'])
@login_required
def delete_playlist(playlist_id):
    playlist = Playlist.query.get_or_404(playlist_id)
    if playlist.user_id != current_user.id:
        flash('Bu listeyi silme yetkiniz yok.', 'danger')
        return redirect(url_for('main.playlists'))
    
    db.session.delete(playlist)
    db.session.commit()
    flash('Liste başarıyla silindi.', 'success')
    return redirect(url_for('main.playlists'))

@bp.route('/playlist/<int:playlist_id>/export')
@login_required
def export_playlist(playlist_id):
    playlist = Playlist.query.get_or_404(playlist_id)
    if playlist.user_id != current_user.id:
        flash('Bu listeye erişim izniniz yok.', 'danger')
        return redirect(url_for('main.playlists'))
    
    # Create a temporary file
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
        # Create PDF document
        doc = SimpleDocTemplate(tmp.name, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []
        
        # Add title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            textColor=colors.HexColor('#0d6efd')
        )
        story.append(Paragraph(playlist.name, title_style))
        story.append(Spacer(1, 12))
        
        # Add creation date
        date_style = ParagraphStyle(
            'Date',
            parent=styles['Normal'],
            fontSize=12,
            textColor=colors.gray
        )
        story.append(Paragraph(f"Oluşturulma Tarihi: {playlist.created_at.strftime('%d.%m.%Y')}", date_style))
        story.append(Spacer(1, 30))
        
        # Add source books section
        story.append(Paragraph("Kaynak Kitaplar", styles['Heading2']))
        story.append(Spacer(1, 12))
        
        source_books = playlist.books.filter_by(is_source=True).all()
        if source_books:
            source_data = [['Kitap Adı', 'Yazar']]
            for book in source_books:
                source_data.append([book.title, book.authors])
            
            source_table = Table(source_data, colWidths=[3*inch, 3*inch])
            source_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f8f9fa')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#0d6efd')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#dee2e6')),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('TOPPADDING', (0, 1), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ]))
            story.append(source_table)
        
        story.append(Spacer(1, 30))
        
        # Add recommended books section
        story.append(Paragraph("Önerilen Kitaplar", styles['Heading2']))
        story.append(Spacer(1, 12))
        
        recommended_books = playlist.books.filter_by(is_source=False).all()
        if recommended_books:
            rec_data = [['Kitap Adı', 'Yazar']]
            for book in recommended_books:
                rec_data.append([book.title, book.authors])
            
            rec_table = Table(rec_data, colWidths=[3*inch, 3*inch])
            rec_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f8f9fa')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#0d6efd')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#dee2e6')),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('TOPPADDING', (0, 1), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ]))
            story.append(rec_table)
        
        # Add footer
        story.append(Spacer(1, 30))
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.gray,
            alignment=1  # Center alignment
        )
        story.append(Paragraph("Bu liste BookRec tarafından oluşturulmuştur.", footer_style))
        story.append(Paragraph("© 2024 BookRec. Tüm hakları saklıdır.", footer_style))
        
        # Build PDF
        doc.build(story)
        tmp_path = tmp.name
    
    try:
        # Send the file
        return send_file(
            tmp_path,
            as_attachment=True,
            download_name=f"{playlist.name.replace(' ', '_')}.pdf",
            mimetype='application/pdf'
        )
    finally:
        # Clean up the temporary file
        os.unlink(tmp_path)

def get_recommendations(favorites):
    """
    Enhanced book recommendation system using multiple features and improved similarity metrics.
    """
    print("Starting recommendation process")
    
    # Get descriptions and metadata from favorites
    fav_data = []
    for fav in favorites:
        try:
            print(f"Fetching data for favorite book: {fav.title}")
            # Try to get detailed book info from Google Books API
            url = f'{GOOGLE_BOOKS_API_URL}/{fav.book_id}?key={GOOGLE_BOOKS_API_KEY}'
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                volume_info = data.get('volumeInfo', {})
                
                # Combine multiple features for better matching
                book_features = {
                    'description': volume_info.get('description', fav.description or ''),
                    'categories': volume_info.get('categories', []),
                    'authors': volume_info.get('authors', []),
                    'publisher': volume_info.get('publisher', ''),
                    'publishedDate': volume_info.get('publishedDate', ''),
                    'averageRating': volume_info.get('averageRating', 0),
                    'ratingsCount': volume_info.get('ratingsCount', 0),
                    'maturityRating': volume_info.get('maturityRating', ''),
                    'language': volume_info.get('language', '')
                }
                
                print(f"Successfully fetched data for {fav.title}")
                fav_data.append(book_features)
                
                # Update favorite with new data if available
                if volume_info.get('description'):
                    fav.description = volume_info.get('description')
                    db.session.commit()
            else:
                print(f"Failed to fetch data for {fav.title}. Status code: {response.status_code}")
                # Use existing data if API call fails
                fav_data.append({
                    'description': fav.description or '',
                    'categories': [],
                    'authors': fav.authors.split(', ') if fav.authors else [],
                    'publisher': '',
                    'publishedDate': '',
                    'averageRating': 0,
                    'ratingsCount': 0,
                    'maturityRating': '',
                    'language': ''
                })
        except Exception as e:
            print(f"Error fetching book data for {fav.book_id}: {str(e)}")
            # Use existing data if API call fails
            fav_data.append({
                'description': fav.description or '',
                'categories': [],
                'authors': fav.authors.split(', ') if fav.authors else [],
                'publisher': '',
                'publishedDate': '',
                'averageRating': 0,
                'ratingsCount': 0,
                'maturityRating': '',
                'language': ''
            })

    if not fav_data:
        print("No favorite data available")
        return []

    # Extract common features from favorites
    common_categories = set()
    common_authors = set()
    for book in fav_data:
        common_categories.update(book['categories'])
        common_authors.update(book['authors'])

    print(f"Common categories: {common_categories}")
    print(f"Common authors: {common_authors}")

    # Build search queries based on favorite features
    search_queries = []
    
    # Add author-based queries (reduced weight)
    for author in common_authors:
        search_queries.append(f'inauthor:"{author}"')
    
    # Add category-based queries
    for category in common_categories:
        search_queries.append(f'subject:{category}')
    
    # Add discovery queries for popular books
    search_queries.append('orderBy=newest')  # New releases
    search_queries.append('orderBy=relevance&filter=paid-ebooks')  # Popular paid books
    search_queries.append('orderBy=relevance&filter=free-ebooks')  # Popular free books

    print(f"Search queries: {search_queries}")

    # Search for books using Google Books API
    books = []
    seen_book_ids = set(fav.book_id for fav in favorites)
    
    for query in search_queries:
        try:
            print(f"Searching with query: {query}")
            search_url = f'{GOOGLE_BOOKS_API_URL}?q={query}&maxResults=10&key={GOOGLE_BOOKS_API_KEY}'
            res = requests.get(search_url, timeout=10)
            
            if res.status_code == 200:
                data = res.json()
                items = data.get('items', [])
                print(f"Found {len(items)} books for query: {query}")
                
                for item in items:
                    book_id = item.get('id')
                    if book_id in seen_book_ids:
                        continue
                    
                    volume_info = item.get('volumeInfo', {})
                    if not volume_info.get('imageLinks'):
                        continue

                    # Get detailed book info
                    try:
                        book_url = f'{GOOGLE_BOOKS_API_URL}/{book_id}?key={GOOGLE_BOOKS_API_KEY}'
                        book_res = requests.get(book_url, timeout=10)
                        if book_res.status_code == 200:
                            book_data = book_res.json().get('volumeInfo', {})
                            
                            # Combine features for similarity calculation
                            book_features = {
                                'id': book_id,
                                'title': book_data.get('title'),
                                'authors': ', '.join(book_data.get('authors', ['Bilinmeyen'])),
                                'thumbnail': book_data.get('imageLinks', {}).get('thumbnail', ''),
                                'description': book_data.get('description', ''),
                                'categories': book_data.get('categories', []),
                                'publisher': book_data.get('publisher', ''),
                                'publishedDate': book_data.get('publishedDate', ''),
                                'averageRating': book_data.get('averageRating', 0),
                                'ratingsCount': book_data.get('ratingsCount', 0),
                                'maturityRating': book_data.get('maturityRating', ''),
                                'language': book_data.get('language', '')
                            }
                            
                            books.append(book_features)
                            seen_book_ids.add(book_id)
                            print(f"Added book: {book_features['title']}")
                            
                            # Limit total number of books to 40 (increased from 30)
                            if len(books) >= 40:
                                break
                    except Exception as e:
                        print(f"Error fetching detailed book info for {book_id}: {str(e)}")
                        continue
                    
                # Break if we have enough books
                if len(books) >= 40:
                    break
            else:
                print(f"Failed to fetch books for query {query}. Status code: {res.status_code}")
        except Exception as e:
            print(f"Error fetching books for query {query}: {str(e)}")
            continue

    print(f"Total books found: {len(books)}")

    if not books:
        print("No books found for recommendations")
        return []

    # Calculate similarity scores using multiple features
    def calculate_similarity(fav_book, candidate_book):
        score = 0.0
        
        # Text similarity using TF-IDF (increased weight)
        if fav_book['description'] and candidate_book['description']:
            try:
                tfidf = TfidfVectorizer(
                    stop_words='english',
                    max_features=1000,
                    ngram_range=(1, 1),
                    min_df=1,
                    max_df=1.0,
                    strip_accents='unicode',
                    lowercase=True
                )
                tfidf_matrix = tfidf.fit_transform([fav_book['description'], candidate_book['description']])
                text_similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
                score += text_similarity * 0.5  # Increased from 0.4
            except Exception as e:
                print(f"Error calculating text similarity: {str(e)}")

        # Category similarity (increased weight)
        fav_categories = set(fav_book['categories'])
        candidate_categories = set(candidate_book['categories'])
        if fav_categories and candidate_categories:
            category_similarity = len(fav_categories.intersection(candidate_categories)) / len(fav_categories.union(candidate_categories))
            score += category_similarity * 0.3  # Same weight

        # Author similarity (reduced weight)
        fav_authors = set(fav_book['authors'])
        candidate_authors = set(candidate_book['authors'].split(', '))
        if fav_authors and candidate_authors:
            author_similarity = len(fav_authors.intersection(candidate_authors)) / len(fav_authors.union(candidate_authors))
            score += author_similarity * 0.1  # Reduced from 0.2

        # Publisher similarity (removed weight)
        # if fav_book['publisher'] and candidate_book['publisher']:
        #     if fav_book['publisher'] == candidate_book['publisher']:
        #         score += 0.1

        # Add diversity bonus for books with different authors
        if not fav_authors.intersection(candidate_authors):
            score += 0.1  # Bonus for different authors

        return score

    # Calculate similarity scores for each book
    scored_books = []
    for book in books:
        max_similarity = 0
        for fav_book in fav_data:
            similarity = calculate_similarity(fav_book, book)
            max_similarity = max(max_similarity, similarity)
        
        # Add rating bonus (increased weight)
        rating_bonus = 0
        if book['averageRating'] and book['ratingsCount']:
            rating_bonus = (book['averageRating'] / 5) * (min(book['ratingsCount'], 1000) / 1000)
        
        final_score = max_similarity + (rating_bonus * 0.2)  # Increased from 0.1
        scored_books.append((book, final_score))

    # Sort books by similarity score and get top recommendations
    scored_books.sort(key=lambda x: x[1], reverse=True)
    
    # Ensure diversity in recommendations
    final_recommendations = []
    seen_authors = set()
    seen_categories = set()
    
    for book, score in scored_books:
        book_authors = set(book['authors'].split(', '))
        book_categories = set(book['categories'])
        
        # Check if this book adds diversity
        if (not book_authors.intersection(seen_authors) or 
            not book_categories.intersection(seen_categories) or 
            len(final_recommendations) < 5):  # Always include top 5 books
            
            final_recommendations.append(book)
            seen_authors.update(book_authors)
            seen_categories.update(book_categories)
            
            if len(final_recommendations) >= 10:
                break
    
    return final_recommendations

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Validation
        if not all([username, email, password, confirm_password]):
            flash('Tüm alanları doldurun.', 'warning')
            return render_template('register.html')
        
        if password != confirm_password:
            flash('Şifreler eşleşmiyor.', 'danger')
            return render_template('register.html')
        
        if len(password) < 6:
            flash('Şifre en az 6 karakter olmalıdır.', 'warning')
            return render_template('register.html')
        
        if User.query.filter_by(username=username).first():
            flash('Bu kullanıcı adı zaten kullanılıyor.', 'danger')
            return render_template('register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Bu e-posta adresi zaten kullanılıyor.', 'danger')
            return render_template('register.html')
        
        # Create new user
        new_user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password, method='pbkdf2:sha256')
        )
        
        try:
            db.session.add(new_user)
            db.session.commit()
            flash('Hesabınız başarıyla oluşturuldu! Şimdi giriş yapabilirsiniz.', 'success')
            return redirect(url_for('main.login'))
        except Exception as e:
            db.session.rollback()
            flash('Hesap oluşturulurken bir hata oluştu. Lütfen daha sonra tekrar deneyin.', 'danger')
            print(f"Error creating user: {str(e)}")
    
    return render_template('register.html')

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash('Başarıyla giriş yaptınız!', 'success')
            return redirect(url_for('main.home'))
        else:
            flash('Geçersiz kullanıcı adı veya şifre.', 'danger')
    
    return render_template('login.html')

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Çıkış yapıldı.", 'info')
    return redirect(url_for('main.home'))