
from app.models.base import db
from app.models.contact import Contact
from app.models.club import Club
from app.models.contact_club import ContactClub
from app.models.user import User
from app.models.user_club import UserClub
from app.models.meeting import Meeting
from app.models.session import SessionLog, SessionType, OwnerMeetingRoles
from app.models.roster import Roster, RosterRole, MeetingRole
from app.models.ticket import Ticket
from app.models.media import Media
from app.models.achievement import Achievement
from app.models.voting import Vote
from app.constants import SessionTypeID
from datetime import datetime
import os

class DataImportService:
    
    def __init__(self, club_no):
        self.club_no = club_no
        self.club_id = None # Resolved later
        
        # Mappings: Source ID -> Target Object
        self.contact_map = {}  # Source Contact ID -> Target Contact Obj
        self.media_map = {}    # Source Media ID -> Target Media Obj
        self.meeting_map = {}  # Source Meeting Number -> Target Meeting Obj
        self.session_type_map = {} # Source Type ID -> Target Type ID

    def resolve_club(self):
        """Resolves club_no to club_id."""
        club = Club.query.filter_by(club_no=str(self.club_no)).first()
        if club:
            self.club_id = club.id
            print(f"Resolved Club No {self.club_no} to ID {self.club_id}")
        else:
            print(f"Club No {self.club_no} not found. Will be created if imported.")

    def create_tables(self, ddl_map):
        """Creates tables if they do not exist."""
        print("Ensuring target schema exists... (SKIPPED by request)")
        # db.create_all()
        
        print("Checking for additional tables from backup... (SKIPPED by request)")
        # from sqlalchemy import inspect
        # inspector = inspect(db.engine)
        # existing_tables = inspector.get_table_names()
        
        # for table_name, ddl in ddl_map.items():
        #     if table_name.lower() not in [t.lower() for t in existing_tables]:
        #         print(f"Table '{table_name}' missing. Creating... (SKIPPED)")
                # Be careful executing raw DDL from backup (can be dangerous/messy)
                # But per requirement: "if a table is absent, then create the table"
                # try:
                #     # Clean DDL? Backup usually has "CREATE TABLE `X` (...)"
                #     db.session.execute(db.text(ddl))
                #     print(f"Created table {table_name}.")
                # except Exception as e:
                #     print(f"Failed to create table {table_name}: {e}")
        # db.session.commit()

    def import_clubs(self, clubs_data):
        print(f"Importing clubs...")
        from app.models.club import Club
        # Source Schema assumption: id, club_no, name, short, district, division, area, address, meet_date, meet_time, phone, web, logo, founded, excomm_id...
        
        for row in clubs_data:
            c_no = row[1]
            existing = Club.query.filter_by(club_no=c_no).first()
            if existing:
                if c_no == str(self.club_no):
                    self.club_id = existing.id
                continue
                
            new_club = Club(
                club_no=c_no,
                club_name=row[2],
                short_name=row[3],
                # Map other fields safely by index or None
            )
            # Add more fields based on schema knowledge or index safety
            if len(row) > 4: new_club.district = row[4]
            if len(row) > 5: new_club.division = row[5]
            if len(row) > 6: new_club.area = row[6]
            
            db.session.add(new_club)
            db.session.flush()
            
            if c_no == str(self.club_no):
                self.club_id = new_club.id
                
        db.session.commit()

    def import_excomm(self, excomm_data):
        print(f"Importing excomm...")
        from app.models.excomm import ExComm
        # Target Schema: id, club_id, term, start, end, name, pres, vpe, vpm, vppr, sec, treas, saa, ipp, created, updated
        # Source Schema assumption needed.
        # Assuming Source matches Target or similar.
        # Let's assume strict match for now or safe parsing.
        
        count = 0
        for row in excomm_data:
             # Basic check if club matches
             # But excomm usually has club_id column.
             # If source has ID: 1, Term: 2, Start: 3...
             
             # If source is backup of THIS DB, columns match?
             # Let's map safely based on position for now.
             
             # Map Source ID 
             # Check dedup: Term + Club
             
             if not self.club_id:
                 print("Skipping excomm import: Club ID not resolved.")
                 return

             c_id = self.club_id # We force import to target club?
             # Or if source has club_id, we map it?
             # If we are importing "backup of club X" into "club Y", we use self.club_id.
             
             term = row[2] # Index 2? id=0, club_id=1, term=2.
             
             existing = Excomm.query.filter_by(club_id=c_id, excomm_term=term).first()
             if not existing:
                 new_exc = Excomm(
                     club_id=c_id,
                     excomm_term=term,
                     start_date=self._parse_date(row[3]),
                     end_date=self._parse_date(row[4]),
                     excomm_name=row[5],
                     president_id=self._map_contact(row[6]),
                     vpe_id=self._map_contact(row[7]),
                     vpm_id=self._map_contact(row[8]),
                     vppr_id=self._map_contact(row[9]),
                     secretary_id=self._map_contact(row[10]),
                     treasurer_id=self._map_contact(row[11]),
                     saa_id=self._map_contact(row[12]),
                     ipp_id=self._map_contact(row[13])
                 )
                 db.session.add(new_exc)
                 count += 1
        db.session.commit()
        print(f"Imported {count} excomm entries.")



    def import_session_types(self, types_data):
        print(f"Importing session types mapping...")
        for row in types_data:
            # Schema: id, Title, DefaultOwner, DurMin, DurMax, IsSection, Predef, ValidProj, IsHidden, RoleID
            source_id = row[0]
            title = row[1]
            
            existing = SessionType.query.filter_by(Title=title).first()
            if existing:
                self.session_type_map[source_id] = existing.id
                # Update role_id if missing or changed (Sync logic)
                mapped_role_id = self.role_map.get(row[9]) if hasattr(self, 'role_map') else None
                if mapped_role_id and existing.role_id != mapped_role_id:
                    print(f"Updating role_id for {title} from {existing.role_id} to {mapped_role_id}")
                    existing.role_id = mapped_role_id
                    db.session.add(existing)
                    db.session.flush()
            else:
                 # Create new if needed (Optional, usually predefined)
                 # Converting Source Schema to Target
                 new_type = SessionType(
                     Title=title,
                     Default_Owner=row[2],
                     Duration_Min=row[3],
                     Duration_Max=row[4],
                     Is_Section=bool(row[5]),
                     Predefined=bool(row[6]),
                     Valid_for_Project=bool(row[7]),
                     Is_Hidden=bool(row[8]),
                     role_id=self.role_map.get(row[9]) if hasattr(self, 'role_map') else None
                 )
                 db.session.add(new_type)
                 db.session.flush()
                 self.session_type_map[source_id] = new_type.id
        db.session.commit()

    def import_meeting_roles(self, roles_data):
        print(f"Importing meeting roles definitions...")
        # Source Schema (deduced): id, Name, Icon, Category, Type, count_comp, evaluable, unique
        # Target Schema (MeetingRole): id, name, icon, unique_per_meeting, count_for_competent, is_evaluable, role_group?
        
        for row in roles_data:
            source_id = row[0]
            name = row[1]
            
            existing = MeetingRole.query.filter_by(name=name).first()
            if not existing:
                new_role = MeetingRole(
                    name=name,
                    icon=row[2],
                    # Map other fields if possible
                    # Assuming basic string/bool mapping
                    # Target might not match 1:1, but Name is key.
                )
                db.session.add(new_role)
                db.session.flush()
                # We assume ID sync isn't strictly required if we map by Name later
                # But for SessionType link, we need the ID.
                # If IDs don't match, we need a map.
                # But let's rely on string matching 'Name' in session_types?
                # No, Session_Types has RoleID (Int).
                # So we must map Source RoleID -> Target RoleID
            
            # Since we can't easily map arbitrary source IDs to Target IDs without a map
            # We skip complex logic and assume source logic relies on DB IDs match if we force them?
            # No, standard is Map.
            # But here `import_session_types` reads `row[9]` (RoleID).
            # We need to know which Target ID that source `row[9]` maps to.
            # So we need `self.role_map`.
            
        # Simplified: Just create map using names?
        # Source RoleID X -> Name 'Toastmaster' -> Target Role Y.
        self.role_map = {} # SourceID -> TargetID
        for row in roles_data:
             s_id = row[0]
             name = row[1]
             target = MeetingRole.query.filter_by(name=name).first()
             if target:
                 self.role_map[s_id] = target.id
        
        print(f"Mapped {len(self.role_map)} meeting roles.")


        
    def import_contacts(self, contacts_data):
        """
        Imports contacts.
        Deduced Schema based on backup:
        ...
        10: Mentor_ID
        ...
        """
        print(f"Importing {len(contacts_data)} contacts...")
        count = 0
        mentor_updates = [] # (target_contact, mentor_ref)
        
        for row in contacts_data:

            source_id = row[0]
            name = row[1]
            
            # Map indices safely
            def get_idx(i): return row[i] if len(row) > i else None
            
            phone = get_idx(7)
            bio = get_idx(8)
            email = get_idx(9)
            member_id = get_idx(10)
            
            # Email heuristics removed as index is now explicitly correct
            final_member_id = member_id

            
            # 1. Deduplication
            target_contact = None
            
            # Check by Name
            target_contact = Contact.query.filter_by(Name=name).first()
            
            if not target_contact and email:
                target_contact = Contact.query.filter_by(Email=email).first()
            
            if not target_contact and phone:
                target_contact = Contact.query.filter_by(Phone_Number=phone).first()
                
            if not target_contact:
                target_contact = Contact(
                    Name=name,
                    Email=email,
                    Phone_Number=phone,
                    Type=get_idx(4) or 'Guest',
                    Date_Created=self._parse_date(get_idx(3)),
                    DTM=bool(get_idx(5)),
                    Completed_Paths=get_idx(6),
                    Bio=bio,
                    Member_ID=final_member_id,
                    Current_Path=get_idx(12),
                    Next_Project=get_idx(13),
                    credentials=get_idx(14),
                    Avatar_URL=os.path.basename(get_idx(15)) if get_idx(15) and get_idx(15) != 'NULL' else None
                )
                db.session.add(target_contact)
                db.session.flush()
                count += 1
            else:
                if email: target_contact.Email = email
                if final_member_id: target_contact.Member_ID = final_member_id
                if get_idx(12): target_contact.Current_Path = get_idx(12)
                if get_idx(13): target_contact.Next_Project = get_idx(13)
                if get_idx(14): target_contact.credentials = get_idx(14)
            if target_contact.Name and not (target_contact.first_name or target_contact.last_name):
                 parts = target_contact.Name.strip().split(' ', 1)
                 target_contact.first_name = parts[0]
                 if len(parts) > 1:
                     target_contact.last_name = parts[1]
                 # print(f"DEBUG: Split name '{target_contact.Name}' -> '{target_contact.first_name}' '{target_contact.last_name}'")

            # Map Source ID -> Target Contact
            self.contact_map[source_id] = target_contact
            
            # Defer Mentor Update (using Mentor_ID index 11)
            m_ref = get_idx(11)
            if m_ref and m_ref != 'NULL':
                mentor_updates.append((target_contact, m_ref))

            # 2. Association (ContactClub)
            if self.club_id:

                existing_cc = ContactClub.query.filter_by(contact_id=target_contact.id, club_id=self.club_id).first()
                if not existing_cc:
                    db.session.add(ContactClub(contact_id=target_contact.id, club_id=self.club_id))
        
        db.session.commit()
        
        # Process deferred mentors
        print(f"Processing {len(mentor_updates)} mentor links...")
        for contact, m_ref in mentor_updates:
            # Try to find mentor by Member_ID (which we mapped from col 9)
            # Or Name?
            # m_ref is like 'PN-02745573'. 
            mentor = Contact.query.filter_by(Member_ID=m_ref).first()
            if mentor:
                contact.Mentor_ID = mentor.id
                db.session.add(contact)
        db.session.commit()
        
        print(f"Imported {count} new contacts.")


    def import_users(self, users_data):
        """
        Imports users.
        Schema (Deduced from backup): 
        0: id
        1: username
        2: created_at
        3: password_hash
        4: contact_id (Source)
        5: email
        6: status
        """
        print(f"Importing {len(users_data)} users...")
        count = 0
        for row in users_data:
            username = row[1]
            # row[4] is Contact ID, row[5] is Email
            email = row[5] if len(row) > 5 else None 
            
            target_user = User.query.filter((User.username == username) | (User.email == email)).first()
            
            if not target_user:
                target_user = User(
                    username=username,
                    password_hash=row[3], # Hash
                    email=email,
                    created_at=self._parse_date(row[2]),
                    status=row[6] if len(row) > 6 else 'active'
                )
                db.session.add(target_user)
                db.session.flush()
                count += 1
                
            # Association & Name Sync
            source_contact_id = row[4] 
            target_contact = self.contact_map.get(source_contact_id)

            
            if target_user:
                 # Fix Email if incorrect (e.g. from previous bad import)
                 if email and target_user.email != email:
                     print(f"Updating email for {username} from {target_user.email} to {email}")
                     target_user.email = email
            
            if target_contact:
                # Sync member_no from contact
                if target_contact.Member_ID:
                    target_user.member_no = target_contact.Member_ID
                
                # Sync names from contact to user
                # We assume Contact import handled name splitting correctly
                if target_contact.first_name:
                    target_user.first_name = target_contact.first_name
                if target_contact.last_name:
                    target_user.last_name = target_contact.last_name
                
                # Link UserClub
                uc = UserClub.query.filter_by(user_id=target_user.id, club_id=self.club_id).first()
                if not uc:
                    uc = UserClub(
                        user_id=target_user.id,
                        club_id=self.club_id,
                        contact_id=target_contact.id,
                        club_role_level=1 # Default Member level
                    )
                    db.session.add(uc)
                elif not uc.contact_id:
                    uc.contact_id = target_contact.id

        db.session.commit()
        print(f"Imported {count} new users.")

    def import_meetings(self, meetings_data):
        print(f"Importing {len(meetings_data)} meetings...")
        count = 0
        for row in meetings_data:
            # Schema: id, Number, Date, Template, WOD, BestTT, BestEval, BestSpk, BestRole, Start, Media, Title, Type, Sub, Status, Manager, GE, NPS
            meeting_no = row[1]
            
            existing = Meeting.query.filter_by(Meeting_Number=meeting_no).first()
            if existing:
                self.meeting_map[meeting_no] = existing
                continue
            
            # Create
                
            # Create
            new_meeting = Meeting(
                Meeting_Number=meeting_no,
                club_id=self.club_id,
                Meeting_Date=self._parse_date(row[2]),
                Meeting_Template=row[3],
                WOD=row[4],
                best_table_topic_id=self._map_contact(row[5]),
                best_evaluator_id=self._map_contact(row[6]),
                best_speaker_id=self._map_contact(row[7]),
                best_role_taker_id=self._map_contact(row[8]),
                Start_Time=self._parse_time(row[9]),
                # Media handled later? Or now if map exists? We import media later? No, usually Media table first?
                # Circular dependency. We can update media_id later or import media first.
                # Let's assume Media is imported FIRST.
                media_id=self.media_map.get(row[10]) if row[10] else None,
                Meeting_Title=row[11],
                type=row[12],
                Subtitle=row[13],
                status=row[14] or 'unpublished',
                manager_id=self._map_contact(row[15]),
                # ge_mode=row[16], nps=row[17]
            )
            db.session.add(new_meeting)
            db.session.flush()
            self.meeting_map[meeting_no] = new_meeting
            count += 1
            
        db.session.commit()
        print(f"Imported {count} new meetings.")

    def import_session_logs(self, logs_data):
        print(f"Importing {len(logs_data)} session logs...")
        count = 0 
        for row in logs_data:
            # Schema: id, MeetNo, TypeID, Start, Min, Max, Seq, Notes, Title, ProjID, Status, Code, State, Pathway, OwnerID(Legacy?)
            # Wait, live schema for `Session_Logs` does NOT have Owner_ID.
            # Source schema from step 44: id, MeetNo, TypeID, Owner_ID, Start...
            # Index 3 is Owner_ID.
            
            meet_no = row[1]
            if meet_no not in self.meeting_map:
                continue # Skip if meeting ignored
                
            meeting_obj = self.meeting_map[meet_no]
            
            # Check duplicate Session Log? (Title + Meeting)
            session_title = row[9] # Schema varying, strictly check index
            # Source (Step 44): 0:id, 1:MeetNo, 2:TypeID, 3:OwnerID, 4:Start, 5:Min, 6:Max, 7:Seq, 8:Notes, 9:Title ...
            
            # Simple dedup: If meeting is NEW (count > 0 in import_meetings), we insert all.
            # If meeting was EXISTING, we act conservatively: skip or insert missing?
            # Decision: Insert if not exists matching (Title, Type).
            
            # Note: Type_ID might need mapping if ID changed, but usually SessionTypes are static.
            # We assume SessionTypes IDs match or we rely on them.
            type_id = self.session_type_map.get(row[2])
            if not type_id:
                # Fallback: if not in map, assume existing (dangerous but original behavior)
                type_id = row[2]
                # Better: Check DB?
                # If we skipped importing types, map is empty.
                # But we should rely on map if provided.
                # If map has entries, use it. If empty, maybe assume identity?
                if self.session_type_map:
                     print(f"WARNING: Type ID {row[2]} not found in map. Skipping log {row}.")
                     continue
            
            # Resolve Owner BEFORE log deduplication
            source_owner_id = row[3]
            target_contact = self.contact_map.get(source_owner_id)
            
            st = SessionType.query.get(type_id)
            is_single_owner = st.role.has_single_owner if st and st.role else True
            
            # Check duplicate Session Log
            target_log = None
            if is_single_owner and target_contact:
                # If single-owner role, logs should be unique PER owner if title/type match
                target_log = SessionLog.query.join(OwnerMeetingRoles).filter(
                    SessionLog.Meeting_Number == meet_no,
                    SessionLog.Session_Title == (session_title if session_title else ""),
                    SessionLog.Type_ID == type_id,
                    OwnerMeetingRoles.contact_id == target_contact.id
                ).first()
                
            if not target_log and not is_single_owner:
                # Fallback to title/type match ONLY for shared roles
                target_log = SessionLog.query.filter_by(
                    Meeting_Number=meet_no,
                    Session_Title=session_title if session_title else "",
                    Type_ID=type_id
                ).first()
            
            # Capture credential from source (Index 12)
            source_credential = row[12] if len(row) > 12 else None
            
            # Determine if this log is a Project/Speech
            # Using simple check on Project_ID (row[10]) and Session Type?
            # We don't have session_type object easily available yet (type_id is row[3])
            # But we fetched it earlier
            is_prepared_speech = False
            session_type = db.session.get(SessionType, type_id)
            if session_type:
                 is_prepared_speech = (session_type.id == SessionTypeID.PREPARED_SPEECH) or (session_type.Title == 'Presentation')
            
            project_id = row[10]
            should_import_metadata = (project_id is not None) or is_prepared_speech
            
            if not target_log:
                new_log = SessionLog(
                    Meeting_Number=meet_no,
                    Type_ID=type_id,
                    Start_Time=self._parse_time(row[4]),
                    Duration_Min=row[5],
                    Duration_Max=row[6],
                    Meeting_Seq=row[7],
                    Notes=row[8],
                    Session_Title=session_title,
                    Project_ID=project_id,
                    Status=row[11],
                    # credentials=row[12], Removed in SessionLog but used in OwnerMeetingRoles
                    project_code=row[13] if should_import_metadata else None,
                    state=row[14],
                    pathway=row[15] if should_import_metadata else None
                )
                db.session.add(new_log)
                db.session.flush()
                count += 1
                target_log = new_log
            
            # Link Owner
            if target_contact:
                # Sync User member_no if linked via UserClub
                for uc in target_contact.user_club_records:
                    if uc.user and target_contact.Member_ID and not uc.user.member_no:
                        uc.user.member_no = target_contact.Member_ID
                
                # Check / Create OwnerMeetingRoles
                if st and st.role_id:
                    # Determine if single owner
                    is_single_owner = st.role.has_single_owner if st.role else True
                    
                    # Check owner link
                    query = OwnerMeetingRoles.query.filter_by(
                         meeting_id=meeting_obj.id,
                         role_id=st.role_id
                    )
                    
                    target_log_id = target_log.id if is_single_owner else None
                    if is_single_owner:
                        query = query.filter_by(session_log_id=target_log_id)
                    else:
                        query = query.filter(OwnerMeetingRoles.session_log_id == None)
                        
                    omr = query.filter_by(contact_id=target_contact.id).first()
                    
                    if not omr:
                        omr = OwnerMeetingRoles(
                            meeting_id=meeting_obj.id,
                            role_id=st.role_id,
                            contact_id=target_contact.id,
                            session_log_id=target_log_id
                        )
                    
                    # Update credential if available and missing? Or always overwrite from source?
                    # Source is backup, so we trust it.
                    if source_credential:
                        omr.credential = source_credential
                        
                    db.session.add(omr)

        db.session.commit()
        print(f"Imported {count} session logs.")

    def import_roster(self, roster_data):
        print(f"Importing roster...")
        count = 0
        for row in roster_data:
            # Schema: id, MeetNo, Order, Ticket(String), ContactID, Type
            # Target Schema: id, MeetNo, Order, ContactID, Type, TicketID(Int)
            
            meet_no = row[1]
            if meet_no not in self.meeting_map:
                continue
                
            contact_id = self._map_contact(row[4])
            ticket_str = row[3]
            
            ticket_id = None
            if ticket_str:
                ticket = Ticket.query.filter_by(name=ticket_str).first()
                if not ticket:
                    ticket = Ticket(name=ticket_str)
                    db.session.add(ticket)
                    db.session.flush()
                ticket_id = ticket.id
                
            # Dedup
            existing = Roster.query.filter_by(meeting_number=meet_no, order_number=row[2]).first()
            if not existing:
                new_roster = Roster(
                    meeting_number=meet_no,
                    order_number=row[2],
                    contact_id=contact_id,
                    contact_type=row[5],
                    ticket_id=ticket_id
                )
                db.session.add(new_roster)
                count += 1
                
        db.session.commit()
        print(f"Imported {count} roster entries.")

    def import_media(self, media_data):
        print(f"Importing media...")
        for row in media_data:
            # id, log_id, url, notes
            # We import media primarily to link to meetings/logs.
            # But logs/meetings link TO media.
            # Logic: Import Media first?
            # Schema: id, log_id, url, notes
            
            source_id = row[0]
            url = row[2]
            
            existing = Media.query.filter_by(url=url).first()
            if existing:
                self.media_map[source_id] = existing.id
            else:
                new_media = Media(url=url, notes=row[3])
                db.session.add(new_media)
                db.session.flush()
                self.media_map[source_id] = new_media.id
        
        db.session.commit()

    def _map_contact(self, source_id):
        if not source_id: return None
        contact = self.contact_map.get(source_id)
        return contact.id if contact else None

    def _parse_date(self, val):
        if not val or val == 'NULL': return None
        if isinstance(val, (str, bytes)):
             try: return datetime.strptime(str(val), '%Y-%m-%d').date()
             except: return None
        return val

    def _parse_time(self, val):
        if not val or val == 'NULL': return None
        # Handle time parsing format
        try:
             # Try varying formats or split
             if len(str(val)) > 8: val = str(val)[:8]
             return datetime.strptime(str(val), '%H:%M:%S').time()
        except: return None

    def import_achievements(self, achievements_data):
        print(f"Importing achievements...")
        count = 0 
        for row in achievements_data:
            # Schema: id, contact_id, member_id, date, type, path_name, level, notes
            source_contact_id = row[1]
            target_contact_id = self._map_contact(source_contact_id)
            if not target_contact_id: continue
            
            # Dedup: Contact + Date + Type + Level? 
            # Or just check if identical record exists.
            existing = Achievement.query.filter_by(
                contact_id=target_contact_id,
                issue_date=self._parse_date(row[3]),
                achievement_type=row[4],
                level=row[6]
            ).first()
            
            if not existing:
                new_ach = Achievement(
                    contact_id=target_contact_id,
                    member_id=row[2],
                    issue_date=self._parse_date(row[3]),
                    achievement_type=row[4],
                    path_name=row[5],
                    level=row[6],
                    notes=row[7]
                )
                db.session.add(new_ach)
                count += 1
        
        db.session.commit()
        print(f"Imported {count} achievements.")

    def import_votes(self, votes_data):
        print(f"Importing votes...")
        count = 0
        for row in votes_data:
            # Schema: id, meeting_number, voter_id, category, contact_id, question, score, comments
            meet_no = row[1]
            if meet_no not in self.meeting_map:
                continue
                
            contact_id = self._map_contact(row[4])
            
            # Dedup: Meeting + Voter + Category + Contact?
            existing = Vote.query.filter_by(
                meeting_number=meet_no,
                voter_identifier=row[2],
                award_category=row[3],
                contact_id=contact_id
            ).first()
            
            if not existing:
                new_vote = Vote(
                    meeting_number=meet_no,
                    voter_identifier=row[2],
                    award_category=row[3],
                    contact_id=contact_id,
                    question=row[5],
                    score=row[6],
                    comments=row[7]
                )
                db.session.add(new_vote)
                count += 1
                
        db.session.commit()
        print(f"Imported {count} votes.")

