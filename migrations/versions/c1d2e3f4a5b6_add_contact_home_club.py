"""add contact home_club column with backfill

Revision ID: c1d2e3f4a5b6
Revises: dba589bd1002
Create Date: 2026-06-05 14:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c1d2e3f4a5b6'
down_revision = 'dba589bd1002'
branch_labels = None
depends_on = None


def upgrade():
    # Add the home_club column to Contacts. Plain text by design — supports
    # inactive clubs that don't have a row in our clubs table. See
    # docs/CONTACT_USER_CLUB_MODEL.md rule 6.
    with op.batch_alter_table('Contacts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('home_club', sa.String(length=200), nullable=True))

    # Backfill: for each contact linked to a user that has a home club,
    # copy the home club's name into the new column. Pure-guest contacts
    # (no user) stay NULL — that's the intended empty state. See
    # docs/CONTACT_USER_CLUB_MODEL.md open question 4.
    conn = op.get_bind()
    conn.execute(sa.text("""
        UPDATE Contacts c
        JOIN user_clubs uc ON uc.contact_id = c.id AND uc.is_home = TRUE
        JOIN clubs cl ON cl.id = uc.club_id
        SET c.home_club = cl.club_name
    """))


def downgrade():
    with op.batch_alter_table('Contacts', schema=None) as batch_op:
        batch_op.drop_column('home_club')
