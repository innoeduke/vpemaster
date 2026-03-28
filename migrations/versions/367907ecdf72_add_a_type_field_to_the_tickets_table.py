"""add a type field to the tickets table

Revision ID: 367907ecdf72
Revises: 4390b0c7464c
Create Date: 2026-03-06 11:29:59.021778

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '367907ecdf72'
down_revision = '4390b0c7464c'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('tickets')]
    indexes = [i['name'] for i in inspector.get_indexes('tickets')]

    with op.batch_alter_table('tickets', schema=None) as batch_op:
        if 'type' not in columns:
            batch_op.add_column(sa.Column('type', sa.String(length=50), nullable=True))
        if 'uq_tickets_name' in indexes:
            batch_op.drop_index(batch_op.f('uq_tickets_name'))

    # ### end Alembic commands ###


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('tickets')]
    indexes = [i['name'] for i in inspector.get_indexes('tickets')]

    # 1. Remove duplicate ticket rows (keep lowest id per name) before
    #    restoring the unique constraint.  Later migrations may have
    #    inserted rows that share a name but differ by type (e.g.
    #    'Walk-in' Member vs Guest).  We must also reassign any roster
    #    references that point to the rows we are about to delete.
    op.execute("""
        UPDATE roster r
        JOIN tickets t_dup ON r.ticket_id = t_dup.id
        JOIN (
            SELECT name, MIN(id) AS keep_id
            FROM tickets
            GROUP BY name
            HAVING COUNT(*) > 1
        ) dups ON t_dup.name = dups.name AND t_dup.id != dups.keep_id
        SET r.ticket_id = dups.keep_id
    """)
    op.execute("""
        DELETE t FROM tickets t
        JOIN (
            SELECT name, MIN(id) AS keep_id
            FROM tickets
            GROUP BY name
            HAVING COUNT(*) > 1
        ) dups ON t.name = dups.name AND t.id != dups.keep_id
    """)

    # 2. Drop the type column first (before the unique index is restored)
    if 'type' in columns:
        with op.batch_alter_table('tickets', schema=None) as batch_op:
            batch_op.drop_column('type')

    # 3. Recreate the unique index now that names are unique
    # Re-inspect indexes after the batch alter above
    inspector = sa.inspect(conn)
    indexes = [i['name'] for i in inspector.get_indexes('tickets')]
    if 'uq_tickets_name' not in indexes:
        with op.batch_alter_table('tickets', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('uq_tickets_name'), ['name'], unique=True)

    # ### end Alembic commands ###
