import sys
import os

# Add current directory to path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from app import create_app, db
from app.models.roster import MeetingRole, RosterRole
from app.models.session import SessionType, OwnerMeetingRoles
from app.models.excomm_officer import ExcommOfficer
from app.models.planner import Planner
from app.constants import GLOBAL_CLUB_ID

# Define standard roles definition
STANDARD_ROLES_DEFS = [
    {
        "new_name": "Ballot Counter",
        "old_names": ["Ballot Counter"],
        "icon": "fa-calculator",
        "award_category": None,
        "needs_approval": False,
        "has_single_owner": False,
        "is_member_only": False,
        "ticket_type": "Role-taker"
    },
    {
        "new_name": "Chief Judge",
        "old_names": ["Contest Chief Judge", "Chief Contest Judge", "Chief Judge"],
        "icon": "fa-gavel",
        "award_category": None,
        "needs_approval": True,
        "has_single_owner": False,
        "is_member_only": False,
        "ticket_type": None
    },
    {
        "new_name": "Contest Chair",
        "old_names": ["Contest Chair"],
        "icon": "fa-microphone",
        "award_category": None,
        "needs_approval": True,
        "has_single_owner": False,
        "is_member_only": False,
        "ticket_type": None
    },
    {
        "new_name": "Election Chair",
        "old_names": ["Election Chair"],
        "icon": "fa-vote-yea",
        "award_category": None,
        "needs_approval": True,
        "has_single_owner": True,
        "is_member_only": False,
        "ticket_type": None
    },
    {
        "new_name": "Moderator",
        "old_names": ["Moderator"],
        "icon": "fa-gavel",
        "award_category": None,
        "needs_approval": True,
        "has_single_owner": True,
        "is_member_only": False,
        "ticket_type": None
    },
    {
        "new_name": "Panelist",
        "old_names": ["Panelist"],
        "icon": "fa-users",
        "award_category": None,
        "needs_approval": True,
        "has_single_owner": False,
        "is_member_only": False,
        "ticket_type": None
    },
    {
        "new_name": "Immediate Past President",
        "old_names": ["IPP", "Immediate Past President"],
        "icon": "fa-handshake-angle",
        "type": "officer",
        "award_category": None,
        "needs_approval": True,
        "has_single_owner": False,
        "is_member_only": False,
        "ticket_type": None
    }
]

def run_conversion():
    app = create_app()
    with app.app_context():
        print("Starting custom roles to standard roles conversion script...\n")
        try:
            for role_def in STANDARD_ROLES_DEFS:
                new_name = role_def["new_name"]
                old_names = role_def["old_names"]
                
                print(f"=== Processing: {new_name} ===")
                
                # 1. Upsert global standard role
                # Look for existing global role with the new name, or any of the old names
                global_role = None
                for name in [new_name] + old_names:
                    global_role = MeetingRole.query.filter_by(name=name, club_id=GLOBAL_CLUB_ID).first()
                    if global_role:
                        break
                
                if global_role:
                    print(f"Found existing global role ID {global_role.id}. Updating to standard attributes and renaming to '{new_name}'...")
                    global_role.name = new_name
                    global_role.icon = role_def["icon"]
                    global_role.type = role_def.get("type", "standard")
                    global_role.award_category = role_def["award_category"]
                    global_role.needs_approval = role_def["needs_approval"]
                    global_role.has_single_owner = role_def["has_single_owner"]
                    global_role.is_member_only = role_def["is_member_only"]
                    global_role.ticket_type = role_def["ticket_type"]
                else:
                    print(f"Creating new global standard role '{new_name}'...")
                    global_role = MeetingRole(
                        name=new_name,
                        icon=role_def["icon"],
                        type=role_def.get("type", "standard"),
                        award_category=role_def["award_category"],
                        needs_approval=role_def["needs_approval"],
                        has_single_owner=role_def["has_single_owner"],
                        is_member_only=role_def["is_member_only"],
                        ticket_type=role_def["ticket_type"],
                        club_id=GLOBAL_CLUB_ID
                    )
                    db.session.add(global_role)
                
                db.session.flush() # Populate the ID
                target_role_id = global_role.id
                print(f"Global role ID: {target_role_id}")
                
                # 2. Find all local/custom overrides (club_id != 1)
                local_roles = MeetingRole.query.filter(
                    MeetingRole.club_id != GLOBAL_CLUB_ID,
                    MeetingRole.name.in_([new_name] + old_names)
                ).all()
                
                if local_roles:
                    print(f"Found {len(local_roles)} local custom overrides to migrate.")
                    for lr in local_roles:
                        print(f"  Migrating local role '{lr.name}' (ID {lr.id}, Club {lr.club_id})...")
                        
                        # A. Migrate RosterRole
                        rrs = RosterRole.query.filter_by(role_id=lr.id).all()
                        for rr in rrs:
                            # Check if the roster entry already has this standard role to avoid constraint violations
                            duplicate = RosterRole.query.filter_by(roster_id=rr.roster_id, role_id=target_role_id).first()
                            if duplicate:
                                db.session.delete(rr)
                            else:
                                rr.role_id = target_role_id
                        
                        # B. Migrate SessionType
                        sts = SessionType.query.filter_by(role_id=lr.id).all()
                        for st in sts:
                            st.role_id = target_role_id
                            
                        # C. Migrate OwnerMeetingRoles
                        omrs = OwnerMeetingRoles.query.filter_by(role_id=lr.id).all()
                        for omr in omrs:
                            omr.role_id = target_role_id
                            
                        # D. Migrate ExcommOfficer
                        eos = ExcommOfficer.query.filter_by(meeting_role_id=lr.id).all()
                        for eo in eos:
                            # Check if duplicate exists
                            duplicate = ExcommOfficer.query.filter_by(excomm_id=eo.excomm_id, meeting_role_id=target_role_id).first()
                            if duplicate:
                                db.session.delete(eo)
                            else:
                                eo.meeting_role_id = target_role_id
                                
                        # E. Migrate Planner
                        planners = Planner.query.filter_by(meeting_role_id=lr.id).all()
                        for p in planners:
                            p.meeting_role_id = target_role_id
                            
                        # F. Delete the local override
                        db.session.delete(lr)
                        print(f"  Deleted local role ID {lr.id}.")
                else:
                    print("No local custom overrides found for this role.")
                print()
                
            db.session.commit()
            print("✅ All custom roles successfully converted to standard roles and local references migrated!")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error during migration: {str(e)}", file=sys.stderr)
            raise e

if __name__ == "__main__":
    run_conversion()
