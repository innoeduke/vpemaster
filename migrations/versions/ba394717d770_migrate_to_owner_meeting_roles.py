"""migrate to owner_meeting_roles

Revision ID: ba394717d770
Revises: 90ce9be2b3f8
Create Date: 2026-01-23 17:42:01.209416

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ba394717d770'
down_revision = '90ce9be2b3f8'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)
    columns = [c['name'] for c in insp.get_columns('meeting_roles')]
    
    # 1. (Handled by 90ce9be2b3f8)


    # 2. Create owner_meeting_roles table
    # Drop first if exists (to handle failed partial migrations)
    if 'owner_meeting_roles' in insp.get_table_names():
        op.drop_table('owner_meeting_roles')
        
    op.create_table('owner_meeting_roles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('meeting_id', sa.Integer(), nullable=True),
        sa.Column('role_id', sa.Integer(), nullable=True),
        sa.Column('contact_id', sa.Integer(), nullable=True),
        sa.Column('session_log_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['contact_id'], ['Contacts.id'], ),
        sa.ForeignKeyConstraint(['meeting_id'], ['Meetings.id'], ),
        sa.ForeignKeyConstraint(['role_id'], ['meeting_roles.id'], ),
        sa.ForeignKeyConstraint(['session_log_id'], ['Session_Logs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_owner_meeting_roles_contact_id'), 'owner_meeting_roles', ['contact_id'], unique=False)
    op.create_index(op.f('ix_owner_meeting_roles_meeting_id'), 'owner_meeting_roles', ['meeting_id'], unique=False)
    op.create_index(op.f('ix_owner_meeting_roles_role_id'), 'owner_meeting_roles', ['role_id'], unique=False)

    # 3. Migrate Data
    # We need to map session_log_owners -> owner_meeting_roles
    # session_log_owners: (session_log_id, contact_id)
    # Target: (meeting_id, role_id, contact_id, session_log_id [conditional])
    
    # helper SQL to get data
    # We join: session_log_owners -> Session_Logs -> Session_Types -> meeting_roles
    # Also JOIN Meetings to get the proper PK (id) from Meeting_Number
    
    sql = sa.text("""
        SELECT 
            slo.session_log_id,
            slo.contact_id,
            m.id as meeting_id,
            mr.id as role_id,
            mr.has_single_owner
        FROM session_log_owners slo
        JOIN Session_Logs sl ON slo.session_log_id = sl.id
        JOIN Meetings m ON sl.Meeting_Number = m.Meeting_Number
        JOIN Session_Types st ON sl.Type_ID = st.id
        JOIN meeting_roles mr ON st.role_id = mr.id
    """)
    
    results = conn.execute(sql).fetchall()
    
    # Prepare inserts
    # Use a set to handle deduplication for shared roles
    # (meeting_id, role_id, contact_id) -> session_log_id (or None)
    
    # Actually, we can just insert row by row, but for shared roles we want DISTINCT entries (meeting_id, role_id, contact_id, NULL)
    # If multiple logs share the same role, they will produce duplicates if we simply loop.
    # So we must verify uniqueness for expected shared entries.
    
    seen_inserts = set()
    inserts = []
    
    for row in results:
        s_id = row.session_log_id
        c_id = row.contact_id
        m_id = row.meeting_id
        r_id = row.role_id
        is_single = row.has_single_owner # Boolean
        
        final_s_id = s_id if is_single else None
        
        # Unique Key for insertion: (meeting, role, contact, session_log_id)
        key = (m_id, r_id, c_id, final_s_id)
        
        if key not in seen_inserts:
            inserts.append({
                'meeting_id': m_id,
                'role_id': r_id,
                'contact_id': c_id,
                'session_log_id': final_s_id
            })
            seen_inserts.add(key)
            
    if inserts:
        op.bulk_insert(
            sa.table('owner_meeting_roles',
                sa.Column('meeting_id', sa.Integer),
                sa.Column('role_id', sa.Integer),
                sa.Column('contact_id', sa.Integer),
                sa.Column('session_log_id', sa.Integer)
            ),
            inserts
        )

    # 4. Drop old table
    op.drop_table('session_log_owners')


def downgrade():
    # Reverse of upgrade
    conn = op.get_bind()
    
    # 1. Recreate session_log_owners
    insp = sa.inspect(conn)
    if 'session_log_owners' not in insp.get_table_names():
        op.create_table('session_log_owners',
            sa.Column('session_log_id', sa.Integer(), nullable=False),
            sa.Column('contact_id', sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(['contact_id'], ['Contacts.id'], name='fk_session_log_owners_contact_id'),
            sa.ForeignKeyConstraint(['session_log_id'], ['Session_Logs.id'], name='fk_session_log_owners_session_log_id'),
            sa.PrimaryKeyConstraint('session_log_id', 'contact_id')
        )
    else:
        # If it already exists (from a failed downgrade attempt), clear it to avoid Duplicate Entry errors
        conn.execute(sa.text("DELETE FROM session_log_owners"))
    
    # 2. Migrate Data Back
    # Warning: Shared roles (session_log_id=NULL) will be harder to map back to specific session logs if distinct logic was lost.
    # But we can try to map to ALL logs of that role in that meeting.
    
    # Get all OwnerMeetingRoles
    sql = sa.text("SELECT * FROM owner_meeting_roles")
    rows = conn.execute(sql).fetchall()
    
    inserts = []
    
    for row in rows:
        c_id = row.contact_id
        m_id = row.meeting_id
        r_id = row.role_id
        s_id = row.session_log_id
        
        if s_id is not None:
            inserts.append({'session_log_id': s_id, 'contact_id': c_id})
        else:
            # Shared Role: Find all session logs for this meeting + role
            # and assign this contact to ALL of them.
            sub_sql = sa.text("""
                SELECT sl.id 
                FROM Session_Logs sl
                JOIN Session_Types st ON sl.Type_ID = st.id
                WHERE sl.Meeting_Number = :m_id AND st.role_id = :r_id
            """)
            logs = conn.execute(sub_sql, {'m_id': m_id, 'r_id': r_id}).fetchall()
            for log in logs:
                inserts.append({'session_log_id': log.id, 'contact_id': c_id})
    
    # Deduplicate inserts just in case
    # List of dicts to set of tuples
    unique_inserts = set()
    final_inserts = []
    for i in inserts:
        key = (i['session_log_id'], i['contact_id'])
        if key not in unique_inserts:
            unique_inserts.add(key)
            final_inserts.append(i)

    if final_inserts:
        op.bulk_insert(
            sa.table('session_log_owners',
                sa.Column('session_log_id', sa.Integer),
                sa.Column('contact_id', sa.Integer)
            ),
            final_inserts
        )

    # 3. Drop owner_meeting_roles
    op.drop_table('owner_meeting_roles')

    # 4. (Handled by 90ce9be2b3f8)

