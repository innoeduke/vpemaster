# vpemaster/pathways_routes.py

from flask import Blueprint, render_template, request, jsonify, session
from datetime import date
from . import db
from .models import Project, Pathway, PathwayProject, LevelRole, Contact
from .auth.utils import login_required, is_authorized
from .auth.permissions import Permissions
from flask_login import current_user


pathways_bp = Blueprint('pathways_bp', __name__)


def get_pathway_library_data():
    pathways = Pathway.query.filter_by(status='active').order_by(Pathway.name).all()
    
    # pre-fetch all pathway projects to create a lookup
    all_pp = db.session.query(PathwayProject, Pathway.abbr).join(Pathway).all()
    project_codes_lookup = {} # {project_id: {path_abbr: code, ...}}
    for pp, path_abbr in all_pp:
        if pp.project_id not in project_codes_lookup:
            project_codes_lookup[pp.project_id] = {}
        project_codes_lookup[pp.project_id][path_abbr] = pp.code

    # Group pathways by type
    grouped_pathways = {}
    pathways_data = []

    # Fetch all project associations for ALL pathways in one go
    # Join Project to get details
    all_pathway_projects = db.session.query(PathwayProject, Project)\
        .join(Project, PathwayProject.project_id == Project.id)\
        .all()

    # Group by path_id in memory
    pp_by_path = {}
    for pp, proj in all_pathway_projects:
        if pp.path_id not in pp_by_path:
            pp_by_path[pp.path_id] = []
        pp_by_path[pp.path_id].append((pp, proj))

    for pathway in pathways:
        pathway_dict = {
            'id': pathway.id,
            'name': pathway.name,
            'abbr': pathway.abbr,
            'type': pathway.type,
            'projects': []
        }
        
        projs = pp_by_path.get(pathway.id, [])
        # Optional: Sort by level for better display
        projs.sort(key=lambda x: (x[0].level if x[0].level else 99, x[0].code))

        for pathway_project, project in projs:
            project_dict = {
                "id": project.id,
                "Project_Name": project.Project_Name,
                "code": pathway_project.code,
                "type": pathway_project.type,
                "Introduction": project.Introduction or '',
                "Overview": project.Overview or '',
                "Purpose": project.Purpose or '',
                "Requirements": project.Requirements or '',
                "Resources": project.Resources or '',
                "path_codes": project_codes_lookup.get(project.id, {}),
                "level": pathway_project.level
            }
            pathway_dict['projects'].append(project_dict)
            
        ptype = pathway.type
        if ptype and ptype.lower() != 'others':
            label = ptype.upper()
            if label not in grouped_pathways:
                grouped_pathways[label] = []
            grouped_pathways[label].append(pathway_dict)
            pathways_data.append(pathway_dict)

    # Sort grouped_pathways by keys (labels) ascending
    grouped_pathways = dict(sorted(grouped_pathways.items()))
    
    return {
        'grouped_pathways': grouped_pathways,
        'pathways': pathways_data
    }

@pathways_bp.route('/pathway_library')
def pathway_library():
    if not is_authorized(Permissions.PATHWAY_LIB_VIEW):
        return redirect(url_for('agenda_bp.agenda'))

    has_lucky_draw_access = is_authorized(Permissions.LUCKY_DRAW_VIEW)
    has_pathways_access = is_authorized(Permissions.PATHWAY_LIB_VIEW)
    
    data = get_pathway_library_data()
    return render_template(
        'pathway_library.html', 
        **data,
        active_tab='pathway_library',
        has_lucky_draw_access=has_lucky_draw_access,
        has_pathways_access=has_pathways_access,
        Permissions=Permissions
    )


@pathways_bp.route('/pathway_library/update_project/<int:project_id>', methods=['POST'])
@login_required
def update_project(project_id):
    if not is_authorized(Permissions.PATHWAY_LIB_EDIT):
        return jsonify(success=False, message="Permission denied"), 403

    project = Project.query.get_or_404(project_id)
    data = request.get_json()

    # Get and save raw text from the client
    project.Introduction = data.get('Introduction')
    project.Overview = data.get('Overview')
    project.Purpose = data.get('Purpose')
    project.Requirements = data.get('Requirements')
    project.Resources = data.get('Resources')

    db.session.commit()

    # Return raw text for display and re-editing
    return jsonify(
        success=True,
        Introduction=project.Introduction,
        Overview=project.Overview,
        Purpose=project.Purpose,
        Requirements=project.Requirements,
        Resources=project.Resources
    )


@pathways_bp.route('/api/contacts/<int:contact_id>/pathways', methods=['GET'])
@login_required
def get_contact_pathways(contact_id):
    if not (is_authorized(Permissions.CONTACT_BOOK_EDIT) or is_authorized(Permissions.ACHIEVEMENTS_VIEW)):
        return jsonify(success=False, message="Permission denied"), 403

    contact = db.session.get(Contact, contact_id)
    if not contact:
        return jsonify(success=False, message="Contact not found"), 404

    from .models.contact_path import ContactPath
    registered = [cp.to_dict() for cp in contact.registered_paths]
    registered_ids = {cp.path_id for cp in contact.registered_paths}

    available_pathways = Pathway.query.filter_by(status='active').order_by(Pathway.name).all()
    available = [
        {'id': p.id, 'name': p.name, 'abbr': p.abbr}
        for p in available_pathways if p.id not in registered_ids
    ]

    return jsonify(success=True, registered=registered, available=available)


@pathways_bp.route('/api/contacts/<int:contact_id>/pathways/register', methods=['POST'])
@login_required
def register_contact_pathway(contact_id):
    if not is_authorized(Permissions.ACHIEVEMENTS_EDIT):
        return jsonify(success=False, message="Permission denied"), 403

    contact = db.session.get(Contact, contact_id)
    if not contact:
        return jsonify(success=False, message="Contact not found"), 404

    data = request.get_json() or {}
    pathway_id = data.get('pathway_id')
    if not pathway_id:
        return jsonify(success=False, message="Pathway ID is required"), 400

    pathway = db.session.get(Pathway, pathway_id)
    if not pathway:
        return jsonify(success=False, message="Pathway not found"), 404

    from .models.contact_path import ContactPath
    # Check if already registered
    existing = ContactPath.query.filter_by(contact_id=contact_id, path_id=pathway_id).first()
    if existing:
        return jsonify(success=False, message="Pathway is already registered for this contact"), 400

    # If first registered path, set as default
    is_first = len(contact.registered_paths) == 0
    new_cp = ContactPath(
        contact_id=contact.id,
        path_id=pathway.id,
        status='working',
        is_default=is_first,
        registered_date=date.today()
    )
    db.session.add(new_cp)
    
    # Sync legacy _Current_Path if this is default
    if is_first:
        contact._Current_Path = pathway.name

    db.session.commit()
    
    from .utils import sync_contact_metadata
    sync_contact_metadata(contact.id)

    return jsonify(success=True, message=f"Successfully registered pathway: {pathway.name}")


@pathways_bp.route('/api/contacts/<int:contact_id>/pathways/<int:pathway_id>/complete', methods=['POST'])
@login_required
def complete_contact_pathway(contact_id, pathway_id):
    if not is_authorized(Permissions.ACHIEVEMENTS_EDIT):
        return jsonify(success=False, message="Permission denied"), 403

    contact = db.session.get(Contact, contact_id)
    if not contact:
        return jsonify(success=False, message="Contact not found"), 404

    from .models.contact_path import ContactPath
    cp = ContactPath.query.filter_by(contact_id=contact_id, path_id=pathway_id).first()
    if not cp:
        return jsonify(success=False, message="Registered pathway not found"), 404

    from datetime import date
    cp.status = 'completed'
    cp.completed_date = date.today()

    # Automatically record achievement if user is linked
    user_id = contact.user_id
    if user_id:
        from .models.achievement import Achievement
        # Check if they already have this path completion recorded to avoid duplicates
        existing_ach = Achievement.query.filter_by(
            user_id=user_id,
            achievement_type='path-completion',
            path_name=cp.pathway.name
        ).first()
        if not existing_ach:
            from .services.achievement_service import AchievementService
            AchievementService.record_achievement(
                user_id=user_id,
                requestor_id=current_user.id,
                achievement_type='path-completion',
                issue_date=date.today(),
                path_name=cp.pathway.name
            )

    db.session.commit()
    
    from .utils import sync_contact_metadata
    sync_contact_metadata(contact.id)

    return jsonify(success=True, message=f"Successfully completed pathway: {cp.pathway.name}")


@pathways_bp.route('/api/contacts/<int:contact_id>/pathways/<int:pathway_id>/set_default', methods=['POST'])
@login_required
def set_default_contact_pathway(contact_id, pathway_id):
    if not is_authorized(Permissions.CONTACT_BOOK_EDIT):
        return jsonify(success=False, message="Permission denied"), 403

    contact = db.session.get(Contact, contact_id)
    if not contact:
        return jsonify(success=False, message="Contact not found"), 404

    from .models.contact_path import ContactPath
    target_cp = ContactPath.query.filter_by(contact_id=contact_id, path_id=pathway_id).first()
    if not target_cp:
        return jsonify(success=False, message="Registered pathway not found"), 404

    for cp in contact.registered_paths:
        cp.is_default = (cp.id == target_cp.id)

    # Sync legacy _Current_Path
    contact._Current_Path = target_cp.pathway.name

    db.session.commit()
    
    from .utils import sync_contact_metadata
    sync_contact_metadata(contact.id)

    return jsonify(success=True, message=f"Successfully set {target_cp.pathway.name} as default")


@pathways_bp.route('/api/contacts/<int:contact_id>/pathways/<int:pathway_id>/deregister', methods=['POST'])
@login_required
def deregister_contact_pathway(contact_id, pathway_id):
    if not is_authorized(Permissions.ACHIEVEMENTS_EDIT):
        return jsonify(success=False, message="Permission denied"), 403

    contact = db.session.get(Contact, contact_id)
    if not contact:
        return jsonify(success=False, message="Contact not found"), 404

    from .models.contact_path import ContactPath
    cp = ContactPath.query.filter_by(contact_id=contact_id, path_id=pathway_id).first()
    if not cp:
        return jsonify(success=False, message="Registered pathway not found"), 404

    # If it was default, try to find another one to make default
    was_default = cp.is_default
    pathway_name = cp.pathway.name
    
    # Also remove associated path-completion achievement to prevent
    # sync_contact_metadata from re-creating this ContactPath from achievements
    if cp.status == 'completed':
        user_id = contact.user_id
        if user_id:
            from .models.achievement import Achievement
            Achievement.query.filter_by(
                user_id=user_id,
                achievement_type='path-completion',
                path_name=pathway_name
            ).delete()
    
    db.session.delete(cp)
    
    # Trigger loading/re-evaluating registered paths
    db.session.flush()

    if was_default:
        # Try to find another working path
        next_default = next((x for x in contact.registered_paths if x.status == 'working'), None)
        if not next_default:
            next_default = next((x for x in contact.registered_paths if x.status == 'completed'), None)
        
        if next_default:
            next_default.is_default = True
            contact._Current_Path = next_default.pathway.name
        else:
            contact._Current_Path = None

    db.session.commit()
    
    # Expire the contact to force registered_paths reload from DB
    db.session.expire(contact)
    
    from .utils import sync_contact_metadata
    sync_contact_metadata(contact.id)

    return jsonify(success=True, message=f"Successfully deregistered pathway: {pathway_name}")


