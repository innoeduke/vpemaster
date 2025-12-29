"""add unpublished status to meeting

Revision ID: 8e034df1676e
Revises: 7377df54272a
Create Date: 2025-12-29 16:24:18.461961

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '8e034df1676e'
down_revision = '7377df54272a'
branch_labels = None
depends_on = None


def upgrade():
    # Only update the status column in Meetings table
    # MySQL requires re-creating the ENUM or using ALTER TABLE
    op.execute("ALTER TABLE Meetings MODIFY COLUMN status ENUM('unpublished', 'not started', 'running', 'finished', 'cancelled') NOT NULL DEFAULT 'unpublished'")


def downgrade():
    op.execute("ALTER TABLE Meetings MODIFY COLUMN status ENUM('not started', 'running', 'finished', 'cancelled') NOT NULL DEFAULT 'not started'")
