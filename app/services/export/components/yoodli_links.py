from ..base import BaseExportComponent
from ..formatter import ExportFormatter
from ....constants import SessionTypeID


class YoodliLinksComponent(BaseExportComponent):
    """Renders the Yoodli Links section for PowerBI."""
    def render(self, ws, context, start_row):
        ws.append([])
        ws.append(["3. YOODLI LINKS"])
        ws.append([])
        ws.append(["Meeting Number", "Speaker", None, None, None, "Speaker Yoodli", "Evaluator", "Evaluator Yoodli"])
        ExportFormatter.apply_header_style(ws, ws.max_row)
        
        # Logic to match speakers with evaluators
        speakers = []
        evaluator_map = {}
        
        for log, st in context.logs:
            if log.Project_ID:
                speakers.append(log)
            if st.id == SessionTypeID.EVALUATION:
                # Evaluation Session_Title contains the speaker's name
                speaker_name = log.Session_Title
                if speaker_name:
                    evaluator_map[speaker_name] = log
                
        for s_log in speakers:
            # Match evaluator by speaker's name
            speaker_name = s_log.owner.Name if s_log.owner else ""
            eval_log = evaluator_map.get(speaker_name)
            
            s_name = speaker_name
            if s_log.owner and s_log.owner.Type == 'Guest': s_name += " (Guest)"
            
            e_name = ""
            e_url = ""
            if eval_log:
                e_name = eval_log.owner.Name if eval_log.owner else ""
                if eval_log.owner and eval_log.owner.Type == 'Guest': e_name += " (Guest)"
                e_url = eval_log.media.url if eval_log.media else ""
            
            ws.append([
                s_log.Meeting_Number,
                s_name,
                None, None, None,
                s_log.media.url if s_log.media else "",
                e_name,
                e_url
            ])
        
        # Auto-fit columns for this component
        ExportFormatter.auto_fit_columns(ws)
        return ws.max_row + 1
