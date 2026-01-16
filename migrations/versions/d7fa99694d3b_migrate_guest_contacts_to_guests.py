"""migrate_guest_contacts_to_guests

Revision ID: d7fa99694d3b
Revises: 08e99002e832
Create Date: 2026-01-17 01:12:28.036393

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd7fa99694d3b'
down_revision = '08e99002e832'
branch_labels = None
depends_on = None


def upgrade():
    """Migrate all Guest-type contacts to the guests table."""
    from datetime import datetime, timezone
    
    # Get database connection
    connection = op.get_bind()
    
    # Query all contacts where Type = 'Guest'
    result = connection.execute(sa.text("""
        SELECT id, Name, Phone_Number, Email, Date_Created, Bio
        FROM Contacts
        WHERE Type = 'Guest'
    """))
    
    guest_contacts = result.fetchall()
    
    # Insert each guest contact into the guests table
    for contact in guest_contacts:
        contact_id, name, phone, email, date_created, bio = contact
        
        # Convert Date_Created to datetime if it exists
        created_date = datetime.now(timezone.utc)
        if date_created:
            # If date_created is a date object, convert to datetime
            if hasattr(date_created, 'year'):
                created_date = datetime.combine(date_created, datetime.min.time()).replace(tzinfo=timezone.utc)
        
        # Insert into guests table
        connection.execute(sa.text("""
            INSERT INTO guests (club_id, name, phone, email, status, type, created_date, notes)
            VALUES (:club_id, :name, :phone, :email, :status, :type, :created_date, :notes)
        """), {
            'club_id': 1,
            'name': name,
            'phone': phone,
            'email': email,
            'status': None,
            'type': 'standard',
            'created_date': created_date,
            'notes': bio
        })


def downgrade():
    """Remove migrated guest records from guests table."""
    # This downgrade removes all guests with type='standard' and club_id=1
    # that were created by this migration. Since we can't reliably identify
    # which specific records were created by this migration vs. manually added,
    # we'll leave the downgrade empty to prevent accidental data loss.
    pass
