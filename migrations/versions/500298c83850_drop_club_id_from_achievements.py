"""drop club_id from achievements

Revision ID: 500298c83850
Revises: f78bbc878a49
Create Date: 2026-02-27 21:05:06.045522

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '500298c83850'
down_revision = 'f78bbc878a49'
branch_labels = None
depends_on = None


def upgrade():
    from sqlalchemy.engine.reflection import Inspector
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    
    # 1. Drop Foreign Key if it exists
    fks = inspector.get_foreign_keys('achievements')
    if any(fk['name'] == 'fk_achievements_club_id_clubs' for fk in fks):
        with op.batch_alter_table('achievements', schema=None) as batch_op:
            batch_op.drop_constraint('fk_achievements_club_id_clubs', type_='foreignkey')
    
    # 2. Drop Index if it exists
    indexes = inspector.get_indexes('achievements')
    if any(idx['name'] == 'ix_achievements_club_id' for idx in indexes):
        with op.batch_alter_table('achievements', schema=None) as batch_op:
            batch_op.drop_index('ix_achievements_club_id')

    # 3. Drop Column if it exists
    columns = inspector.get_columns('achievements')
    if any(col['name'] == 'club_id' for col in columns):
        with op.batch_alter_table('achievements', schema=None) as batch_op:
            batch_op.drop_column('club_id')


def downgrade():
    from sqlalchemy.engine.reflection import Inspector
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    
    # 1. Add Column if it doesn't exist
    columns = inspector.get_columns('achievements')
    if not any(col['name'] == 'club_id' for col in columns):
        with op.batch_alter_table('achievements', schema=None) as batch_op:
            batch_op.add_column(sa.Column('club_id', sa.INTEGER(), nullable=True))

    # 2. Create Foreign Key if it doesn't exist
    fks = inspector.get_foreign_keys('achievements')
    if not any(fk['name'] == 'fk_achievements_club_id_clubs' for fk in fks):
        with op.batch_alter_table('achievements', schema=None) as batch_op:
            batch_op.create_foreign_key('fk_achievements_club_id_clubs', 'clubs', ['club_id'], ['id'])

    # 3. Create Index if it doesn't exist
    indexes = inspector.get_indexes('achievements')
    if not any(idx['name'] == 'ix_achievements_club_id' for idx in indexes):
        with op.batch_alter_table('achievements', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_achievements_club_id'), ['club_id'], unique=False)
