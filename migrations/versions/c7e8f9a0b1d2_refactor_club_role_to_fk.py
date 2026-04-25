"""refactor club_role_level bitmask to auth_role_id FK

Revision ID: c7e8f9a0b1d2
Revises: b4f7a2c1d839
Create Date: 2026-04-07 16:18:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision = 'c7e8f9a0b1d2'
down_revision = 'b4f7a2c1d839'
branch_labels = None
depends_on = None


def get_column_names(conn, table_name):
    inspector = Inspector.from_engine(conn)
    return [c['name'] for c in inspector.get_columns(table_name)]


def upgrade():
    conn = op.get_bind()
    
    # 1. Add new auth_role_id column (nullable initially)
    with op.batch_alter_table('user_clubs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('auth_role_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_user_clubs_auth_role', 'auth_roles', ['auth_role_id'], ['id'])
        batch_op.create_index('ix_user_clubs_auth_role', ['auth_role_id'])
    
    # 2. Fetch all auth_roles ordered by level DESC so we can find highest match
    roles = conn.execute(sa.text(
        "SELECT id, name, level FROM auth_roles ORDER BY level DESC"
    )).fetchall()
    
    # Build a role lookup: {level: id}
    role_by_level = {r[2]: r[0] for r in roles}  # level -> id
    user_role_id = next((r[0] for r in roles if r[1] == 'User'), None)
    
    # 3. Migrate existing bitmask data to the highest matching role
    user_clubs = conn.execute(sa.text(
        "SELECT id, club_role_level FROM user_clubs"
    )).fetchall()
    
    for uc_id, bitmask in user_clubs:
        if not bitmask or bitmask == 0:
            # No role assigned, default to User
            best_role_id = user_role_id
        else:
            # Find the highest role whose level matches the bitmask
            best_role_id = user_role_id  # fallback
            for level, role_id in sorted(role_by_level.items(), reverse=True):
                if level and level > 0 and (bitmask & level) == level:
                    best_role_id = role_id
                    break
        
        if best_role_id:
            conn.execute(
                sa.text("UPDATE user_clubs SET auth_role_id = :rid WHERE id = :ucid"),
                {'rid': best_role_id, 'ucid': uc_id}
            )
    
    # 4. Drop the old club_role_level column
    with op.batch_alter_table('user_clubs', schema=None) as batch_op:
        batch_op.drop_column('club_role_level')


def downgrade():
    conn = op.get_bind()
    columns = get_column_names(conn, 'user_clubs')
    
    # 1. Re-add club_role_level column
    if 'club_role_level' not in columns:
        with op.batch_alter_table('user_clubs', schema=None) as batch_op:
            batch_op.add_column(sa.Column('club_role_level', sa.Integer(), nullable=False, server_default='0'))
    
    # 2. Migrate auth_role_id back to bitmask level
    if 'auth_role_id' in columns:
        roles = conn.execute(sa.text("SELECT id, level FROM auth_roles")).fetchall()
        role_level_map = {r[0]: r[1] for r in roles}
        
        user_clubs = conn.execute(sa.text(
            "SELECT id, auth_role_id FROM user_clubs"
        )).fetchall()
        
        for uc_id, role_id in user_clubs:
            level = role_level_map.get(role_id, 0) if role_id else 0
            conn.execute(
                sa.text("UPDATE user_clubs SET club_role_level = :level WHERE id = :ucid"),
                {'level': level or 0, 'ucid': uc_id}
            )
    
    # 3. Drop auth_role_id column and related constraints
    if 'auth_role_id' in columns:
        # Drop constraints and indexes with raw SQL to handle potential missing names or platform differences
        try:
            conn.execute(sa.text("ALTER TABLE user_clubs DROP FOREIGN KEY fk_user_clubs_auth_role"))
        except Exception:
            pass
        
        try:
            conn.execute(sa.text("ALTER TABLE user_clubs DROP INDEX ix_user_clubs_auth_role"))
        except Exception:
            pass

        with op.batch_alter_table('user_clubs', schema=None) as batch_op:
            batch_op.drop_column('auth_role_id')
