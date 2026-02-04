from ..base import BaseExportComponent
from ..formatter import ExportFormatter
from app.utils import derive_credentials


class AgendaComponent(BaseExportComponent):
    """Renders the main agenda table."""
    def render(self, ws, context, start_row):
        # Component title
        ws.append(["AGENDA"])
        ExportFormatter.apply_header_style(ws, ws.max_row)
        ws.append([])
        
        # Headers
        headers = ["Start", "Title", "Owner", "Duration"]
        ws.append(headers)
        ExportFormatter.apply_header_style(ws, ws.max_row)
        
        for log, st in context.logs:
            # Skip hidden sessions
            is_hidden = log.hidden if log.hidden is not None else st.Is_Hidden
            if is_hidden:
                continue
            
            # Add blank line before section sessions
            if st.Is_Section:
                ws.append([])
            
            # Replicating _format_export_row logic
            start_time = log.Start_Time.strftime('%H:%M') if log.Start_Time else ""
            
            # Duration logic
            duration = ""
            if log.Duration_Max is not None:
                if log.Duration_Min is not None and log.Duration_Min > 0 and log.Duration_Min != log.Duration_Max:
                    duration = f"{log.Duration_Min}'-{log.Duration_Max}'"
                else:
                    duration = f"{log.Duration_Max}'"
            
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
            
            # Owner logic with multiple owners support
            owner_parts = []
            for o in log.owners:
                o_str = o.Name
                if o.DTM:
                    o_str += "ᴰᵀᴹ"
                else:
                    creds = derive_credentials(o)
                    if creds:
                        o_str += f" - {creds}"
                owner_parts.append(o_str)
            owner = " & ".join(owner_parts)
            
            ws.append([start_time, title, owner, duration])
            
            # Formatting title cells if too long
            if len(title) > 50:
                ExportFormatter.apply_wrap_text(ws.cell(row=ws.max_row, column=2))
        
        # Auto-fit columns for this component
        ExportFormatter.auto_fit_columns(ws)
        return ws.max_row + 3  # Add 2 blank lines spacing
