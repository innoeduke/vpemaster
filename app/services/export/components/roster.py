from sqlalchemy import orm
from ..base import BaseExportComponent
from ..formatter import ExportFormatter
from ....models import Roster


class RosterComponent(BaseExportComponent):
    """Renders the Roster table."""
    def render(self, ws, context, start_row):
        headers = ["Order", "Name", "Ticket (Type)"]
        ws.append(headers)
        ExportFormatter.apply_header_style(ws, ws.max_row)
        
        roster_entries = Roster.query.options(orm.joinedload(Roster.contact)).filter_by(
            meeting_number=context.meeting_number).order_by(Roster.order_number).all()
            
        for entry in roster_entries:
            ws.append([
                entry.order_number,
                entry.contact.Name if entry.contact else '',
                f"{entry.ticket} ({entry.contact.Type})"
            ])
        
        # Auto-fit columns for this component
        ExportFormatter.auto_fit_columns(ws)
        return ws.max_row + 1
