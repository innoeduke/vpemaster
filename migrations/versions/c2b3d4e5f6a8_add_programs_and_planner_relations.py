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
    # Create programs table
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

    # Create program_tasks table
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

    # Create program_enrollments table
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
    with op.batch_alter_table('planner', schema=None) as batch_op:
        batch_op.add_column(sa.Column('enrollment_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('program_task_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('auto_completed', sa.Boolean(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('completed_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('completed_by_id', sa.Integer(), nullable=True))
        
        batch_op.create_index(batch_op.f('ix_planner_enrollment_id'), ['enrollment_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_planner_program_task_id'), ['program_task_id'], unique=False)
        
        batch_op.create_foreign_key(batch_op.f('fk_planner_enrollment_id_program_enrollments'), 'program_enrollments', ['enrollment_id'], ['id'], ondelete='CASCADE')
        batch_op.create_foreign_key(batch_op.f('fk_planner_program_task_id_program_tasks'), 'program_tasks', ['program_task_id'], ['id'], ondelete='SET NULL')
        batch_op.create_foreign_key(batch_op.f('fk_planner_completed_by_id_users'), 'users', ['completed_by_id'], ['id'], ondelete='SET NULL')

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

    # Drop columns and foreign keys from planner table
    with op.batch_alter_table('planner', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_planner_completed_by_id_users'), type_='foreignkey')
        batch_op.drop_constraint(batch_op.f('fk_planner_program_task_id_program_tasks'), type_='foreignkey')
        batch_op.drop_constraint(batch_op.f('fk_planner_enrollment_id_program_enrollments'), type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_planner_program_task_id'))
        batch_op.drop_index(batch_op.f('ix_planner_enrollment_id'))
        batch_op.drop_column('completed_by_id')
        batch_op.drop_column('completed_at')
        batch_op.drop_column('auto_completed')
        batch_op.drop_column('program_task_id')
        batch_op.drop_column('enrollment_id')

    # Drop program tables
    with op.batch_alter_table('program_enrollments', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_program_enrollments_mentor_contact_id'))
        batch_op.drop_index(batch_op.f('ix_program_enrollments_mentor_user_id'))
        batch_op.drop_index(batch_op.f('ix_program_enrollments_user_id'))
        batch_op.drop_index(batch_op.f('ix_program_enrollments_program_id'))
        batch_op.drop_index(batch_op.f('ix_program_enrollments_club_id'))
    op.drop_table('program_enrollments')

    with op.batch_alter_table('program_tasks', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_program_tasks_program_id'))
    op.drop_table('program_tasks')

    with op.batch_alter_table('programs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_programs_club_id'))
    op.drop_table('programs')
