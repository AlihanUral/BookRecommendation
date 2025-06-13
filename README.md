# Book Recommender System

A Flask-based web application that helps users discover and organize books based on their preferences.

## Features

- User authentication and profile management
- Book search and recommendations
- Create and manage playlists
- Save favorite books
- PDF report generation
- Machine learning-based book recommendations

## Tech Stack

- **Backend**: Flask 3.0.2
- **Database**: SQLAlchemy
- **Authentication**: Flask-Login
- **Machine Learning**: scikit-learn
- **PDF Generation**: reportlab
- **Frontend**: HTML, CSS, JavaScript

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/book_recommender.git
cd book_recommender
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
Create a `.env` file in the root directory and add:
```
FLASK_APP=run.py
FLASK_ENV=development
SECRET_KEY=your-secret-key
```

5. Initialize the database:
```bash
flask db init
flask db migrate
flask db upgrade
```

6. Run the application:
```bash
flask run
```

## Usage

1. Register a new account or login
2. Search for books
3. Create playlists and add books
4. Get personalized book recommendations
5. Save favorite books
6. Generate PDF reports

## Contributing

1. Fork the repository
2. Create a new branch
3. Make your changes
4. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 