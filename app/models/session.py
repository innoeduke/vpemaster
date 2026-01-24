"""Session models including SessionType and SessionLog."""
import re
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import joinedload, subqueryload

from .base import db
from ..constants import ProjectID, SessionTypeID


class SessionType(db.Model):
    __tablename__ = 'Session_Types'
    id = db.Column(db.Integer, primary_key=True)
    Title = db.Column(db.String(255), nullable=False, unique=True)
    Default_Owner = db.Column(db.String(255))
    Is_Section = db.Column(db.Boolean, default=False)
    Is_Hidden = db.Column(db.Boolean, default=False)
    Predefined = db.Column(db.Boolean, default=True)
    Valid_for_Project = db.Column(db.Boolean, default=False)
    Duration_Min = db.Column(db.Integer)
    Duration_Max = db.Column(db.Integer)
    role_id = db.Column(db.Integer, db.ForeignKey('meeting_roles.id'), nullable=True)

    role = db.relationship('app.models.roster.MeetingRole', backref='session_types')



# Association Table for Many-to-Many SessionLog <-> Contact
# [DEPRECATED] session_log_owners = db.Table('session_log_owners', ... )

class OwnerMeetingRoles(db.Model):
    __tablename__ = 'owner_meeting_roles'
    id = db.Column(db.Integer, primary_key=True)
    meeting_id = db.Column(db.Integer, db.ForeignKey('Meetings.id'), index=True)
    role_id = db.Column(db.Integer, db.ForeignKey('meeting_roles.id'), index=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('Contacts.id'), index=True)
    # session_log_id is only populated if role.has_single_owner is True
    session_log_id = db.Column(db.Integer, db.ForeignKey('Session_Logs.id'), nullable=True, index=False)

    meeting = db.relationship('Meeting', backref='owner_roles')
    role = db.relationship('app.models.roster.MeetingRole')
    contact = db.relationship('Contact', backref='meeting_roles')
    session_log = db.relationship('SessionLog', backref='specific_role_owners')


class SessionLog(db.Model):
    __tablename__ = 'Session_Logs'
    id = db.Column(db.Integer, primary_key=True)
    Meeting_Number = db.Column(mysql.SMALLINT(unsigned=True), db.ForeignKey(
        'Meetings.Meeting_Number'), nullable=False)
    Meeting_Seq = db.Column(db.Integer)
    # For custom titles like speeches
    Session_Title = db.Column(db.String(255))
    Type_ID = db.Column(db.Integer, db.ForeignKey(
        'Session_Types.id'), nullable=False)
    
    # [DEPRECATED] Owner_ID and credentials removed in favor of owners relationship
    # Owner_ID = db.Column(db.Integer, db.ForeignKey('Contacts.id'))
    # credentials = db.Column(db.String(255), default='')
    Project_ID = db.Column(db.Integer, db.ForeignKey('Projects.id'))
    Start_Time = db.Column(db.Time)
    Duration_Min = db.Column(db.Integer, default=0)
    Duration_Max = db.Column(db.Integer)
    Notes = db.Column(db.String(1000))
    Status = db.Column(db.String(50))
    state = db.Column(db.String(50), nullable=False,
                      default='active')  # Can be 'active', 'waiting', 'cancelled'
    project_code = db.Column(db.String(10))
    pathway = db.Column(db.String(100))

    meeting = db.relationship('Meeting', backref='session_logs')
    project = db.relationship('Project', backref='session_logs')
    
    # [DEPRECATED] Single Owner Relationship (Primary)
    # owner = db.relationship('Contact', backref='session_logs', foreign_keys=[Owner_ID])
    
    @property
    def owner(self):
        """Helper for primary owner logic (backward compatibility)"""
        owners = self.owners
        return owners[0] if owners else None
    
    # Dynamic Owners Property
    @property
    def owners(self):
        from .contact import Contact
        
    @property
    def owners(self):
        from .contact import Contact
        
        # Safety checks
        if not self.meeting:
            return []
            
        # Determine target role and scope
        target_role_id = 0
        has_single_owner = True
        
        if self.session_type and self.session_type.role:
            target_role_id = self.session_type.role_id
            has_single_owner = self.session_type.role.has_single_owner
            
        query = Contact.query.join(OwnerMeetingRoles).filter(
            OwnerMeetingRoles.meeting_id == self.meeting.id,
            OwnerMeetingRoles.role_id == target_role_id
        )
        if has_single_owner:
             query = query.filter(OwnerMeetingRoles.session_log_id == self.id)
        else:
             # For shared roles, session_log_id is NULL
             query = query.filter(OwnerMeetingRoles.session_log_id == None)
        return query.all()

    @owners.setter
    def owners(self, value):
        from .contact import Contact
        
        # Handle different input types (list of objects, list of IDs, single object, single ID)
        new_owner_ids = []
        if isinstance(value, (list, tuple)):
            for item in value:
                if hasattr(item, 'id'):
                    new_owner_ids.append(item.id)
                elif isinstance(item, int):
                    new_owner_ids.append(item)
        elif hasattr(value, 'id'):
            new_owner_ids = [value.id]
        elif isinstance(value, int):
            new_owner_ids = [value]
        elif value is None:
            new_owner_ids = []
            
        # Use class method to update junction table
        self.set_owners(self, new_owner_ids)

    # Legacy relationship removed/replaced by property logic
    # owners = db.relationship(...)

    session_type = db.relationship('SessionType', backref='session_logs')

    media = db.relationship('Media', backref='session_log',
                            uselist=False, cascade='all, delete-orphan')

    def derive_project_code(self, owner_contact=None):
        """
        Derives the 'project_code' based on the role, project, and owner's pathway.
        Consolidated logic from legacy utils.derive_project_code.
        """
        from ..utils import get_project_code
        from .project import Pathway
        
        contact = owner_contact or self.owner
        if not contact or not contact.Current_Path:
            return None

        pathway_name = contact.Current_Path
        path_obj = db.session.query(Pathway).filter_by(name=pathway_name).first()
        if not path_obj:
            return None

        pathway_suffix = path_obj.abbr
        role_name = self.session_type.role.name if self.session_type and self.session_type.role else None

        # --- Priority 1: Speaker/Evaluator with Project ID ---
        # Dynamically identify roles linked to session types valid for projects
        project_specific_roles = [st.role.name for st in SessionType.query.filter_by(Valid_for_Project=True).all() if st.role]
        
        is_presentation = (self.session_type and self.session_type.Title == 'Presentation')
        
        if (role_name in project_specific_roles or is_presentation) and self.Project_ID:
            # For presentations, we might want to use self.pathway if it's explicitly set to a series
            # but per requirement, we use owner's current path for the DB field, 
            # while Project.get_code will naturally find the series fallback.
            code = get_project_code(self.Project_ID, pathway_name)
            if code:
                return code

        # --- Priority 2: Other roles - Use highest level achievement + 1 ---
        else:
            # Determine base level from contact.credentials for consistency
            start_level = 1
            creds = contact.credentials
            if creds:
                # Match the current path abbreviation followed by a level number
                match = re.match(rf"^{pathway_suffix}(\d+)$", creds.strip().upper())
                if match:
                    level_achieved = int(match.group(1))
                    # If level L is completed, the current work is for level L+1 (capped at 5)
                    start_level = min(level_achieved + 1, 5)
                
            return f"{pathway_suffix}{start_level}"

        return None

    def get_display_level_and_type(self, pathway_cache=None):
        """
        Determine log type, display level, and project code for this session log.
        
        Args:
            pathway_cache (dict, optional): Pre-fetched pathway/project data for performance.
                                            Format: {project_id: {pathway_id: PathwayProject}}
        
        Returns:
            tuple: (display_level, log_type, project_code)
                   - display_level: str (e.g., "1", "2", "General")
                   - log_type: str ("speech" or "role")
                   - project_code: str (e.g., "SR1.1", "EH2.3", or "")
        """
        from .project import Pathway, PathwayProject
        
        display_level = "General"
        log_type = 'role'
        project_code = ""
        
        if not self.session_type or not self.session_type.role:
            return display_level, log_type, project_code
        
        is_prepared_speech = self.project and self.project.is_prepared_speech
        
        # Determine if this is a speech
        if (self.session_type.Valid_for_Project and self.Project_ID and self.Project_ID != ProjectID.GENERIC) or is_prepared_speech:
            log_type = 'speech'
            pathway_abbr = None
            found_data = False
            
            # Priority 1: Lookup PathwayProject data (Canonical)
            if self.Project_ID:
                found_via_cache = False
                if pathway_cache and self.Project_ID in pathway_cache:
                    # Use cached data if available
                    pp_data = pathway_cache[self.Project_ID]
                    if pp_data:
                        # Find the BEST PathwayProject matching the user's context
                        target_path = self.pathway or (self.owner.Current_Path if self.owner else None)
                        first_pp = None
                        
                        if target_path:
                            for pp in pp_data.values():
                                if pp.pathway and pp.pathway.name == target_path:
                                    first_pp = pp
                                    break
                        
                        # Fallback to any if not found
                        if not first_pp:
                             first_pp = next(iter(pp_data.values()))

                        display_level = str(first_pp.level) if first_pp.level else "1"
                        # Optimized: Use pre-loaded relationship from cache
                        if first_pp.pathway and first_pp.pathway.abbr:
                            pathway_abbr = first_pp.pathway.abbr
                        
                        # Set project code from canonical source immediately
                        if pathway_abbr:
                             project_code = f"{pathway_abbr}{first_pp.code}"
                        else:
                             project_code = first_pp.code
                        
                        found_via_cache = True
                        found_data = True
                
                if not found_via_cache:
                    # No cache, query directly
                    # Try to find match with log's own pathway first, then user's current path
                    target_path_name = self.pathway or (self.owner.Current_Path if self.owner else None)
                    
                    if target_path_name:
                        target_path = Pathway.query.filter_by(name=target_path_name).first()
                        if target_path:
                            pp = PathwayProject.query.filter_by(
                                project_id=self.Project_ID, 
                                path_id=target_path.id
                            ).first()
                            if pp:
                                pathway_abbr = target_path.abbr
                                display_level = str(pp.level) if pp.level else "1"
                                project_code = f"{pathway_abbr}{pp.code}" if pathway_abbr else pp.code
                                found_data = True
                        
                    # Fallback: any pathway
                    if not found_data:
                        pp = PathwayProject.query.filter_by(project_id=self.Project_ID).first()
                        if pp:
                            path_obj = db.session.get(Pathway, pp.path_id)
                            if path_obj:
                                pathway_abbr = path_obj.abbr
                                display_level = str(pp.level) if pp.level else "1"
                                project_code = f"{pathway_abbr}{pp.code}"
                                found_data = True

            # Priority 2: Use project_code if no canonical data found (or as supplement?)
            # Actually, if we found data, we trust DB. If not, use snapshot.
            if not found_data and self.project_code:
                match = re.match(r"([A-Z]+)(\d+)", self.project_code)
                if match:
                    pathway_abbr = match.group(1)
                    display_level = str(match.group(2))
                    project_code = self.project_code
        
        else:  # It's a role
            if self.project_code:
                match = re.match(r"([A-Z]+)(\d+)", self.project_code)
                if match:
                    display_level = str(match.group(2))
        
        return display_level, log_type, project_code
    

    
    def update_media(self, url):
        """Update, create, or delete associated media."""
        from .media import Media
        
        if url:
            if self.media:
                self.media.url = url
            else:
                self.media = Media(url=url)
        elif self.media:
            db.session.delete(self.media)

    def update_pathway(self, pathway_name):
        """
        Update log pathway and sync with user profile.
        CRITICAL RULE: Only 'pathway'-type paths (e.g., "Presentation Mastery") are stored in 
        SessionLog.pathway and Contact.Current_Path. 'presentation'-type paths (Series) 
        are used purely for project lookup and should NEVER be saved here.
        """
        from .project import Pathway
        
        if not pathway_name:
            return
            
        # Verify the pathway type in the database
        path_obj = Pathway.query.filter_by(name=pathway_name).first()
        if not path_obj or path_obj.type != 'pathway':
            # Do not allow storing series/presentation-type paths in the main pathway column
            return

        old_pathway = self.pathway
        self.pathway = pathway_name
        
        # Sync to user profile if relevant
        if self.owner and old_pathway != pathway_name:
            # Sync to the Contact's current path (ensures profile is updated)
            self.owner.Current_Path = pathway_name
            db.session.add(self.owner)

    def update_durations(self, data, updated_project=None):
        """
        Update durations based on structural changes.
        Priority: Project Defaults > Session Type Defaults > Preserve Manual Edits.
        """
        new_project_id = data.get('project_id')
        if new_project_id in [None, "", "null"]:
            new_project_id = None
        else:
            try:
                new_project_id = int(new_project_id)
            except (ValueError, TypeError):
                new_project_id = None

        project_changed = (self.Project_ID != new_project_id)
        
        new_st_title = data.get('session_type_title')
        st_changed = (new_st_title and self.session_type and self.session_type.Title != new_st_title)

        # Update Project ID first if provided
        if 'project_id' in data:
            self.Project_ID = new_project_id

        if project_changed and self.Project_ID:
            if updated_project:
                self.Duration_Min = updated_project.Duration_Min
                self.Duration_Max = updated_project.Duration_Max
        elif st_changed:
            new_st = SessionType.query.filter_by(Title=new_st_title).first()
            if new_st:
                self.Duration_Min = new_st.Duration_Min
                self.Duration_Max = new_st.Duration_Max

    def get_summary_data(self):
        """Get project name, code, and pathway for response serialization."""
        from .project import Project
        
        project_name = "N/A"
        project_code = ""
        current_pathway = self.pathway or (self.owner.Current_Path if self.owner else "N/A")

        if self.Project_ID:
            project = db.session.get(Project, self.Project_ID)
            if project:
                project_name = project.Project_Name
                
                # Use the more robust logic to get level, type, and code
                _, _, derived_code = self.get_display_level_and_type()
                project_code = derived_code

        return {
            "project_name": project_name,
            "project_code": project_code,
            "pathway": current_pathway
        }

    def matches_filters(self, pathway=None, level=None, status=None, log_type=None):
        """
        Check if this log matches the given filters.
        
        Args:
            pathway (str, optional): Pathway name to filter by (or 'all' for no filtering)
            level (str, optional): Level to filter by (e.g., "1", "2")
            status (str, optional): Status to filter by (e.g., "Completed")
            log_type (str, optional): Pre-determined log type ("speech" or "role")
        
        Returns:
            bool: True if log matches all provided filters
        """
        # Level filter
        if level and hasattr(self, '_display_level'):
            if self._display_level != level:
                return False
        
        # Pathway filter (only for speeches or if pathway is explicitly set)
        if pathway and pathway != 'all':
            current_log_path = getattr(self, 'pathway', None)
            
            # If log has a pathway and it doesn't match → reject
            if current_log_path and current_log_path != pathway:
                return False
            
            # If log has no pathway:
            # - Speeches must belong to the selected pathway → reject
            # - Roles are generic → accept
            if not current_log_path and log_type == 'speech':
                return False
        
        # Status filter
        if status:
            if log_type == 'speech':
                if self.Status != status:
                    return False
            else:  # role
                # For roles, only show if linked to project AND status matches
                if not (self.Project_ID and self.Status == status):
                    return False
        
        return True

    @classmethod
    def set_owners(cls, target_log, new_owner_ids):
        """
        Sets the owners for a session log (and related logs if role is not distinct),
        updates credentials, and derives project codes.
        
        This method DOES NOT sync with Roster or clear Waitlists. 
        Those side effects are managed by RoleService.
        
        Args:
            target_log: The SessionLog object to update
            new_owner_ids: List of IDs of the new owners (or empty list/None to unassign)
            
        Returns:
            list: List of updated SessionLog objects
        """
        from .roster import MeetingRole
        from .contact import Contact
        from .project import Pathway, PathwayProject
        from ..utils import derive_credentials
        from .session import OwnerMeetingRoles
        
        if new_owner_ids is None:
            new_owner_ids = []
        if isinstance(new_owner_ids, int):
            new_owner_ids = [new_owner_ids]
            
        # 1. Identify all logs to update (for recalculating metadata)
        session_type = target_log.session_type
        if not session_type and target_log.Type_ID:
             session_type = db.session.get(SessionType, target_log.Type_ID)
             
        role_obj = session_type.role if session_type else None
        
        sessions_to_update = [target_log]
        
        has_single_owner = role_obj.has_single_owner if role_obj else True
        
        if role_obj and not has_single_owner:
            # Find all logs for this role in this meeting
            target_role_id = role_obj.id
            
            # For shared roles, ALL logs of this role in the meeting are updated
            query = db.session.query(cls)\
                .join(SessionType, cls.Type_ID == SessionType.id)\
                .filter(cls.Meeting_Number == target_log.Meeting_Number)\
                .filter(SessionType.role_id == target_role_id)
                
            sessions_to_update = query.all()
            if target_log not in sessions_to_update:
                sessions_to_update.append(target_log)

        # 2. Update OwnerMeetingRoles (The Source of Truth)
        # Identify scope - handle case where meeting relationship might not be loaded
        meeting_id = None
        if target_log.meeting:
            meeting_id = target_log.meeting.id
        
        if not meeting_id:
            # Fallback if meeting relationship not loaded or obj new
            from .meeting import Meeting
            m = Meeting.query.filter_by(Meeting_Number=target_log.Meeting_Number).first()
            meeting_id = m.id if m else None
        
        if meeting_id:
            # Determine Role ID and Single Owner Status
            # Default to 0 and Single Owner if no role associated
            target_role_id = 0
            is_single_owner = True
            
            if role_obj:
                target_role_id = role_obj.id
                is_single_owner = has_single_owner
            
            # Determine Deletion Criteria
            delete_query = OwnerMeetingRoles.query.filter(
                OwnerMeetingRoles.meeting_id == meeting_id,
                OwnerMeetingRoles.role_id == target_role_id
            )
            
            if is_single_owner:
                delete_query = delete_query.filter(OwnerMeetingRoles.session_log_id == target_log.id)
            else:
                delete_query = delete_query.filter(OwnerMeetingRoles.session_log_id == None)
                
            delete_query.delete(synchronize_session=False)
            
            # Insertion
            if new_owner_ids:
                # Deduplicate owner_ids
                unique_owner_ids = list(dict.fromkeys(new_owner_ids))
                
                # Verify contacts exist? (Optional, DB FK enforces it, but cleaner to filter)
                # We fetch them anyway later.
                pass 
                
                for cid in unique_owner_ids:
                    new_omr = OwnerMeetingRoles(
                        meeting_id=meeting_id,
                        role_id=target_role_id,
                        contact_id=cid,
                        session_log_id=target_log.id if is_single_owner else None
                    )
                    db.session.add(new_omr)

        # 3. Prepare Data for Metadata Updates (Credentials, Project Code)
        # Fetch all owner contacts
        owner_contacts = []
        if new_owner_ids:
            # Preserve order of IDs if possible, or just fetch all
            owner_contacts = Contact.query.filter(Contact.id.in_(new_owner_ids)).all()
            # Sort contacts to match input ID order
            owner_contacts.sort(key=lambda c: new_owner_ids.index(c.id))

        primary_owner = owner_contacts[0] if owner_contacts else None
        
        # 4. Update Logs Metadata
        for log in sessions_to_update:
            # Note: log.owners is now a property, so we don't set it.
            # We updated the DB table `owner_meeting_roles` above, so `log.owners` will return new values.
            
            # Project Code Logic (Based on Primary Owner)
            new_path_level = None
            if primary_owner:
                # Basic derivation
                new_path_level = log.derive_project_code(primary_owner)
                
                # Auto-Resolution from Next_Project for Prepared Speeches
                if primary_owner.Next_Project and log.Type_ID == SessionTypeID.PREPARED_SPEECH:
                    current_path_name = primary_owner.Current_Path
                    if current_path_name:
                        pathway = Pathway.query.filter_by(name=current_path_name).first()
                        if pathway and pathway.abbr:
                            if primary_owner.Next_Project.startswith(pathway.abbr):
                                code_suffix = primary_owner.Next_Project[len(pathway.abbr):]
                                pp = PathwayProject.query.filter_by(
                                    path_id=pathway.id,
                                    code=code_suffix
                                ).first()
                                if pp:
                                    log.Project_ID = pp.project_id
                                    new_path_level = primary_owner.Next_Project
            
            log.project_code = new_path_level

        return sessions_to_update

    @classmethod
    def fetch_for_meeting(cls, selected_meeting_number, meeting_obj=None):
        """
        Fetches session logs for a given meeting, filtering by user role access where appropriate.
        
        Args:
            selected_meeting_number: Meeting number to fetch logs for
            meeting_obj: Optional meeting object for authorization check
        
        Returns:
            list: Session logs with eager-loaded relationships
        """
        from ..auth.permissions import Permissions
        from ..auth.utils import is_authorized
        from .roster import Waitlist, MeetingRole
        
        query = db.session.query(cls)\
            .options(
                joinedload(cls.meeting),
                joinedload(cls.session_type).joinedload(SessionType.role),
                # joinedload(cls.owners) Removed as it is now a property
                # We could attempt to optimize fetching OwnerMeetingRoles here if needed
                subqueryload(cls.waitlists).joinedload(Waitlist.contact)
            )\
            .join(SessionType, cls.Type_ID == SessionType.id)\
            .join(MeetingRole, SessionType.role_id == MeetingRole.id)\
            .filter(cls.Meeting_Number == selected_meeting_number)\
            .filter(MeetingRole.name != '', MeetingRole.name.isnot(None))

        if not is_authorized(Permissions.BOOKING_ASSIGN_ALL, meeting=meeting_obj):
            query = query.filter(MeetingRole.type != 'officer')

        return query.all()

    @classmethod
    def delete_for_meeting(cls, meeting_number):
        """Deletes all session logs for a specific meeting."""
        # Fix: Delete OwnerMeetingRoles first to avoid FK constraint
        from .meeting import Meeting
        m = Meeting.query.filter_by(Meeting_Number=meeting_number).first()
        if m:
             OwnerMeetingRoles.query.filter_by(meeting_id=m.id).delete(synchronize_session=False)

        logs = cls.query.filter_by(Meeting_Number=meeting_number).all()
        for log in logs:
            if log.media:
                db.session.delete(log.media)
            db.session.delete(log)
