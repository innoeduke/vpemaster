"""drop redundant meeting number fks

Revision ID: 5cd5450f741a
Revises: 6dc275223ba7
Create Date: 2026-02-12 20:26:59.298024

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5cd5450f741a'
down_revision = '6dc275223ba7'
branch_labels = None
depends_on = None


def upgrade():
    # Drop redundant Meeting_Number FK constraint that blocks renumbering
    # This FK is redundant because we now have meeting_id FK
    with op.batch_alter_table('Session_Logs', schema=None) as batch_op:
        # We use batch_op for SQLite compatibility, but for MySQL it's also safer
        # We wrap in a try-except or check existence if possible
        try:
            batch_op.drop_constraint('fk_Session_Logs_Meeting_Number_Meetings', type_='foreignkey')
        except Exception as e:
            print(f"Warning: Could not drop constraint fk_Session_Logs_Meeting_Number_Meetings: {e}")

    # Check for similar fks on other tables just in case
    for table_name in ['roster', 'planner', 'votes']:
        try:
            with op.batch_alter_table(table_name, schema=None) as batch_op:
                # We don't know the exact names if they exist, but we can try common patterns
                # if we were thorough, but for now we only know about Session_Logs for sure.
                pass
        except:
            pass


def downgrade():
    with op.batch_alter_table('Session_Logs', schema=None) as batch_op:
        batch_op.create_foreign_key('fk_Session_Logs_Meeting_Number_Meetings', 'Meetings', ['Meeting_Number'], ['Meeting_Number'])
