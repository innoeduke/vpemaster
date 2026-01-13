from sqlalchemy import orm
from ...models import db, Meeting, SessionLog, SessionType, Vote, Contact, Pathway
from ...constants import SessionTypeID


class MeetingExportContext:
    """Centralizes data fetching and caching for meeting exports."""
    def __init__(self, meeting_number):
        self.meeting_number = meeting_number
        self._meeting = None
        self._logs = None
        self._votes = None
        self._pathway_mapping = None
        self._speech_details = None
        self._role_map = None

    @property
    def meeting(self):
        if self._meeting is None:
            self._meeting = Meeting.query.options(
                orm.joinedload(Meeting.best_table_topic_speaker),
                orm.joinedload(Meeting.best_evaluator),
                orm.joinedload(Meeting.best_speaker),
                orm.joinedload(Meeting.best_role_taker),
                orm.joinedload(Meeting.media)
            ).filter_by(Meeting_Number=self.meeting_number).first()
        return self._meeting

    @property
    def logs(self):
        if self._logs is None:
            # Replicating _get_export_data logic
            self._logs = db.session.query(SessionLog, SessionType).join(SessionType)\
                .filter(SessionLog.Meeting_Number == self.meeting_number)\
                .order_by(SessionLog.Meeting_Seq).all()
        return self._logs

    @property
    def votes(self):
        if self._votes is None:
            self._votes = Vote.query.options(orm.joinedload(Vote.contact))\
                .filter_by(meeting_number=self.meeting_number).all()
        return self._votes

    @property
    def pathway_mapping(self):
        if self._pathway_mapping is None:
            all_pathways = Pathway.query.filter_by(status='active').order_by(Pathway.name).all()
            self._pathway_mapping = {p.name: p.abbr for p in all_pathways}
        return self._pathway_mapping

    @property
    def speech_details(self):
        if self._speech_details is None:
            # Replicating _get_all_speech_details logic
            self._speech_details = {}
            for log, st in self.logs:
                if st.Valid_for_Project:
                    details = self._get_speech_details(log)
                    self._speech_details[log.id] = details
        return self._speech_details

    def _get_speech_details(self, log):
        """Helper to get speech details for a single log."""
        if not log or not log.project:
            return None
        
        # Resolve the PathwayProject and Pathway objects for this log
        # log.pathway contains the pathway name string
        pp, pathway_obj = log.project.resolve_context(log.pathway)
        
        # Use the existing get_code method which returns the full code like "SR1.2"
        project_code = log.project.get_code(log.pathway)
        
        return {
            'project_code': project_code,
            'pathway_name': pathway_obj.name if pathway_obj else "",
            'project_name': log.project.Project_Name,
            'project_type': pp.type if pp else "other",  # required/elective/other
            'project_purpose': log.project.Purpose or "",
            'duration_min': log.project.Duration_Min,
            'duration_max': log.project.Duration_Max,
            'speech_title': log.Session_Title or ""
        }

    @property
    def role_map(self):
        if self._role_map is None:
            self._role_map = {}
            for log, st in self.logs:
                if log.Owner_ID:
                    role_name = st.Title
                    if st.role:
                        role_name = st.role.name
                    self._role_map[log.Owner_ID] = role_name
        return self._role_map

    @property
    def participants_dict(self):
        """Extracts participant data for Sheet 4 and Tally Sync."""
        # Grouped logic
        groups = {
            "Prepared Speakers": set(),
            "Individual Evaluators": set(),
            "Table Topics Speakers": set(),
            "Role Takers": set()
        }
        
        speaker_types = {SessionTypeID.KEYNOTE_SPEECH, SessionTypeID.PREPARED_SPEECH, SessionTypeID.PRESENTATION, SessionTypeID.PANEL_DISCUSSION}
        
        for log, st in self.logs:
            if not log.owner or not log.owner.Name: continue
            
            name = log.owner.Name.strip()
            # Don't add (Guest) suffix for participants board
            
            if st.id in speaker_types:
                groups["Prepared Speakers"].add(name)
            elif st.id == SessionTypeID.EVALUATION:
                groups["Individual Evaluators"].add(name)
            elif st.id == SessionTypeID.TOPICS_SPEECH:
                groups["Table Topics Speakers"].add(name)
            elif not st.Is_Section and not st.Is_Hidden:
                if st.role and st.role.type == 'officer': continue
                # Use role.name for role name, not session type title
                role_name = st.role.name if st.role else st.Title
                if role_name:
                    groups["Role Takers"].add((role_name.strip(), name))

        return {
            "Prepared Speakers": sorted(list(groups["Prepared Speakers"])),
            "Individual Evaluators": sorted(list(groups["Individual Evaluators"])),
            "Table Topics Speakers": sorted(list(groups["Table Topics Speakers"])),
            "Role Takers": sorted(list(groups["Role Takers"]), key=lambda x: (x[0], x[1]))
        }
