from ..base import BaseExportComponent
from ..formatter import ExportFormatter
from app.utils import derive_credentials


class PowerBIAgendaComponent(BaseExportComponent):
    """Renders the Meeting Agenda section for PowerBI."""
    def render(self, ws, context, start_row):
        from app.models.club_rule import ClubRule
        from unittest.mock import Mock
        
        club_id = context.meeting.club_id
        show_end_time = False
        try:
            if club_id and not isinstance(club_id, Mock):
                rule_record = ClubRule.query.filter_by(club_id=club_id, rule_name='session_end_time').first()
                show_end_time = rule_record.is_enabled if rule_record else False
        except Exception:
            pass

        ws.append([])
        ws.append(["2. MEETING AGENDA"])
        ws.append([])
        ws.append(["Meeting Number", "Start Time", "Title", "Duration", "Owner"])
        ExportFormatter.apply_header_style(ws, ws.max_row)
        
        for log, st in context.logs:
            if st.Is_Section or st.Is_Hidden:
                continue
                
            # Title logic
            if st.Title == "Evaluation" and log.Session_Title:
                # Evaluation title: "Evaluation for <speaker>"
                title = f"Evaluation for {log.Session_Title}"
            elif st.Title == "Keynote Speech" and log.Session_Title:
                # Keynote speech: use title as-is without quotes, but strip any existing quotes
                title = log.Session_Title.replace('"', '').replace("'", "")
            elif st.Valid_for_Project and log.id in context.speech_details and log.Session_Title:
                # Speech project title: SR1.2 "My Speech"
                # Remove existing quotes from speech title first, then add quotes
                sd = context.speech_details[log.id]
                if sd and sd['project_code']:
                    clean_title = sd['speech_title'].replace('"', '').replace("'", "")
                    title = f"{sd['project_code']} \"{clean_title}\""
                else:
                    title = log.Session_Title or st.Title
            else:
                # Regular session: use custom title or session type title
                title = log.Session_Title or st.Title
            
            duration = ""
            if log.Duration_Max is not None:
                if log.Duration_Min is not None and log.Duration_Min > 0 and log.Duration_Min != log.Duration_Max:
                    duration = f"[{log.Duration_Min}'-{log.Duration_Max}']"
                else:
                    duration = f"[{log.Duration_Max}']"
            
            start_time = log.Start_Time.strftime('%H:%M') if log.Start_Time else ""
            time_display = start_time
            if show_end_time and start_time:
                duration_val = int(log.Duration_Max or 0)
                if duration_val > 0:
                    from datetime import datetime, timedelta
                    dummy_dt = datetime.combine(datetime.min.date(), log.Start_Time)
                    end_dt = dummy_dt + timedelta(minutes=duration_val)
                    end_time_str = end_dt.time().strftime('%H:%M')
                    time_display = f"{start_time} - {end_time_str}"
                else:
                    time_display = start_time

            # Owner logic with multiple owners support
            owner_parts = []
            for o in log.owners:
                o_str = o.Name
                if o.DTM:
                    o_str += "ᴰᵀᴹ"
                
                creds = derive_credentials(o)
                if creds and creds != "DTM":
                    o_str += f" - {creds}"
                owner_parts.append(o_str)
            owner = " & ".join(owner_parts)
                
            ws.append([log.Meeting_Number, time_display, title, duration, owner])
            if len(title) > 50:
                ExportFormatter.apply_wrap_text(ws.cell(row=ws.max_row, column=3))
        
        # Auto-fit columns for this component
        ExportFormatter.auto_fit_columns(ws)
        return ws.max_row + 2
