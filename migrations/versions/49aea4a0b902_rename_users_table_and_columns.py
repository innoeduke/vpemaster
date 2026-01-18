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
    # Check if the table needs to be renamed
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    table_names = inspector.get_table_names()
    
    # Rename table if it exists as 'Users' and 'users' does not exist
    if 'Users' in table_names and 'users' not in table_names:
        op.rename_table('Users', 'users')
    
    # Get the current table name (either 'users' or 'Users')
    current_table_name = 'users' if 'users' in table_names else 'Users'
    
    # Get current columns
    columns = {col['name']: col for col in inspector.get_columns(current_table_name)}
    
    # Rename columns only if they exist with the old names
    with op.batch_alter_table(current_table_name, schema=None) as batch_op:
        if 'Username' in columns:
            batch_op.alter_column('Username', new_column_name='username', existing_type=sa.String(50), nullable=False)
        if 'Email' in columns:
            batch_op.alter_column('Email', new_column_name='email', existing_type=sa.String(120), nullable=True)
        if 'Contact_ID' in columns:
            batch_op.alter_column('Contact_ID', new_column_name='contact_id', existing_type=sa.Integer(), nullable=True)
        if 'Pass_Hash' in columns:
            batch_op.alter_column('Pass_Hash', new_column_name='password_hash', existing_type=sa.String(255), nullable=False)
        if 'Date_Created' in columns:
            batch_op.alter_column('Date_Created', new_column_name='created_at', existing_type=sa.Date(), nullable=True)
        if 'Status' in columns:
            batch_op.alter_column('Status', new_column_name='status', existing_type=sa.String(50), nullable=False, server_default='active')

    # Update FKs pointing to this table - only if they exist
    try:
        with op.batch_alter_table('permission_audits', schema=None) as batch_op:
            batch_op.drop_constraint('permission_audits_ibfk_1', type_='foreignkey')
            batch_op.create_foreign_key(None, 'users', ['admin_id'], ['id'])
    except Exception:
        pass  # Constraint might not exist or already updated

    try:
        with op.batch_alter_table('user_clubs', schema=None) as batch_op:
            batch_op.drop_constraint('user_clubs_ibfk_5', type_='foreignkey')
            batch_op.create_foreign_key(None, 'users', ['user_id'], ['id'], ondelete='CASCADE')
    except Exception:
        pass  # Constraint might not exist or already updated


def downgrade():
    # Note: MySQL automatically updates foreign key references when a table is renamed,
    # so the FK constraints user_clubs_ibfk_5 and permission_audits_ibfk_1 already point
    # to the 'users' table and will automatically update to point to 'Users' when we rename it back.
    # We don't need to drop and recreate them.

    conn = op.get_bind()
    inspector = sa.inspect(conn)
    table_names = inspector.get_table_names()
    
    # Get current columns for 'users'
    columns = {col['name']: col for col in inspector.get_columns('users')} if 'users' in table_names else {}

    with op.batch_alter_table('users', schema=None) as batch_op:
        if 'username' in columns:
            batch_op.alter_column('username', new_column_name='Username', existing_type=sa.String(50), nullable=False)
        if 'email' in columns:
            batch_op.alter_column('email', new_column_name='Email', existing_type=sa.String(120), nullable=True)
        if 'contact_id' in columns:
            batch_op.alter_column('contact_id', new_column_name='Contact_ID', existing_type=sa.Integer(), nullable=True)
        if 'password_hash' in columns:
            batch_op.alter_column('password_hash', new_column_name='Pass_Hash', existing_type=sa.String(255), nullable=False)
        if 'created_at' in columns:
            batch_op.alter_column('created_at', new_column_name='Date_Created', existing_type=sa.Date(), nullable=True)
        if 'status' in columns:
            batch_op.alter_column('status', new_column_name='Status', existing_type=sa.String(50), nullable=False, server_default='active')

    if 'users' in table_names and 'Users' not in table_names:
        op.rename_table('users', 'Users')
