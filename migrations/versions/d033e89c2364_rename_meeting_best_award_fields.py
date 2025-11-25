"""rename_meeting_best_award_fields

Revision ID: d033e89c2364
Revises: 33229ae767dc
Create Date: 2025-11-25 18:18:55.182158

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'd033e89c2364'
down_revision = '33229ae767dc'
branch_labels = None
depends_on = None


def upgrade():
    # Rename Best_TT_ID to best_table_topic_id
    op.alter_column('Meetings', 'Best_TT_ID', new_column_name='best_table_topic_id',
                    existing_type=mysql.INTEGER(), nullable=True)
    
    # Rename Best_Evaluator_ID to best_evaluator_id
    op.alter_column('Meetings', 'Best_Evaluator_ID', new_column_name='best_evaluator_id',
                    existing_type=mysql.INTEGER(), nullable=True)
    
    # Rename Best_Speaker_ID to best_speaker_id
    op.alter_column('Meetings', 'Best_Speaker_ID', new_column_name='best_speaker_id',
                    existing_type=mysql.INTEGER(), nullable=True)
    
    # Rename Best_Roletaker_ID to best_role_taker_id
    op.alter_column('Meetings', 'Best_Roletaker_ID', new_column_name='best_role_taker_id',
                    existing_type=mysql.INTEGER(), nullable=True)


def downgrade():
    # Rename best_role_taker_id to Best_Roletaker_ID
    op.alter_column('Meetings', 'best_role_taker_id', new_column_name='Best_Roletaker_ID',
                    existing_type=mysql.INTEGER(), nullable=True)
    
    # Rename best_speaker_id to Best_Speaker_ID
    op.alter_column('Meetings', 'best_speaker_id', new_column_name='Best_Speaker_ID',
                    existing_type=mysql.INTEGER(), nullable=True)
    
    # Rename best_evaluator_id to Best_Evaluator_ID
    op.alter_column('Meetings', 'best_evaluator_id', new_column_name='Best_Evaluator_ID',
                    existing_type=mysql.INTEGER(), nullable=True)
    
    # Rename best_table_topic_id to Best_TT_ID
    op.alter_column('Meetings', 'best_table_topic_id', new_column_name='Best_TT_ID',
                    existing_type=mysql.INTEGER(), nullable=True)