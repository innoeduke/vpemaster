import io
import openpyxl
from .context import MeetingExportContext
from .factory import ExportFactory


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
