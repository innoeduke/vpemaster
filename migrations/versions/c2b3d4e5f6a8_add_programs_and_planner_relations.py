"""add programs and planner relations

Revision ID: c2b3d4e5f6a8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-22 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c2b3d4e5f6a8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    # Create programs table if it doesn't exist
    if 'programs' not in existing_tables:
        op.create_table(
            'programs',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('club_id', sa.Integer(), nullable=True),
            sa.Column('name', sa.String(length=120), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
            sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_by_id', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['club_id'], ['clubs.id'], name=op.f('fk_programs_club_id_clubs'), ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], name=op.f('fk_programs_created_by_id_users'), ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id', name=op.f('pk_programs'))
        )
        with op.batch_alter_table('programs', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_programs_club_id'), ['club_id'], unique=False)

    # Create program_tasks table if it doesn't exist
    if 'program_tasks' not in existing_tables:
        op.create_table(
            'program_tasks',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('program_id', sa.Integer(), nullable=False),
            sa.Column('title', sa.String(length=200), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('phase_label', sa.String(length=60), nullable=True),
            sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('completion_type', sa.String(length=30), nullable=False),
            sa.Column('completion_config', sa.JSON(), nullable=True),
            sa.Column('is_required', sa.Boolean(), nullable=False, server_default='1'),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['program_id'], ['programs.id'], name=op.f('fk_program_tasks_program_id_programs'), ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id', name=op.f('pk_program_tasks'))
        )
        with op.batch_alter_table('program_tasks', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_program_tasks_program_id'), ['program_id'], unique=False)

    # Create program_enrollments table if it doesn't exist
    if 'program_enrollments' not in existing_tables:
        op.create_table(
            'program_enrollments',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('program_id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('mentor_user_id', sa.Integer(), nullable=True),
            sa.Column('mentor_contact_id', sa.Integer(), nullable=True),
            sa.Column('club_id', sa.Integer(), nullable=False),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='active'),
            sa.Column('started_at', sa.DateTime(), nullable=False),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('created_by_id', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['club_id'], ['clubs.id'], name=op.f('fk_program_enrollments_club_id_clubs'), ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], name=op.f('fk_program_enrollments_created_by_id_users'), ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['mentor_contact_id'], ['Contacts.id'], name=op.f('fk_program_enrollments_mentor_contact_id_Contacts'), ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['mentor_user_id'], ['users.id'], name=op.f('fk_program_enrollments_mentor_user_id_users'), ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['program_id'], ['programs.id'], name=op.f('fk_program_enrollments_program_id_programs'), ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_program_enrollments_user_id_users'), ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id', name=op.f('pk_program_enrollments')),
            sa.UniqueConstraint('program_id', 'user_id', 'club_id', name='uq_program_enrollment_user_club')
        )
        with op.batch_alter_table('program_enrollments', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_program_enrollments_club_id'), ['club_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_program_enrollments_program_id'), ['program_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_program_enrollments_user_id'), ['user_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_program_enrollments_mentor_user_id'), ['mentor_user_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_program_enrollments_mentor_contact_id'), ['mentor_contact_id'], unique=False)

    # Alter planner table
    if 'planner' in existing_tables:
        planner_fks = {fk['name'] for fk in inspector.get_foreign_keys('planner')}
        planner_indexes = {idx['name'] for idx in inspector.get_indexes('planner')}
        planner_cols = {col['name'] for col in inspector.get_columns('planner')}

        with op.batch_alter_table('planner', schema=None) as batch_op:
            if 'enrollment_id' not in planner_cols:
                batch_op.add_column(sa.Column('enrollment_id', sa.Integer(), nullable=True))
            if 'program_task_id' not in planner_cols:
                batch_op.add_column(sa.Column('program_task_id', sa.Integer(), nullable=True))
            if 'auto_completed' not in planner_cols:
                batch_op.add_column(sa.Column('auto_completed', sa.Boolean(), nullable=False, server_default='0'))
            if 'completed_at' not in planner_cols:
                batch_op.add_column(sa.Column('completed_at', sa.DateTime(), nullable=True))
            if 'completed_by_id' not in planner_cols:
                batch_op.add_column(sa.Column('completed_by_id', sa.Integer(), nullable=True))
            
            idx_name = 'ix_planner_enrollment_id'
            if idx_name not in planner_indexes:
                batch_op.create_index(batch_op.f(idx_name), ['enrollment_id'], unique=False)
            
            idx_name = 'ix_planner_program_task_id'
            if idx_name not in planner_indexes:
                batch_op.create_index(batch_op.f(idx_name), ['program_task_id'], unique=False)
            
            fk_name = 'fk_planner_enrollment_id_program_enrollments'
            if fk_name not in planner_fks:
                batch_op.create_foreign_key(batch_op.f(fk_name), 'program_enrollments', ['enrollment_id'], ['id'], ondelete='CASCADE')
                
            fk_name = 'fk_planner_program_task_id_program_tasks'
            if fk_name not in planner_fks:
                batch_op.create_foreign_key(batch_op.f(fk_name), 'program_tasks', ['program_task_id'], ['id'], ondelete='SET NULL')
                
            fk_name = 'fk_planner_completed_by_id_users'
            if fk_name not in planner_fks:
                batch_op.create_foreign_key(batch_op.f(fk_name), 'users', ['completed_by_id'], ['id'], ondelete='SET NULL')

    # Seed permissions and associate them with roles
    from datetime import datetime, timezone
    conn = op.get_bind()

    # 1. Seed permissions in database
    for perm_name, perm_desc, perm_cat, perm_res, perm_act in [
        ('PROGRAMS_SELF', 'Manage own program enrollments and view plans', 'planner', 'programs', 'view_own'),
        ('PROGRAMS_MANAGE', 'CRUD program templates and manage all enrollments', 'planner', 'programs', 'manage')
    ]:
        existing = conn.execute(
            sa.text("SELECT id FROM permissions WHERE name = :name"),
            {'name': perm_name}
        ).fetchone()
        
        if not existing:
            conn.execute(
                sa.text("""
                    INSERT INTO permissions (name, description, category, resource, action, created_at)
                    VALUES (:name, :desc, :cat, :res, :act, :created_at)
                """),
                {
                    'name': perm_name,
                    'desc': perm_desc,
                    'cat': perm_cat,
                    'res': perm_res,
                    'act': perm_act,
                    'created_at': datetime.now(timezone.utc)
                }
            )

    # 2. Grant permissions to roles
    inspector = sa.inspect(conn)
    rp_cols = {c['name'] for c in inspector.get_columns('role_permissions')}
    has_club_id = 'club_id' in rp_cols

    if has_club_id:
        club_rows = conn.execute(sa.text("SELECT id FROM clubs")).fetchall()
        club_ids = [row[0] for row in club_rows]
    else:
        club_ids = [None]

    for perm_name, target_roles in [
        ('PROGRAMS_SELF', ('Member', 'Staff', 'Operator', 'ClubAdmin')),
        ('PROGRAMS_MANAGE', ('Operator', 'ClubAdmin'))
    ]:
        perm_row = conn.execute(
            sa.text("SELECT id FROM permissions WHERE name = :name"),
            {'name': perm_name}
        ).fetchone()
        if not perm_row:
            continue
        pid = perm_row[0]

        for role_name in target_roles:
            role_row = conn.execute(
                sa.text("SELECT id FROM auth_roles WHERE name = :name"),
                {'name': role_name}
            ).fetchone()

            if role_row:
                rid = role_row[0]
                for cid in club_ids:
                    if has_club_id:
                        exists = conn.execute(
                            sa.text("SELECT 1 FROM role_permissions WHERE role_id = :rid AND permission_id = :pid AND club_id = :cid"),
                            {'rid': rid, 'pid': pid, 'cid': cid}
                        ).fetchone()
                        if not exists:
                            conn.execute(
                                sa.text("INSERT INTO role_permissions (role_id, permission_id, club_id) VALUES (:rid, :pid, :cid)"),
                                {'rid': rid, 'pid': pid, 'cid': cid}
                            )
                    else:
                        exists = conn.execute(
                            sa.text("SELECT 1 FROM role_permissions WHERE role_id = :rid AND permission_id = :pid"),
                            {'rid': rid, 'pid': pid}
                        ).fetchone()
                        if not exists:
                            conn.execute(
                                sa.text("INSERT INTO role_permissions (role_id, permission_id) VALUES (:rid, :pid)"),
                                {'rid': rid, 'pid': pid}
                            )


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Clean up role permissions
    for perm_name in ('PROGRAMS_SELF', 'PROGRAMS_MANAGE'):
        perm_row = conn.execute(
            sa.text("SELECT id FROM permissions WHERE name = :name"),
            {'name': perm_name}
        ).fetchone()
        if perm_row:
            pid = perm_row[0]
            conn.execute(
                sa.text("DELETE FROM role_permissions WHERE permission_id = :pid"),
                {'pid': pid}
            )
        conn.execute(
            sa.text("DELETE FROM permissions WHERE name = :name"),
            {'name': perm_name}
        )

    # Get tables in DB to see what exists
    existing_tables = inspector.get_table_names()

    # Drop columns and foreign keys from planner table if they exist
    if 'planner' in existing_tables:
        planner_fks = {fk['name'] for fk in inspector.get_foreign_keys('planner')}
        planner_indexes = {idx['name'] for idx in inspector.get_indexes('planner')}
        planner_cols = {col['name'] for col in inspector.get_columns('planner')}

        with op.batch_alter_table('planner', schema=None) as batch_op:
            # Check and drop foreign keys
            fk_name = 'fk_planner_completed_by_id_users'
            if fk_name in planner_fks:
                batch_op.drop_constraint(fk_name, type_='foreignkey')
            
            fk_name = 'fk_planner_program_task_id_program_tasks'
            if fk_name in planner_fks:
                batch_op.drop_constraint(fk_name, type_='foreignkey')
            
            fk_name = 'fk_planner_enrollment_id_program_enrollments'
            if fk_name in planner_fks:
                batch_op.drop_constraint(fk_name, type_='foreignkey')

            # Check and drop indexes
            idx_name = 'ix_planner_program_task_id'
            if idx_name in planner_indexes:
                batch_op.drop_index(idx_name)
            
            idx_name = 'ix_planner_enrollment_id'
            if idx_name in planner_indexes:
                batch_op.drop_index(idx_name)

            # Check and drop columns
            for col_name in ('completed_by_id', 'completed_at', 'auto_completed', 'program_task_id', 'enrollment_id'):
                if col_name in planner_cols:
                    batch_op.drop_column(col_name)

    # Drop program tables if they exist
    if 'program_enrollments' in existing_tables:
        op.drop_table('program_enrollments')

    if 'program_tasks' in existing_tables:
        op.drop_table('program_tasks')

    if 'programs' in existing_tables:
        op.drop_table('programs')
