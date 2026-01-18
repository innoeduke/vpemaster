"""populate_user_clubs_from_contacts

Revision ID: b2ec9631b851
Revises: 2517a8b1c7fa
Create Date: 2026-01-17 01:27:31.571116

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2ec9631b851'
down_revision = '2517a8b1c7fa'
branch_labels = None
depends_on = None


def upgrade():
    """Populate user_clubs table from Contacts table data."""
    from datetime import datetime, timezone
    
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = [c['name'] for c in inspector.get_columns('Users')]
    
    # Check if Contact_ID exists (case-insensitive)
    has_contact_id = any(c.lower() == 'contact_id' for c in columns)

    users_with_contacts = []
    if has_contact_id:
        # Get all users with Contact_ID
        users_with_contacts = connection.execute(sa.text("""
            SELECT u.id as user_id, c.id as contact_id, c.Mentor_ID, c.Current_Path, c.Next_Project
            FROM Users u
            INNER JOIN Contacts c ON u.Contact_ID = c.id
            WHERE u.Contact_ID IS NOT NULL
        """)).fetchall()
    
    for user_row in users_with_contacts:
        user_id, contact_id, mentor_id, current_path, next_project = user_row
        
        # Lookup current_path_id from pathways table
        current_path_id = None
        if current_path:
            path_result = connection.execute(sa.text("""
                SELECT id FROM pathways WHERE name = :path_name
            """), {'path_name': current_path}).fetchone()
            if path_result:
                current_path_id = path_result[0]
        
        # Lookup next_project_id from Projects table
        next_project_id = None
        if next_project:
            project_result = connection.execute(sa.text("""
                SELECT id FROM Projects WHERE Project_Name = :project_name
            """), {'project_name': next_project}).fetchone()
            if project_result:
                next_project_id = project_result[0]
        
        # Check if user_club already exists
        existing_uc = connection.execute(sa.text("""
            SELECT 1 FROM user_clubs 
            WHERE user_id = :user_id AND club_id = :club_id
        """), {'user_id': user_id, 'club_id': 1}).fetchone()

        if not existing_uc:
            # Insert into user_clubs
            connection.execute(sa.text("""
                INSERT INTO user_clubs 
                (user_id, club_id, club_role_id, current_path_id, is_home, mentor_id, next_project_id, created_at, updated_at)
                VALUES 
                (:user_id, :club_id, :club_role_id, :current_path_id, :is_home, :mentor_id, :next_project_id, :created_at, :updated_at)
            """), {
                'user_id': user_id,
                'club_id': 1,
                'club_role_id': 4,
                'current_path_id': current_path_id,
                'is_home': True,
                'mentor_id': mentor_id,
                'next_project_id': next_project_id,
                'created_at': datetime.now(timezone.utc),
                'updated_at': datetime.now(timezone.utc)
            })


def downgrade():
    """Remove user_clubs records created by this migration."""
    # We don't reverse this migration as we can't reliably identify
    # which records were created by this migration vs. manually added
    pass
