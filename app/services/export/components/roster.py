from sqlalchemy import orm
from ..base import BaseExportComponent
from ..formatter import ExportFormatter
from ....models import Roster


class RosterComponent(BaseExportComponent):
    """Renders the Roster table."""
    def render(self, ws, context, start_row):
        headers = ["Order", "Name", "Ticket"]
        ws.append(headers)
        ExportFormatter.apply_header_style(ws, ws.max_row)
        
        roster_entries = Roster.query.options(orm.joinedload(Roster.contact), orm.joinedload(Roster.ticket)).filter_by(
            meeting_id=context.meeting_id).order_by(Roster.order_number).all()
            
        for entry in roster_entries:
            ws.append([
                entry.order_number,
                entry.contact.Name if entry.contact else '',
                entry.ticket.name if entry.ticket else ''
            ])
        
        # Auto-fit columns for this component
        ExportFormatter.auto_fit_columns(ws)
        return ws.max_row + 1
