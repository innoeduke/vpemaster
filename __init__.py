from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt

app = Flask(__name__)

# Secret key for session management
app.config['SECRET_KEY'] = 'your_super_secret_key_here' # Replace with your secret key

# Configure the database connection
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqldb://shltmc:SHLTMC_leadership_D8@shltmc.mysql.pythonanywhere-services.com/shltmc$Education'
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_recycle' : 280}

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

# Import models to ensure they are registered with the app

# Import and register the blueprints
from .agenda_routes import agenda_bp
from .contacts_routes import contacts_bp
from .speech_logs_routes import speech_logs_bp
from .users_routes import users_bp
from .main_routes import main_bp
from .pathways_routes import pathways_bp


app.register_blueprint(agenda_bp)
app.register_blueprint(contacts_bp)
app.register_blueprint(speech_logs_bp)
app.register_blueprint(users_bp)
app.register_blueprint(main_bp)
app.register_blueprint(pathways_bp)
