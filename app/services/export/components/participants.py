from ..base import BaseExportComponent
from ..formatter import ExportFormatter


class ParticipantsComponent(BaseExportComponent):
    """Renders the Participants table."""
    def render(self, ws, context, start_row):
        ws.append(['Group', 'Name'])
        ExportFormatter.apply_header_style(ws, ws.max_row)
        
        data = context.participants_dict
        
        for group in ["Prepared Speakers", "Individual Evaluators", "Table Topics Speakers"]:
            for name in data[group]:
                ws.append([group, name])
            if data[group]: ws.append([])
            
        for role, name in data["Role Takers"]:
            ws.append(["Role Takers", f"{role}: {name}"])
        
        # Auto-fit columns for this component
        ExportFormatter.auto_fit_columns(ws)
        return ws.max_row + 1
