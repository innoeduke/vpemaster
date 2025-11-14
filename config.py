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
    SECRET_KEY = os.getenv('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')

    # Flask-SQLAlchemy settings
    SQLALCHEMY_ENGINE_OPTIONS = {'pool_recycle': 280}
    SQLALCHEMY_TRACK_MODIFICATIONS = False  # Good practice

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

    MEETING_TYPES = {
        "Club Election": {
            "owner_role_id": 45, "template": "club_election.csv"
        },
        "Debate": {
            "owner_role_id": 40, "template": "debate.csv"
        },
        "Keynote Speech": {
            "owner_role_id": 20, "template": "default.csv"
        },
        "Panel Discussion": {
            "owner_role_id": 44, "template": "panel_discussion.csv"
        },
        "Speech Contest": {
            "owner_role_id": 3, "template": "speech_contest.csv"
        },
        "Speech Marathon": {
            "owner_role_id": 3, "template": "speech_marathon.csv"
        }
    }

    SERIES_INITIALS = {
        "Successful Club Series": "SC",
        "Better Speaker Series": "BS",
        "Leadership Excellence Series": "LE"
    }
