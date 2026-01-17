"""Rename Users table and columns

Revision ID: 49aea4a0b902
Revises: 50ea78715e68
Create Date: 2026-01-18 00:23:54.595933

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '49aea4a0b902'
down_revision = '50ea78715e68'
branch_labels = None
depends_on = None


def upgrade():
    # Rename table
    op.rename_table('Users', 'users')

    # Rename columns
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('Username', new_column_name='username', existing_type=sa.String(50), nullable=False)
        batch_op.alter_column('Email', new_column_name='email', existing_type=sa.String(120), nullable=True)
        batch_op.alter_column('Contact_ID', new_column_name='contact_id', existing_type=sa.Integer(), nullable=True)
        # Note: server_default might be lost/changed if not specified, but Status had default='active' which is app level usually, but DB level 'active'
        batch_op.alter_column('Pass_Hash', new_column_name='password_hash', existing_type=sa.String(255), nullable=False)
        batch_op.alter_column('Date_Created', new_column_name='created_at', existing_type=sa.Date(), nullable=True)
        batch_op.alter_column('Status', new_column_name='status', existing_type=sa.String(50), nullable=False, server_default='active')

    # Update FKs pointing to this table
    with op.batch_alter_table('permission_audits', schema=None) as batch_op:
        # Constraint name might vary, but assuming the one from autogen is correct.
        # If strict naming convention is used by Alembic, this works. 
        # Safest to try dropping by name if known, else we might leave old constraint? 
        # MySQL usually updates FK target table name automatically on rename, but let's be explicit to match metadata.
        batch_op.drop_constraint('permission_audits_ibfk_1', type_='foreignkey')
        batch_op.create_foreign_key(None, 'users', ['admin_id'], ['id'])

    with op.batch_alter_table('user_clubs', schema=None) as batch_op:
        batch_op.drop_constraint('user_clubs_ibfk_5', type_='foreignkey')
        batch_op.create_foreign_key(None, 'users', ['user_id'], ['id'], ondelete='CASCADE')


def downgrade():
    with op.batch_alter_table('user_clubs', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.create_foreign_key('user_clubs_ibfk_5', 'Users', ['user_id'], ['id'], ondelete='CASCADE')

    with op.batch_alter_table('permission_audits', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.create_foreign_key('permission_audits_ibfk_1', 'Users', ['admin_id'], ['id'])

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('username', new_column_name='Username', existing_type=sa.String(50), nullable=False)
        batch_op.alter_column('email', new_column_name='Email', existing_type=sa.String(120), nullable=True)
        batch_op.alter_column('contact_id', new_column_name='Contact_ID', existing_type=sa.Integer(), nullable=True)
        batch_op.alter_column('password_hash', new_column_name='Pass_Hash', existing_type=sa.String(255), nullable=False)
        batch_op.alter_column('created_at', new_column_name='Date_Created', existing_type=sa.Date(), nullable=True)
        batch_op.alter_column('status', new_column_name='Status', existing_type=sa.String(50), nullable=False, server_default='active')

    op.rename_table('users', 'Users')
