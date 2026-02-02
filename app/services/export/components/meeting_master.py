from ..base import BaseExportComponent
from ..formatter import ExportFormatter


class MeetingMasterComponent(BaseExportComponent):
    """Renders the Meeting Master section for PowerBI."""
    def render(self, ws, context, start_row):
        ws.append([])
        ws.append(["1. MEETING MASTER"])
        ws.append([])
        headers = [
            "Excomm", "Meeting Date", "Meeting Number", "Meeting Title",
            "Keynote Speaker", "Meeting Video Url", "Word of the Day",
            "Best Topic Speaker", "Best Role Taker", "Best Speaker", "Best Evaluator"
        ]
        ws.append(headers)
        ExportFormatter.apply_header_style(ws, ws.max_row)
        
        # Get ExComm info from database
        excomm_string = ''
        meeting = context.meeting
        excomm = meeting.get_excomm()
        if excomm:
            excomm_string = f'{excomm.excomm_term} "{excomm.excomm_name}"'.strip()
        
        # Find keynote speaker from session logs
        keynote_speaker = ""
        for log, st in context.logs:
            if st.Title == "Keynote Speech" and log.owner:
                keynote_speaker = log.owner.Name
                break
        
        meeting = context.meeting
        row_data = [
            excomm_string,
            meeting.Meeting_Date.strftime('%Y/%m/%d'),
            meeting.Meeting_Number,
            meeting.Meeting_Title,
            keynote_speaker,
            meeting.media.url if meeting.media else "",
            meeting.WOD if meeting.WOD else "",
            meeting.best_table_topic_speaker.Name if meeting.best_table_topic_speaker else "",
            meeting.best_role_taker.Name if meeting.best_role_taker else "",
            meeting.best_speaker.Name if meeting.best_speaker else "",
            meeting.best_evaluator.Name if meeting.best_evaluator else ""
        ]
        ws.append(row_data)
        
        # Auto-fit columns for this component
        ExportFormatter.auto_fit_columns(ws)
        return ws.max_row + 2
