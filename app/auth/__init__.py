from flask import Blueprint

# Define the blueprint
auth_bp = Blueprint('auth_bp', __name__, template_folder='templates')

# Import the routes to register them with the blueprint
from . import routes