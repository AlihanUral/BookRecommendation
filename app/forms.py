from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, IntegerField, SelectField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional, NumberRange

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[
        DataRequired(),
        Length(min=3, max=20, message='Username must be between 3 and 20 characters')
    ])
    email = StringField('Email', validators=[
        DataRequired(),
        Email(message='Please enter a valid email address')
    ])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=6, message='Password must be at least 6 characters long')
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])
    submit = SubmitField('Register')

class ReviewForm(FlaskForm):
    rating = IntegerField('Rating', validators=[
        DataRequired(),
        NumberRange(min=1, max=5, message='Rating must be between 1 and 5')
    ])
    review_text = TextAreaField('Review', validators=[
        Optional(),
        Length(max=1000, message='Review cannot be longer than 1000 characters')
    ])
    submit = SubmitField('Submit Review')

class PlaylistForm(FlaskForm):
    name = StringField('Playlist Name', validators=[
        DataRequired(),
        Length(min=1, max=100, message='Playlist name must be between 1 and 100 characters')
    ])
    submit = SubmitField('Create Playlist')

class SearchForm(FlaskForm):
    query = StringField('Search', validators=[Optional()])
    genre = StringField('Genre', validators=[Optional()])
    author = StringField('Author', validators=[Optional()])
    sort_by = SelectField('Sort By', choices=[
        ('relevance', 'Relevance'),
        ('newest', 'Newest'),
        ('rating', 'Rating')
    ], validators=[Optional()])
    submit = SubmitField('Search')
