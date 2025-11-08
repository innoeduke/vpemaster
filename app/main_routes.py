from flask import Blueprint, redirect, url_for
from .auth.utils import login_required

main_bp = Blueprint('main_bp', __name__)

@main_bp.route('/')
@login_required
def index():
    return redirect(url_for('agenda_bp.agenda'))