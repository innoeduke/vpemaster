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
    from sqlalchemy.engine.reflection import Inspector
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    existing_tables = set(inspector.get_table_names())

    if 'issues' not in existing_tables:
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
    existing_issue_indexes = {i['name'] for i in inspector.get_indexes('issues')} if 'issues' in existing_tables else set()
    with op.batch_alter_table('issues', schema=None) as batch_op:
        if 'ix_issues_club_id' not in existing_issue_indexes:
            batch_op.create_index(batch_op.f('ix_issues_club_id'), ['club_id'], unique=False)
        if 'ix_issues_submitter_id' not in existing_issue_indexes:
            batch_op.create_index(batch_op.f('ix_issues_submitter_id'), ['submitter_id'], unique=False)
        if 'ix_issues_assignee_id' not in existing_issue_indexes:
            batch_op.create_index(batch_op.f('ix_issues_assignee_id'), ['assignee_id'], unique=False)
        if 'ix_issues_club_created' not in existing_issue_indexes:
            batch_op.create_index('ix_issues_club_created', ['club_id', 'created_at'], unique=False)

    if 'issue_comments' not in existing_tables:
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
    existing_ic_indexes = {i['name'] for i in inspector.get_indexes('issue_comments')} if 'issue_comments' in existing_tables else set()
    with op.batch_alter_table('issue_comments', schema=None) as batch_op:
        if 'ix_issue_comments_issue_id' not in existing_ic_indexes:
            batch_op.create_index(batch_op.f('ix_issue_comments_issue_id'), ['issue_id'], unique=False)

    from datetime import datetime, timezone

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
        # role_permissions.club_id is NOT NULL on prod (set by
        # a1b2c3d4e5f7). Insert one row per (role, club) so the
        # permission is granted in every club.
        club_rows = conn.execute(sa.text("SELECT id FROM clubs")).fetchall()
        for role_name in ('SysAdmin', 'ClubAdmin'):
            role_row = conn.execute(
                sa.text("SELECT id FROM auth_roles WHERE name = :role_name"),
                {'role_name': role_name},
            ).fetchone()
            if not role_row:
                continue
            rid = role_row[0]
            for (cid,) in club_rows:
                exists = conn.execute(
                    sa.text("SELECT 1 FROM role_permissions WHERE role_id = :rid AND permission_id = :pid AND club_id = :cid"),
                    {'rid': rid, 'pid': pid, 'cid': cid},
                ).fetchone()
                if not exists:
                    conn.execute(
                        sa.text("INSERT INTO role_permissions (role_id, permission_id, club_id) VALUES (:rid, :pid, :cid)"),
                        {'rid': rid, 'pid': pid, 'cid': cid},
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

    # Drop the dependent table first — that removes its indexes and the
    # foreign keys that reference the parent table. Trying to drop the
    # index first fails with "needed in a foreign key constraint".
    if 'issue_comments' in {t.lower() for t in sa.inspect(op.get_bind()).get_table_names()}:
        op.drop_table('issue_comments')
    if 'issues' in {t.lower() for t in sa.inspect(op.get_bind()).get_table_names()}:
        op.drop_table('issues')
