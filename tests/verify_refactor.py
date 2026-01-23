import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.session import SessionLog, SessionType, OwnerMeetingRoles
from app.models.roster import MeetingRole
from app.models.contact import Contact
from app.models.meeting import Meeting
from app.services.role_service import RoleService

def verify_refactor():
    app = create_app()
    with app.app_context():
        print("Setting up test data...")
        # 1. Create Meeting
        m_num = 9999
        meeting = Meeting.query.filter_by(Meeting_Number=m_num).first()
        if meeting:
            print("Cleaning up old test meeting...")
            meeting.delete_full()
            
        from app.models.club import Club
        club = Club.query.first()
        if not club:
            print("No club found.")
            return

        meeting = Meeting(Meeting_Number=m_num, club_id=club.id, Meeting_Date='2026-01-01')
        db.session.add(meeting)
        db.session.commit()
        
        # 2. Create Roles
        # Distinct Role
        r_distinct = MeetingRole.query.filter_by(name="TestDistinct").first()
        if not r_distinct:
            r_distinct = MeetingRole(name="TestDistinct", type="standard", 
                                     needs_approval=False, has_single_owner=True)
            db.session.add(r_distinct)
        else:
            r_distinct.has_single_owner = True
            
        # Shared Role
        r_shared = MeetingRole.query.filter_by(name="TestShared").first()
        if not r_shared:
            r_shared = MeetingRole(name="TestShared", type="standard", 
                                   needs_approval=False, has_single_owner=False)
            db.session.add(r_shared)
        else:
            r_shared.has_single_owner = False
        
        db.session.commit()
        
        # 3. Create Session Types
        st_distinct = SessionType.query.filter_by(Title="TypeDistinct").first()
        if st_distinct:
             db.session.delete(st_distinct)
        st_shared = SessionType.query.filter_by(Title="TypeShared").first()
        if st_shared:
             db.session.delete(st_shared)
        db.session.commit()

        st_distinct = SessionType(Title="TypeDistinct", role_id=r_distinct.id)
        st_shared = SessionType(Title="TypeShared", role_id=r_shared.id)
        db.session.add_all([st_distinct, st_shared])
        db.session.commit()
        
        # 4. Create Logs
        log_d1 = SessionLog(Meeting_Number=m_num, Type_ID=st_distinct.id, Session_Title="D1")
        log_d2 = SessionLog(Meeting_Number=m_num, Type_ID=st_distinct.id, Session_Title="D2")
        log_s1 = SessionLog(Meeting_Number=m_num, Type_ID=st_shared.id, Session_Title="S1")
        log_s2 = SessionLog(Meeting_Number=m_num, Type_ID=st_shared.id, Session_Title="S2")
        
        db.session.add_all([log_d1, log_d2, log_s1, log_s2])
        db.session.commit()
        
        # Get Contacts
        c1 = Contact.query.get(78) or Contact.query.first()
        c2 = Contact.query.filter(Contact.id != c1.id).first()
        
        if not c1 or not c2:
            print("Not enough contacts.")
            return

        print(f"Using contacts: {c1.id} and {c2.id}")
        
        # --- TEST 1: Distinct Role ---
        print("\nTest 1: Distinct Role Assignment")
        # Assign c1 to log_d1
        RoleService.assign_meeting_role(log_d1, [c1.id])
        db.session.commit()
        
        # Verify
        owners_d1 = [o.id for o in log_d1.owners]
        owners_d2 = [o.id for o in log_d2.owners]
        
        print(f"Log D1 Owners: {owners_d1}")
        print(f"Log D2 Owners: {owners_d2}")
        
        if c1.id in owners_d1 and not owners_d2:
            print("PASS: Distinct role assignment is isolated.")
        else:
            print(f"FAIL: Distinct role isolation failed. D1={owners_d1}, D2={owners_d2}")

        # --- TEST 2: Shared Role ---
        print("\nTest 2: Shared Role Assignment")
        # Assign c2 to log_s1
        RoleService.assign_meeting_role(log_s1, [c2.id])
        db.session.commit()
        
        # Verify (Both should show owner because they share the role pool)
        # Refresh objects
        db.session.expire_all()
        log_s1 = db.session.get(SessionLog, log_s1.id)
        log_s2 = db.session.get(SessionLog, log_s2.id)

        owners_s1 = [o.id for o in log_s1.owners]
        owners_s2 = [o.id for o in log_s2.owners]
        
        print(f"Log S1 Owners: {owners_s1}")
        print(f"Log S2 Owners: {owners_s2}")
        
        if c2.id in owners_s1 and c2.id in owners_s2:
            print("PASS: Shared role assignment propagated to all logs of that role.")
        else:
            print(f"FAIL: Shared role propagation failed. S1={owners_s1}, S2={owners_s2}")
            
        # --- TEST 3: Multi-Owner on Distinct ---
        print("\nTest 3: Multi-Owner on Distinct")
        RoleService.assign_meeting_role(log_d1, [c1.id, c2.id])
        db.session.commit()
        
        db.session.expire_all()
        log_d1 = db.session.get(SessionLog, log_d1.id)
        owners_d1 = [o.id for o in log_d1.owners]
        print(f"Log D1 Owners: {owners_d1}")
        
        if c1.id in owners_d1 and c2.id in owners_d1:
             print("PASS: Multi-owner supported on distinct role.")
        else:
             print("FAIL: Multi-owner failed.")

        # Cleanup
        # meeting.delete_full()
        # print("\nCleanup done.")

if __name__ == "__main__":
    verify_refactor()
