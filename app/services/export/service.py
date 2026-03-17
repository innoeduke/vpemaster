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
    def generate_meeting_xlsx(meeting_id):
        context = MeetingExportContext(meeting_id)
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

