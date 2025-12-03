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
            "owner_role_id": 45, "template": "club_election.csv",
            "background_color": "#FFDDC1", "foreground_color": "#000000"
        },
        "Debate": {
            "owner_role_id": 40, "template": "debate.csv",
            "background_color": "#D4F1F4", "foreground_color": "#000000"
        },
        "Keynote Speech": {
            "owner_role_id": 20, "template": "default.csv",
            "background_color": "#C1E1C1", "foreground_color": "#000000"
        },
        "Panel Discussion": {
            "owner_role_id": 44, "template": "panel_discussion.csv",
            "background_color": "#F0E68C", "foreground_color": "#000000"
        },
        "Speech Contest": {
            "owner_role_id": 3, "template": "speech_contest.csv",
            "background_color": "#E6E6FA", "foreground_color": "#000000"
        },
        "Speech Marathon": {
            "owner_role_id": 3, "template": "speech_marathon.csv",
            "background_color": "#FFC0CB", "foreground_color": "#000000"
        }
    }

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
