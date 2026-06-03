"""consolidate permissions

Revision ID: 2f830fef3c3a
Revises: b4a20082afb8
Create Date: 2026-06-04 01:27:13.862466

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2f830fef3c3a'
down_revision = 'b4a20082afb8'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    
    # 1. New permissions to add
    new_perms_data = [
        # (name, description, category, resource, action)
        ('SETTINGS_VIEW', 'View system settings, ticket types, and roles', 'settings', 'settings', 'view'),
        ('SETTINGS_EDIT', 'Configure club settings, ticket prices, customize roles, manage other clubs, and reset user passwords', 'settings', 'settings', 'edit'),
        ('MEDIA_MANAGE', 'Upload or view external speech/meeting video URLs, and manage meeting files', 'settings', 'media', 'manage'),
        
        ('MEETING_VIEW_PUBLISHED', 'View published agendas, general meeting details, and role assignments', 'meeting', 'meeting', 'view_published'),
        ('MEETING_VIEW_ALL', 'View all meetings (including draft/unpublished meetings)', 'meeting', 'meeting', 'view_all'),
        ('MEETING_CREATE', 'Create new meetings or cancel/delete meetings', 'meeting', 'meeting', 'create'),
        ('MEETING_MANAGE', 'Edit meeting structures, and assign, remove, or approve meeting role bookings for other users', 'meeting', 'meeting', 'manage'),
        ('BOOKING_OWN', 'Book or cancel own meeting roles, and view own speech/project log history', 'meeting', 'booking', 'own'),
        ('VOTING_VIEW_RESULTS', 'View final voting results/winners', 'meeting', 'voting', 'view_results'),
        ('VOTING_TRACK_PROGRESS', 'Track live meeting voting progress in real-time', 'meeting', 'voting', 'track_progress'),
        
        ('SPEECH_LOGS_MANAGE', 'Manage speech logs/records for all members, including paths, projects, and achievements', 'speech_logs', 'speech_logs', 'manage'),
        
        ('ROSTER_VIEW', 'View club member list (roster), guest books, and officer directory', 'roster', 'roster', 'view'),
        ('ROSTER_EDIT', 'Edit club roster (member profiles), add/edit contacts and guest records, and update club officer / Excomm teams', 'roster', 'roster', 'edit'),
        
        ('LIBRARY_VIEW', 'View Pathways curriculum (levels, paths, projects), achievements, and club history', 'tools', 'library', 'view'),
        ('LUCKY_DRAW_EDIT', 'Configure, edit, and run lucky draws', 'tools', 'lucky_draw', 'edit'),
        
        ('CHAT_COMMANDS', 'Run chat terminal commands', 'chat', 'chat', 'commands'),
        ('CHAT_AI', 'Talk to AI Assistant using LLM', 'chat', 'chat', 'ai'),
    ]
    
    from datetime import datetime, timezone
    # Insert new permissions
    created_at = datetime.now(timezone.utc)
    for name, desc, cat, res, act in new_perms_data:
        # Check if already exists
        exists = conn.execute(sa.text("SELECT id FROM permissions WHERE name = :name"), {"name": name}).fetchone()
        if not exists:
            conn.execute(
                sa.text("INSERT INTO permissions (name, description, category, resource, action, created_at) "
                        "VALUES (:name, :desc, :cat, :res, :act, :created_at)"),
                {"name": name, "desc": desc, "cat": cat, "res": res, "act": act, "created_at": created_at}
            )
            
    # Get all new permissions mapping: name -> id
    new_perms_map = {}
    rows = conn.execute(sa.text("SELECT id, name FROM permissions")).fetchall()
    for row in rows:
        new_perms_map[row[1]] = row[0]
        
    # Mapping definition
    mapping = {
        'SETTINGS_VIEW': ['SETTINGS_VIEW_ALL'],
        'SETTINGS_EDIT': ['SETTINGS_EDIT_ALL', 'CLUBS_MANAGE', 'RESET_PASSWORD_CLUB'],
        'MEDIA_MANAGE': ['MEDIA_ACCESS', 'FILE_UPLOAD_MANAGE'],
        'MEETING_VIEW_PUBLISHED': ['AGENDA_VIEW', 'BOOKING_VIEW_ALL'],
        'MEETING_VIEW_ALL': ['AGENDA_VIEW_UNPUBLISHED'],
        'MEETING_CREATE': ['AGENDA_CREATE', 'AGENDA_DELETE'],
        'MEETING_MANAGE': ['AGENDA_EDIT', 'BOOKING_ASSIGN_ALL'],
        'BOOKING_OWN': ['BOOKING_BOOK_OWN', 'SPEECH_LOGS_VIEW_OWN'],
        'VOTING_VIEW_RESULTS': ['VOTING_VIEW_RESULTS'],
        'VOTING_TRACK_PROGRESS': ['VOTING_TRACK_PROGRESS'],
        'SPEECH_LOGS_MANAGE': ['SPEECH_LOGS_VIEW_ALL', 'SPEECH_LOGS_EDIT_ALL', 'PATHWAY_LIB_EDIT', 'ACHIEVEMENTS_EDIT'],
        'ROSTER_VIEW': ['ROSTER_VIEW', 'CONTACT_BOOK_VIEW', 'CONTACTS_MEMBERS_VIEW'],
        'ROSTER_EDIT': ['ROSTER_EDIT', 'CONTACT_BOOK_EDIT', 'CONTACT_ADD_GUEST', 'ABOUT_CLUB_EDIT'],
        'LIBRARY_VIEW': ['PATHWAY_LIB_VIEW', 'ACHIEVEMENTS_VIEW', 'ABOUT_CLUB_VIEW'],
        'LUCKY_DRAW_EDIT': ['LUCKY_DRAW_VIEW', 'LUCKY_DRAW_EDIT'],
        'CHAT_COMMANDS': ['CHAT_COMMANDS'],
        'CHAT_AI': ['CHAT_AI'],
    }
    
    # 2. Migrate existing role-permission assignments
    for new_perm_name, old_perm_names in mapping.items():
        new_perm_id = new_perms_map.get(new_perm_name)
        if not new_perm_id:
            continue
            
        for old_name in old_perm_names:
            # Skip if old_name and new_name are the same
            if old_name == new_perm_name:
                continue
                
            old_perm_row = conn.execute(sa.text("SELECT id FROM permissions WHERE name = :name"), {"name": old_name}).fetchone()
            if not old_perm_row:
                continue
            old_perm_id = old_perm_row[0]
            
            # Find roles with this old permission
            role_ids = [r[0] for r in conn.execute(
                sa.text("SELECT role_id FROM role_permissions WHERE permission_id = :old_id"),
                {"old_id": old_perm_id}
            ).fetchall()]
            
            for role_id in role_ids:
                # Check if the role already has the new permission assigned
                has_new = conn.execute(
                    sa.text("SELECT id FROM role_permissions WHERE role_id = :role_id AND permission_id = :new_id"),
                    {"role_id": role_id, "new_id": new_perm_id}
                ).fetchone()
                
                if not has_new:
                    conn.execute(
                        sa.text("INSERT INTO role_permissions (role_id, permission_id) VALUES (:role_id, :new_id)"),
                        {"role_id": role_id, "new_id": new_perm_id}
                    )
                    
    # 3. Clean up old/redundant permissions
    all_old_names = []
    for old_list in mapping.values():
        all_old_names.extend(old_list)
    all_old_names.extend(['PLANNER_VIEW', 'PLANNER_EDIT', 'PROFILE_VIEW', 'PROFILE_EDIT'])
    
    # Remove from DB if not in new names list
    new_names = set(mapping.keys())
    to_delete = [n for n in all_old_names if n not in new_names]
    
    if to_delete:
        # PostgreSQL/SQLite/MySQL handle IN query values using tuples
        conn.execute(
            sa.text("DELETE FROM permissions WHERE name IN :names"),
            {"names": tuple(to_delete)}
        )


def downgrade():
    conn = op.get_bind()
    
    # 1. Restore old permissions data
    old_perms_data = [
        ('SETTINGS_VIEW_ALL', 'Permission to settings view all', 'settings', 'settings', 'view_all'),
        ('SETTINGS_EDIT_ALL', 'Permission to settings edit all', 'settings', 'settings', 'edit_all'),
        ('CLUBS_MANAGE', 'Manage all clubs features', 'club', 'club', 'manage'),
        ('RESET_PASSWORD_CLUB', 'Permission for RESET_PASSWORD_CLUB', 'club', 'user', 'reset_password'),
        ('MEDIA_ACCESS', 'Access to external media URLs', 'agenda', 'agenda', 'media_access'),
        ('FILE_UPLOAD_MANAGE', 'Manage upload links and retrieve files', 'club', 'file', 'upload_manage'),
        ('AGENDA_VIEW', 'Permission to agenda view', 'agenda', 'agenda', 'view'),
        ('BOOKING_VIEW_ALL', 'Permission to view the booking records of all users', 'booking', 'booking', 'view_all'),
        ('AGENDA_VIEW_UNPUBLISHED', 'View unpublished meetings', 'agenda', 'agenda', 'view_unpublished'),
        ('AGENDA_CREATE', 'Allow creating a new meeting', 'agenda', 'agenda', 'create'),
        ('AGENDA_DELETE', 'Allow deleting a meeting', 'agenda', 'agenda', 'delete'),
        ('AGENDA_EDIT', 'Permission to agenda edit', 'agenda', 'agenda', 'edit'),
        ('BOOKING_ASSIGN_ALL', 'Permission to booking assign all', 'booking', 'booking', 'assign_all'),
        ('BOOKING_BOOK_OWN', 'Permission to booking book own', 'booking', 'booking', 'book_own'),
        ('SPEECH_LOGS_VIEW_OWN', 'Permission to speech logs view own', 'speech_logs', 'speech_logs', 'view_own'),
        ('SPEECH_LOGS_VIEW_ALL', 'Permission to speech logs view all', 'speech_logs', 'speech_logs', 'view_all'),
        ('SPEECH_LOGS_EDIT_ALL', 'Permission to speech logs edit all', 'speech_logs', 'speech_logs', 'edit_all'),
        ('PATHWAY_LIB_EDIT', 'Permission to pathway lib edit', 'pathways', 'pathways', 'edit'),
        ('ACHIEVEMENTS_EDIT', 'Permission to achievements edit', 'achievements', 'achievements', 'edit'),
        ('PATHWAY_LIB_VIEW', 'Permission to pathway lib view', 'pathways', 'pathways', 'view'),
        ('ACHIEVEMENTS_VIEW', 'Permission to achievements view', 'achievements', 'achievements', 'view'),
        ('ABOUT_CLUB_VIEW', 'View club information and executive committee', 'club', 'club', 'view_about'),
        ('ROSTER_VIEW', 'Permission to roster view', 'roster', 'roster', 'view'),
        ('CONTACT_BOOK_VIEW', 'Permission to contact book view', 'contacts', 'contacts', 'view_book'),
        ('CONTACTS_MEMBERS_VIEW', 'View Member Contacts', 'contacts', 'contacts', 'view_members'),
        ('ROSTER_EDIT', 'Edit club roster', 'roster', 'roster', 'edit'),
        ('CONTACT_BOOK_EDIT', 'Permission to contact book edit', 'contacts', 'contacts', 'edit_book'),
        ('CONTACT_ADD_GUEST', 'Add Guest contact from roster', 'contacts', 'contacts', 'add_guest'),
        ('ABOUT_CLUB_EDIT', 'Edit club information and executive committee', 'club', 'club', 'edit_about'),
        ('LUCKY_DRAW_VIEW', 'View lucky draw', 'club', 'lucky_draw', 'view'),
        ('PLANNER_VIEW', 'Allow viewing own planner entries', 'planner', 'planner', 'view'),
        ('PLANNER_EDIT', 'Allow creating/editing own planner entries', 'planner', 'planner', 'edit'),
        ('PROFILE_VIEW', 'View any profile', 'profile', 'profile', 'view'),
        ('PROFILE_EDIT', 'Edit any profile', 'profile', 'profile', 'edit'),
    ]
    
    from datetime import datetime, timezone
    created_at = datetime.now(timezone.utc)
    for name, desc, cat, res, act in old_perms_data:
        exists = conn.execute(sa.text("SELECT id FROM permissions WHERE name = :name"), {"name": name}).fetchone()
        if not exists:
            conn.execute(
                sa.text("INSERT INTO permissions (name, description, category, resource, action, created_at) "
                        "VALUES (:name, :desc, :cat, :res, :act, :created_at)"),
                {"name": name, "desc": desc, "cat": cat, "res": res, "act": act, "created_at": created_at}
            )
            
    # Get all permissions mapping: name -> id
    perms_map = {}
    rows = conn.execute(sa.text("SELECT id, name FROM permissions")).fetchall()
    for row in rows:
        perms_map[row[1]] = row[0]
        
    mapping = {
        'SETTINGS_VIEW': ['SETTINGS_VIEW_ALL'],
        'SETTINGS_EDIT': ['SETTINGS_EDIT_ALL', 'CLUBS_MANAGE', 'RESET_PASSWORD_CLUB'],
        'MEDIA_MANAGE': ['MEDIA_ACCESS', 'FILE_UPLOAD_MANAGE'],
        'MEETING_VIEW_PUBLISHED': ['AGENDA_VIEW', 'BOOKING_VIEW_ALL'],
        'MEETING_VIEW_ALL': ['AGENDA_VIEW_UNPUBLISHED'],
        'MEETING_CREATE': ['AGENDA_CREATE', 'AGENDA_DELETE'],
        'MEETING_MANAGE': ['AGENDA_EDIT', 'BOOKING_ASSIGN_ALL'],
        'BOOKING_OWN': ['BOOKING_BOOK_OWN', 'SPEECH_LOGS_VIEW_OWN'],
        'SPEECH_LOGS_MANAGE': ['SPEECH_LOGS_VIEW_ALL', 'SPEECH_LOGS_EDIT_ALL', 'PATHWAY_LIB_EDIT', 'ACHIEVEMENTS_EDIT'],
        'ROSTER_VIEW': ['ROSTER_VIEW', 'CONTACT_BOOK_VIEW', 'CONTACTS_MEMBERS_VIEW'],
        'ROSTER_EDIT': ['ROSTER_EDIT', 'CONTACT_BOOK_EDIT', 'CONTACT_ADD_GUEST', 'ABOUT_CLUB_EDIT'],
        'LIBRARY_VIEW': ['PATHWAY_LIB_VIEW', 'ACHIEVEMENTS_VIEW', 'ABOUT_CLUB_VIEW'],
        'LUCKY_DRAW_EDIT': ['LUCKY_DRAW_VIEW', 'LUCKY_DRAW_EDIT'],
    }
    
    # 2. Reverse assignment
    for new_perm_name, old_names in mapping.items():
        new_perm_id = perms_map.get(new_perm_name)
        if not new_perm_id:
            continue
            
        role_ids = [r[0] for r in conn.execute(
            sa.text("SELECT role_id FROM role_permissions WHERE permission_id = :new_id"),
            {"new_id": new_perm_id}
        ).fetchall()]
        
        for old_name in old_names:
            old_id = perms_map.get(old_name)
            if not old_id:
                continue
                
            for role_id in role_ids:
                has_old = conn.execute(
                    sa.text("SELECT id FROM role_permissions WHERE role_id = :role_id AND permission_id = :old_id"),
                    {"role_id": role_id, "old_id": old_id}
                ).fetchone()
                
                if not has_old:
                    conn.execute(
                        sa.text("INSERT INTO role_permissions (role_id, permission_id) VALUES (:role_id, :old_id)"),
                        {"role_id": role_id, "old_id": old_id}
                    )
                    
    # 3. Delete new permissions
    to_delete = list(mapping.keys())
    if to_delete:
        conn.execute(
            sa.text("DELETE FROM permissions WHERE name IN :names"),
            {"names": tuple(to_delete)}
        )
