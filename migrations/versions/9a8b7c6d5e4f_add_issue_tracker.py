"""add issue tracker

Revision ID: 9a8b7c6d5e4f
Revises: 8ee6d55c184f
Create Date: 2026-06-08 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9a8b7c6d5e4f'
down_revision = '8ee6d55c184f'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'issues',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('club_id', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('priority', sa.String(length=10), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('submitter_id', sa.Integer(), nullable=False),
        sa.Column('assignee_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['assignee_id'], ['users.id'], name=op.f('fk_issues_assignee_id_users')),
        sa.ForeignKeyConstraint(['club_id'], ['clubs.id'], name=op.f('fk_issues_club_id_clubs'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['submitter_id'], ['users.id'], name=op.f('fk_issues_submitter_id_users')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_issues')),
    )
    with op.batch_alter_table('issues', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_issues_club_id'), ['club_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_issues_submitter_id'), ['submitter_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_issues_assignee_id'), ['assignee_id'], unique=False)
        batch_op.create_index('ix_issues_club_created', ['club_id', 'created_at'], unique=False)

    op.create_table(
        'issue_comments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('issue_id', sa.Integer(), nullable=False),
        sa.Column('author_id', sa.Integer(), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['author_id'], ['users.id'], name=op.f('fk_issue_comments_author_id_users')),
        sa.ForeignKeyConstraint(['issue_id'], ['issues.id'], name=op.f('fk_issue_comments_issue_id_issues'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_issue_comments')),
    )
    with op.batch_alter_table('issue_comments', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_issue_comments_issue_id'), ['issue_id'], unique=False)

    from datetime import datetime, timezone
    conn = op.get_bind()

    existing = conn.execute(
        sa.text("SELECT id FROM permissions WHERE name = 'ISSUE_MANAGE'")
    ).fetchone()
    if not existing:
        conn.execute(
            sa.text("""
                INSERT INTO permissions (name, description, category, resource, action, created_at)
                VALUES ('ISSUE_MANAGE', 'Manage issues (change status, assign, close)', 'tools', 'issue', 'manage', :created_at)
            """),
            {'created_at': datetime.now(timezone.utc)}
        )

    perm_row = conn.execute(
        sa.text("SELECT id FROM permissions WHERE name = 'ISSUE_MANAGE'")
    ).fetchone()
    if perm_row:
        pid = perm_row[0]
        for role_name in ('SysAdmin', 'ClubAdmin'):
            role_row = conn.execute(
                sa.text("SELECT id FROM auth_roles WHERE name = :role_name"),
                {'role_name': role_name},
            ).fetchone()
            if role_row:
                rid = role_row[0]
                exists = conn.execute(
                    sa.text("SELECT 1 FROM role_permissions WHERE role_id = :rid AND permission_id = :pid"),
                    {'rid': rid, 'pid': pid},
                ).fetchone()
                if not exists:
                    conn.execute(
                        sa.text("INSERT INTO role_permissions (role_id, permission_id) VALUES (:rid, :pid)"),
                        {'rid': rid, 'pid': pid},
                    )


def downgrade():
    conn = op.get_bind()
    perm_row = conn.execute(
        sa.text("SELECT id FROM permissions WHERE name = 'ISSUE_MANAGE'")
    ).fetchone()
    if perm_row:
        pid = perm_row[0]
        conn.execute(
            sa.text("DELETE FROM role_permissions WHERE permission_id = :pid"),
            {'pid': pid},
        )
        conn.execute(
            sa.text("DELETE FROM permissions WHERE name = 'ISSUE_MANAGE'"),
        )

    with op.batch_alter_table('issue_comments', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_issue_comments_issue_id'))
    op.drop_table('issue_comments')

    with op.batch_alter_table('issues', schema=None) as batch_op:
        batch_op.drop_index('ix_issues_club_created')
        batch_op.drop_index(batch_op.f('ix_issues_assignee_id'))
        batch_op.drop_index(batch_op.f('ix_issues_submitter_id'))
        batch_op.drop_index(batch_op.f('ix_issues_club_id'))
    op.drop_table('issues')
