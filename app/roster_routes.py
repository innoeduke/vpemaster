from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from .auth.utils import login_required, is_authorized
from .auth.permissions import Permissions
from .models import Roster, Meeting, Contact, ContactClub
from .club_context import get_current_club_id, authorized_club_required
from . import db
from sqlalchemy import distinct

roster_bp = Blueprint('roster_bp', __name__)


@roster_bp.route('/', methods=['GET'])
@login_required
@authorized_club_required
def roster():
    """Redirect standalone roster page to the Tools tab"""
    return redirect(url_for('tools_bp.tools', tab='roster'))


# API endpoints moved to tools_routes.py to consolidate Tools functionality.

