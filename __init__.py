from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from datetime import timedelta
from dotenv import load_dotenv
from .auth import is_authorized
import os

load_dotenv()

app = Flask(__name__)

# Secret key for session management
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['PERMANENT_SESSION_LIFETIME']=timedelta(days=30)

# pythonanywhere configuration
#app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{username}:{password}@{hostname}/{database}'
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_recycle' : 280}


app.config['PATHWAY_MAPPING'] = {
    "Dynamic Leadership": "DL",
    "Engaging Humor": "EH",
    "Motivational Strategies": "MS",
    "Persuasive Influence": "PI",
    "Presentation Mastery": "PM",
    "Visionary Communication": "VC",
    "Distinguished Toastmasters": "DTM"
}

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

@app.context_processor
def inject_authorization():
    return dict(is_authorized=is_authorized)

# Import models to ensure they are registered with the app

# Import and register the blueprints
from .agenda_routes import agenda_bp
from .contacts_routes import contacts_bp
from .speech_logs_routes import speech_logs_bp
from .users_routes import users_bp
from .main_routes import main_bp
from .pathways_routes import pathways_bp
from .tests_routes import tests_bp
from .settings_routes import settings_bp
from .booking_routes import booking_bp



app.register_blueprint(agenda_bp)
app.register_blueprint(contacts_bp)
app.register_blueprint(speech_logs_bp)
app.register_blueprint(users_bp)
app.register_blueprint(main_bp)
app.register_blueprint(pathways_bp)
app.register_blueprint(tests_bp)
app.register_blueprint(settings_bp)
app.register_blueprint(booking_bp)
