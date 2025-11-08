import os
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Base configuration class."""
    
    # Get secret key and database URL from environment variables
    SECRET_KEY = os.getenv('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
    
    # Flask-SQLAlchemy settings
    SQLALCHEMY_ENGINE_OPTIONS = {'pool_recycle': 280}
    SQLALCHEMY_TRACK_MODIFICATIONS = False # Good practice
    
    # Session settings
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
    
    # Your application-specific config
    PATHWAY_MAPPING = {
        "Dynamic Leadership": "DL",
        "Engaging Humor": "EH",
        "Motivational Strategies": "MS",
        "Persuasive Influence": "PI",
        "Presentation Mastery": "PM",
        "Visionary Communication": "VC",
        "Distinguished Toastmasters": "DTM"
    }