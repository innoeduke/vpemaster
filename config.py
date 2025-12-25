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

    MEETING_TYPES = {}

    SERIES_INITIALS = {
        "Successful Club Series": "SC",
        "Better Speaker Series": "BS",
        "Leadership Excellence Series": "LE"
    }

    # Award Categories
    BEST_SPEAKER = 'Best_Speaker'
    BEST_EVALUATOR = 'Best_Evaluator'
    BEST_TT = 'Best_TT'
    BEST_ROLETAKER = 'Best_Roletaker'

    DEFAULT_ROLE_ICON = "fa-question-circle"

    # ROLES Dictionary
    ROLES = {
        "PREPARED_SPEAKER":       {"name": "Prepared Speaker",       "unique": True,    "award": BEST_SPEAKER,   "icon": "fa-user-tie"},
        "KEYNOTE_SPEAKER":        {"name": "Keynote Speaker",        "unique": False,   "award": BEST_SPEAKER,   "icon": "fa-star"},
        "PRESENTER":              {"name": "Presenter",              "unique": True,    "award": BEST_SPEAKER,   "icon": "fa-share-alt"},
        "PANELIST":               {"name": "Panelist",               "unique": "admin", "award": None,           "icon": "fa-users"},
        "INDIVIDUAL_EVALUATOR":   {"name": "Individual Evaluator",   "unique": True,    "award": BEST_EVALUATOR, "icon": "fa-pen-square"},
        "TOPICS_SPEAKER":         {"name": "Topics Speaker",         "unique": "admin", "award": BEST_TT,        "icon": "fa-comment"},
        "TOASTMASTER":            {"name": "Toastmaster",            "unique": False,   "award": BEST_ROLETAKER, "icon": "fa-microphone"},
        "GENERAL_EVALUATOR":      {"name": "General Evaluator",      "unique": False,   "award": BEST_ROLETAKER, "icon": "fa-search"},
        "TOPICMASTER":            {"name": "Topicmaster",            "unique": False,   "award": BEST_ROLETAKER, "icon": "fa-comments"},
        "GRAMMARIAN":             {"name": "Grammarian",             "unique": False,   "award": BEST_ROLETAKER, "icon": "fa-book"},
        "TIMER":                  {"name": "Timer",                  "unique": False,   "award": BEST_ROLETAKER, "icon": "fa-stopwatch"},
        "AH_COUNTER":             {"name": "Ah-Counter",             "unique": False,   "award": BEST_ROLETAKER, "icon": "fa-calculator"},
        "DEBATER":                {"name": "Debater",                "unique": "admin", "award": None,           "icon": "fa-balance-scale"},
        "PHOTOGRAPHER":           {"name": "Photographer",           "unique": False,   "award": None,           "icon": "fa-camera"},
    }

    # Derived role configurations
    UNIQUE_ENTRY_ROLES = [
        role['name'] for role in ROLES.values() if role['unique'] is True
    ]
    ADMIN_UNIQUE_ENTRY_ROLES = [
        role['name'] for role in ROLES.values() if role['unique'] is True or role['unique'] == 'admin'
    ]
    AWARD_CATEGORIES_ROLES = {}
    for role_data in ROLES.values():
        if role_data['award']:
            if role_data['award'] not in AWARD_CATEGORIES_ROLES:
                AWARD_CATEGORIES_ROLES[role_data['award']] = []
            AWARD_CATEGORIES_ROLES[role_data['award']].append(
                role_data['name'])

    # Role Groups
    OFFICER_ROLE_GROUP = 'Officer'
