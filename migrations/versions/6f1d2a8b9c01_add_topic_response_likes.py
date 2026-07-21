"""add topic response likes table

Revision ID: 6f1d2a8b9c01
Revises: ddef9f8b83dd
Create Date: 2026-07-17 19:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '6f1d2a8b9c01'
down_revision = 'ddef9f8b83dd'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('topic_response_likes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('response_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['response_id'], ['topic_responses.id'],
            name=op.f('fk_topic_response_likes_response_id_topic_responses'),
            ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'],
            name=op.f('fk_topic_response_likes_user_id_users'),
            ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_topic_response_likes')),
        sa.UniqueConstraint('response_id', 'user_id',
            name='uq_topic_response_likes_response_user')
    )
    with op.batch_alter_table('topic_response_likes', schema=None) as batch_op:
        batch_op.create_index(
            op.f('ix_topic_response_likes_response_id'),
            ['response_id'], unique=False
        )
        batch_op.create_index(
            op.f('ix_topic_response_likes_user_id'),
            ['user_id'], unique=False
        )


def downgrade():
    with op.batch_alter_table('topic_response_likes', schema=None) as batch_op:
        batch_op.drop_index(op.f('ix_topic_response_likes_user_id'))
        batch_op.drop_index(op.f('ix_topic_response_likes_response_id'))

    op.drop_table('topic_response_likes')