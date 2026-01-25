"""refactor_club_role_id_to_level

Revision ID: c0fd0f865e8a
Revises: a562a4b4de3b
Create Date: 2026-01-20 00:37:07.226026

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'c0fd0f865e8a'
down_revision = 'a562a4b4de3b'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('user_clubs')]

    if 'club_role_level' not in columns:
        with op.batch_alter_table('user_clubs', schema=None) as batch_op:
            # Step 1: Add new column with default 0 to handle existing rows
            batch_op.add_column(sa.Column('club_role_level', sa.Integer(), nullable=False, server_default='0'))

        # Step 2: Migrate Data (MySQL specific update with join)
        if 'club_role_id' in columns:
            op.execute("""
                UPDATE user_clubs 
                JOIN auth_roles ON user_clubs.club_role_id = auth_roles.id 
                SET user_clubs.club_role_level = auth_roles.level
            """)

    if 'club_role_id' in columns:
        with op.batch_alter_table('user_clubs', schema=None) as batch_op:
            # Step 3: Cleanup
            fks = inspector.get_foreign_keys('user_clubs')
            fk_name = next((fk['name'] for fk in fks if 'club_role_id' in fk.get('constrained_columns', [])), None)
            if fk_name:
                batch_op.drop_constraint(fk_name, type_='foreignkey')
            batch_op.drop_column('club_role_id')
            # Optional: Remove the server default now that data is populated
            batch_op.alter_column('club_role_level', server_default=None)

    # with op.batch_alter_table('users', schema=None) as batch_op:
    #     batch_op.drop_index(batch_op.f('Email'))
    #     batch_op.drop_index(batch_op.f('Username'))
    #     batch_op.create_unique_constraint(batch_op.f('uq_users_email'), ['email'])
    #     batch_op.create_unique_constraint(batch_op.f('uq_users_username'), ['username'])

    # ### end Alembic commands ###


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('user_clubs')]
    
    if 'club_role_id' not in columns:
        with op.batch_alter_table('user_clubs', schema=None) as batch_op:
            batch_op.add_column(sa.Column('club_role_id', mysql.INTEGER(), autoincrement=False, nullable=True))
            batch_op.create_foreign_key('fk_user_clubs_club_role_id', 'auth_roles', ['club_role_id'], ['id'], ondelete='SET NULL')
    
    if 'club_role_level' in columns:
        with op.batch_alter_table('user_clubs', schema=None) as batch_op:
            batch_op.drop_column('club_role_level')
