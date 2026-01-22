import io
import os
import openpyxl
from flask import current_app
from pptx import Presentation
from .context import MeetingExportContext
from .factory import ExportFactory
from ...utils import derive_credentials
from ...models import ExComm


class MeetingExportService:
    """Primary service to generate meeting Excel exports."""
    @staticmethod
    def generate_meeting_xlsx(meeting_number):
        context = MeetingExportContext(meeting_number)
        if not context.meeting:
            return None
            
        wb = openpyxl.Workbook()
        # Remove default sheet
        default_ws = wb.active
        
        boards = ExportFactory.get_meeting_boards()
        
        for i, board in enumerate(boards):
            if i == 0:
                ws = default_ws
            else:
                ws = wb.create_sheet()
            board.render(ws, context)
            
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return output

    @staticmethod
    def _initialize_placeholders(meeting):
        """Initialize all PPTX placeholders with empty values."""
        replacements = {
            "{{meeting_number}}": str(meeting.Meeting_Number),
            "{{meeting_date}}": meeting.Meeting_Date.strftime('%d-%b-%Y') if meeting.Meeting_Date else "",
            "{{club_name}}": (meeting.club.club_name if meeting.club else ""),
        }
        
        # Role placeholders (info + duration)
        for p in ["saa", "welcome-officer", "president", "vpm", "vpe", "vppr", "treasurer", "secretary", 
                  "tme", "timer", "ah-counter", "grammarian", "topicsmaster", "ge"]:
            replacements["{{" + p + "_info}}"] = ""
            replacements["{{" + p + "_duration}}"] = ""
        
        # Speaker placeholders (up to 6)
        for i in range(1, 7):
            replacements.update({
                f"{{{{ps{i}}}}}": "", f"{{{{ps{i}_title}}}}": "", 
                f"{{{{ps{i}-project_info}}}}": "", f"{{{{ps{i}_info}}}}": "", 
                f"{{{{ps{i}_duration}}}}": ""
            })
        
        # Evaluator placeholders (up to 6)
        for i in range(1, 7):
            replacements.update({
                f"{{{{ie{i}_info}}}}": "", f"{{{{ie{i}_duration}}}}": ""
            })
        
        # Featured session and table topics
        replacements.update({
            "{{keynote_title}}": "", "{{keynote_duration}}": "", "{{keynote-speaker_info}}": "",
            "{{table-topics_duration}}": ""
        })
        
        return replacements

    @staticmethod
    def _populate_standard_roles(context, meeting, replacements, info_fmt, dur_fmt):
        """Populate standard role information from meeting logs and ExComm."""
        import re
        
        def populate_role(role_pattern=None, title_pattern=None, info_key=None, dur_key=None):
            last_match = None
            for log, st in context.logs:
                if not log.owner: continue
                role_name = (st.role.name if st.role else st.Title)
                if (role_pattern and role_name and re.search(role_pattern, role_name, re.I)) or \
                   (title_pattern and log.Session_Title and re.search(title_pattern, log.Session_Title, re.I)):
                    last_match = (log, st)
            
            if last_match:
                log, st = last_match
                if info_key: replacements[info_key] = info_fmt(log.owner.Name, derive_credentials(log.owner))
                if dur_key: replacements[dur_key] = dur_fmt(log)
                return True
            return False
        
        # Populate from meeting logs
        roles_config = [
            ("saa", None, "SAA Introduction"), ("president", None, "President's Address"),
            ("welcome-officer", "Welcome Officer", None), ("tme", "Toastmaster", None),
            ("timer", "Timer", None), ("ah-counter", "Ah-Counter", None),
            ("grammarian", "Grammarian", None), ("topicsmaster", "Topicsmaster", None),
            ("ge", "General Evaluator", None)
        ]
        for prefix, role_p, title_p in roles_config:
            populate_role(role_p, title_p, "{{" + prefix + "_info}}", "{{" + prefix + "_duration}}")
        
        # Fallback to ExComm for missing info
        excomm = meeting.club.current_excomm if meeting.club else None
        if not excomm:
            excomm = ExComm.query.filter_by(club_id=meeting.club_id).order_by(ExComm.id.desc()).first()
        if excomm:
            officers = excomm.get_officers()
            role_to_prefix = {
                "President": "president", "VPE": "vpe", "VPM": "vpm", "VPPR": "vppr",
                "Secretary": "secretary", "Treasurer": "treasurer", "SAA": "saa",
                "Welcome Officer": "welcome-officer"
            }
            for role_name, contact in officers.items():
                prefix = role_to_prefix.get(role_name)
                key = "{{" + prefix + "_info}}" if prefix else None
                if prefix and contact and key and not replacements.get(key):
                    replacements[key] = info_fmt(contact.Name, derive_credentials(contact))

    @staticmethod
    def _populate_speakers(context, replacements, info_fmt, dur_fmt):
        """Populate prepared speaker information (up to 6 speakers)."""
        speakers = [(log, st) for log, st in context.logs if (st.role and st.role.name == "Prepared Speaker" and log.owner)]
        for i, (log, st) in enumerate(speakers[:6], 1):
            replacements[f"{{{{ps{i}}}}}"] = log.owner.Name
            replacements[f"{{{{ps{i}_info}}}}"] = info_fmt(log.owner.Name, derive_credentials(log.owner))
            replacements[f"{{{{ps{i}_duration}}}}"] = dur_fmt(log)
            
            details = context.speech_details.get(log.id)
            if details:
                replacements[f"{{{{ps{i}_title}}}}"] = details['speech_title'] or details['project_name'] or ""
                replacements[f"{{{{ps{i}-project_info}}}}"] = f"{details['project_code']} - {details['project_name']}" if details['project_code'] and details['project_name'] else (details['project_name'] or "")
            else:
                replacements[f"{{{{ps{i}_title}}}}"] = log.Session_Title or ""

    @staticmethod
    def _populate_evaluators(context, replacements, info_fmt, dur_fmt):
        """Populate individual evaluator information (up to 6 evaluators)."""
        evaluators = [(log, st) for log, st in context.logs if (st.role and st.role.name == "Individual Evaluator" and log.owner)]
        for i, (log, st) in enumerate(evaluators[:6], 1):
            replacements[f"{{{{ie{i}_info}}}}"] = info_fmt(log.owner.Name, derive_credentials(log.owner))
            replacements[f"{{{{ie{i}_duration}}}}"] = dur_fmt(log)

    @staticmethod
    def _populate_featured_session(context, meeting, replacements, info_fmt, dur_fmt):
        """Populate keynote/featured session based on meeting type."""
        featured = None
        m_type = (meeting.type or "").strip().lower()
        
        # Priority 1: Match by meeting type
        for l, s in context.logs:
            if m_type and ((s.Title and s.Title.strip().lower() == m_type) or 
                          (l.Session_Title and l.Session_Title.strip().lower() == m_type)):
                featured = (l, s)
                break
        
        # Priority 2: Standard keynote role
        if not featured:
            featured = next(((l, s) for l, s in context.logs if s.role and s.role.name == "Keynote Speaker"), None)
        
        # Priority 3: Moderator or presenter roles
        if not featured:
            featured = next(((l, s) for l, s in context.logs if s.role and s.role.name in ["Moderator", "Workshop Presenter", "Moderator-Host"]), None)
        
        if featured:
            replacements["{{keynote_title}}"] = featured[0].Session_Title or meeting.type or "Featured Session"
            replacements["{{keynote_duration}}"] = dur_fmt(featured[0])
            if featured[0].owner:
                replacements["{{keynote-speaker_info}}"] = info_fmt(featured[0].owner.Name, derive_credentials(featured[0].owner))
        else:
            replacements["{{keynote_title}}"] = meeting.type or ""

    @staticmethod
    def _populate_table_topics(context, replacements, dur_fmt):
        """Populate table topics duration."""
        tt = next(((l, s) for l, s in context.logs if (s.Title == "Table Topics" or (s.role and s.role.name == "Topicsmaster"))), (None, None))
        if tt[0]:
            replacements["{{table-topics_duration}}"] = dur_fmt(tt[0])

    @staticmethod
    def _perform_replacements(prs, replacements):
        """Apply all placeholder replacements to PowerPoint presentation."""
        import re
        
        def robust_replace(text):
            # Fix spacing for "Evaluator for"
            text = re.sub(r'Evaluator\s*for', 'Evaluator for', text, flags=re.I)
            text = re.sub(r'INDIVIDUAL EVALUATOR\s*for', 'INDIVIDUAL EVALUATOR for', text, flags=re.I)
            # Replace all placeholders
            for key, val in replacements.items():
                if key in text:
                    text = text.replace(key, str(val))
            return text
        
        for slide in prs.slides:
            for shape in slide.shapes:
                if not shape.has_text_frame:
                    continue
                for paragraph in shape.text_frame.paragraphs:
                    full_text = "".join(run.text for run in paragraph.runs)
                    updated_text = robust_replace(full_text)
                    if updated_text != full_text:
                        if paragraph.runs:
                            paragraph.runs[0].text = updated_text
                            for i in range(1, len(paragraph.runs)):
                                paragraph.runs[i].text = ""
                        else:
                            paragraph.text = updated_text

    @staticmethod
    def generate_meeting_pptx(meeting_number):
        """Generate PowerPoint presentation for a meeting."""
        context = MeetingExportContext(meeting_number)
        meeting = context.meeting
        if not meeting:
            return None

        # Define formatting helpers
        def info_fmt(name, creds):
            if not name: return ""
            return f"{name}, {creds}" if creds else name

        def dur_fmt(log):
            if not log: return ""
            dmin, dmax = log.Duration_Min, log.Duration_Max
            if dmin is not None and dmax is not None:
                return f"{dmin} ~ {dmax} '"
            val = dmax if dmax is not None else dmin
            return f"{val} '" if val is not None else ""

        # Initialize and populate all placeholders
        replacements = MeetingExportService._initialize_placeholders(meeting)
        MeetingExportService._populate_standard_roles(context, meeting, replacements, info_fmt, dur_fmt)
        MeetingExportService._populate_speakers(context, replacements, info_fmt, dur_fmt)
        MeetingExportService._populate_evaluators(context, replacements, info_fmt, dur_fmt)
        MeetingExportService._populate_featured_session(context, meeting, replacements, info_fmt, dur_fmt)
        MeetingExportService._populate_table_topics(context, replacements, dur_fmt)

        # Load template and perform replacements
        template_path = os.path.join(current_app.instance_path, 'SHLTMC_Meeting_<nnn>.pptx')
        if not os.path.exists(template_path):
            current_app.logger.error(f"PPTX Template not found at: {template_path}")
            return None

        try:
            prs = Presentation(template_path)
            MeetingExportService._perform_replacements(prs, replacements)
            
            output = io.BytesIO()
            prs.save(output)
            output.seek(0)
            return output

        except Exception as e:
            import traceback
            current_app.logger.error(f"Error generating PPTX: {e}\n{traceback.format_exc()}")
            return None
