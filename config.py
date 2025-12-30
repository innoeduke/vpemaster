import os
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
dotenv_path = os.path.join(BASE_DIR, '.env')

# Load the .env file from that specific path
load_dotenv(dotenv_path=dotenv_path)


class Config:
    """Base configuration class."""

    # Get secret key and database URL from environment variables
    SECRET_KEY = os.getenv('SECRET_KEY') or 'dev-fallback-secret-key-change-in-prod'
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')

    # Flask-SQLAlchemy settings
    SQLALCHEMY_ENGINE_OPTIONS = {'pool_recycle': 280}
    SQLALCHEMY_TRACK_MODIFICATIONS = False  # Good practice

    # Session settings
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
    
    # Flask-Login settings
    REMEMBER_COOKIE_DURATION = timedelta(days=30)
    REMEMBER_COOKIE_HTTPONLY = True
    SESSION_PROTECTION = 'basic'

    # Your application-specific config

    MEETING_TYPES = {}




    DEFAULT_ROLE_ICON = "fa-question-circle"

    # Email configuration
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.googlemail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', 'noreply@example.com')

