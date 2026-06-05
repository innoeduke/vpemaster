from flask import Blueprint, render_template, redirect, url_for, request, jsonify
from flask_login import current_user
from .auth.utils import login_required, is_authorized
from .auth.permissions import Permissions, permission_required
from .models import Roster, Meeting, Contact, ContactClub, Pathway, Ticket
from .club_context import get_current_club_id, authorized_club_required
from . import db
from sqlalchemy import distinct
from .utils import get_meetings_by_status
from .services.role_service import RoleService
from .constants import RoleID

from .pathways_routes import get_pathway_library_data

import re
import uuid
import threading

tools_bp = Blueprint('tools_bp', __name__)



@tools_bp.route('/', methods=['GET'])
def tools():
    has_lucky_draw_access = current_user.is_authenticated
    has_pathways_access = is_authorized(Permissions.LIBRARY_VIEW)

    if has_pathways_access:
        return redirect(url_for('pathways_bp.pathway_library'))
    elif has_lucky_draw_access:
        return redirect(url_for('lucky_draw_bp.lucky_draw'))
    
    return redirect(url_for('agenda_bp.agenda'))


