from ..base import BaseExportComponent
from ..formatter import ExportFormatter
from app.constants import SessionTypeID


class PowerBIAgendaComponent(BaseExportComponent):
    """Renders the Meeting Agenda section for PowerBI."""
    def render(self, ws, context, start_row):
        ws.append([])
        ws.append(["2. MEETING AGENDA"])
        ws.append([])
        ws.append(["Meeting Number", "Start Time", "Title", "Duration", "Owner"])
        ExportFormatter.apply_header_style(ws, ws.max_row)
        
        for log, st in context.logs:
            if st.Is_Section or st.Is_Hidden:
                continue
                
            # Title logic
            if st.id == SessionTypeID.EVALUATION and log.Session_Title:
                # Evaluation title: "Evaluation for <speaker>"
                title = f"Evaluation for {log.Session_Title}"
            elif st.id == SessionTypeID.KEYNOTE_SPEECH and log.Session_Title:
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
            
            # Owner logic with credentials and DTM
            owner = ""
            if log.owner:
                owner = log.owner.Name
                
                # Add DTM superscript
                if log.owner.DTM:
                    owner += "ᴰᵀᴹ"
                
                # For DTM members, don't add credentials
                # For guests, credential is "Guest"
                # For others, use log.credentials
                if not log.owner.DTM:
                    if log.owner.Type == 'Guest':
                        owner += " - Guest"
                    elif log.credentials:
                        owner += f" - {log.credentials}"
                
            ws.append([log.Meeting_Number, log.Start_Time.strftime('%H:%M') if log.Start_Time else "", title, duration, owner])
            if len(title) > 50:
                ExportFormatter.apply_wrap_text(ws.cell(row=ws.max_row, column=3))
        
        # Auto-fit columns for this component
        ExportFormatter.auto_fit_columns(ws)
        return ws.max_row + 2
