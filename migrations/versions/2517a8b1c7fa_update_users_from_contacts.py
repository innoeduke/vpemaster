"""update_users_from_contacts

Revision ID: 2517a8b1c7fa
Revises: d7fa99694d3b
Create Date: 2026-01-17 01:19:27.381922

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2517a8b1c7fa'
down_revision = 'd7fa99694d3b'
branch_labels = None
depends_on = None


def upgrade():
    """Update Users table with data from Contacts table."""
    connection = op.get_bind()
    
    # Update Users table with data from Contacts where Contact_ID is not null
    connection.execute(sa.text("""
        UPDATE Users u
        INNER JOIN Contacts c ON u.Contact_ID = c.id
        SET 
            u.member_no = c.Member_ID,
            u.phone = c.Phone_Number,
            u.dtm = c.DTM,
            u.avatar_url = c.Avatar_URL,
            u.bio = c.Bio
        WHERE u.Contact_ID IS NOT NULL
    """))


def downgrade():
    """Clear the updated fields in Users table."""
    # We don't reverse this migration as it would result in data loss
    # The original data in Users table is being overwritten with Contacts data
    pass
