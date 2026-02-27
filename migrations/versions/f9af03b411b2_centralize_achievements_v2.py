"""centralize_achievements_v2

Revision ID: f9af03b411b2
Revises: 500298c83850
Create Date: 2026-02-27 23:06:24.473326

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'f9af03b411b2'
down_revision = '500298c83850'
branch_labels = None
depends_on = None


def upgrade():
    from sqlalchemy.engine.reflection import Inspector
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    columns = inspector.get_columns('achievements')
    column_names = [col['name'] for col in columns]
    fks = inspector.get_foreign_keys('achievements')
    fk_names = [fk['name'] for fk in fks]

    # Step 1: Add columns as nullable first (so existing rows aren't rejected)
    with op.batch_alter_table('achievements', schema=None) as batch_op:
        if 'user_id' not in column_names:
            batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
        if 'requestor_id' not in column_names:
            batch_op.add_column(sa.Column('requestor_id', sa.Integer(), nullable=True))
        if 'contact_id' in column_names:
            batch_op.alter_column('contact_id',
                   existing_type=mysql.INTEGER(),
                   nullable=True)

    # Step 2: Backfill user_id from user_clubs (contact_id -> user_id mapping)
    conn.execute(sa.text(
        "UPDATE achievements a "
        "JOIN user_clubs uc ON a.contact_id = uc.contact_id "
        "SET a.user_id = uc.user_id "
        "WHERE a.user_id IS NULL OR a.user_id = 0"
    ))

    # Step 3: Delete rows that couldn't be mapped (orphan data)
    conn.execute(sa.text(
        "DELETE FROM achievements WHERE user_id IS NULL OR user_id = 0"
    ))

    # Step 4: Re-inspect after schema changes, then make user_id NOT NULL, drop contact_id, add FKs
    inspector = Inspector.from_engine(conn)
    columns = inspector.get_columns('achievements')
    column_names = [col['name'] for col in columns]
    fks = inspector.get_foreign_keys('achievements')
    fk_names = [fk['name'] for fk in fks]

    with op.batch_alter_table('achievements', schema=None) as batch_op:
        batch_op.alter_column('user_id',
               existing_type=mysql.INTEGER(),
               nullable=False)
        # Drop contact_id FK if it exists
        for fk in fks:
            if 'contact_id' in fk.get('constrained_columns', []):
                batch_op.drop_constraint(fk['name'], type_='foreignkey')
        # Drop contact_id column
        if 'contact_id' in column_names:
            batch_op.drop_column('contact_id')
        if 'fk_achievements_requestor_id_users' not in fk_names:
            batch_op.create_foreign_key(batch_op.f('fk_achievements_requestor_id_users'), 'users', ['requestor_id'], ['id'])
        if 'fk_achievements_user_id_users' not in fk_names:
            batch_op.create_foreign_key(batch_op.f('fk_achievements_user_id_users'), 'users', ['user_id'], ['id'])

    # ### end Alembic commands ###


def downgrade():
    from sqlalchemy.engine.reflection import Inspector
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    columns = inspector.get_columns('achievements')
    column_names = [col['name'] for col in columns]
    fks = inspector.get_foreign_keys('achievements')
    fk_names = [fk['name'] for fk in fks]

    # Step 1: Drop FKs on user_id and requestor_id
    with op.batch_alter_table('achievements', schema=None) as batch_op:
        if 'fk_achievements_user_id_users' in fk_names:
            batch_op.drop_constraint(batch_op.f('fk_achievements_user_id_users'), type_='foreignkey')
        if 'fk_achievements_requestor_id_users' in fk_names:
            batch_op.drop_constraint(batch_op.f('fk_achievements_requestor_id_users'), type_='foreignkey')

    # Step 2: Re-add contact_id column as nullable
    inspector = Inspector.from_engine(conn)
    columns = inspector.get_columns('achievements')
    column_names = [col['name'] for col in columns]

    with op.batch_alter_table('achievements', schema=None) as batch_op:
        if 'contact_id' not in column_names:
            batch_op.add_column(sa.Column('contact_id', sa.Integer(), nullable=True))

    # Step 3: Backfill contact_id from user_clubs (user_id -> contact_id mapping)
    conn.execute(sa.text(
        "UPDATE achievements a "
        "JOIN user_clubs uc ON a.user_id = uc.user_id "
        "SET a.contact_id = uc.contact_id "
        "WHERE a.contact_id IS NULL"
    ))

    # Step 4: Delete rows that couldn't be mapped
    conn.execute(sa.text(
        "DELETE FROM achievements WHERE contact_id IS NULL"
    ))

    # Step 5: Make contact_id NOT NULL, add FK, drop new columns
    inspector = Inspector.from_engine(conn)
    fks = inspector.get_foreign_keys('achievements')
    fk_names = [fk['name'] for fk in fks]
    columns = inspector.get_columns('achievements')
    column_names = [col['name'] for col in columns]

    with op.batch_alter_table('achievements', schema=None) as batch_op:
        batch_op.alter_column('contact_id',
               existing_type=mysql.INTEGER(),
               nullable=False)
        if 'fk_achievements_contact_id_contacts' not in fk_names:
            batch_op.create_foreign_key('fk_achievements_contact_id_contacts', 'Contacts', ['contact_id'], ['id'])
        if 'requestor_id' in column_names:
            batch_op.drop_column('requestor_id')
        if 'user_id' in column_names:
            batch_op.drop_column('user_id')

    # ### end Alembic commands ###
