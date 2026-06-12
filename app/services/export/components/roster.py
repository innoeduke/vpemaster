from sqlalchemy import orm
from ..base import BaseExportComponent
from ..formatter import ExportFormatter
from ....models import Roster
from ....translations.translations import translate as _


class RosterComponent(BaseExportComponent):
    """Renders the Roster table."""
    def render(self, ws, context, start_row):
        headers = [_("Name"), _("Ticket"), _("Ticket Price"), _("Roles"), _("Qty")]
        ws.append(headers)
        ExportFormatter.apply_header_style(ws, ws.max_row)
        
        Roster.convert_expired_early_birds(context.meeting_id)
        
        roster_entries = Roster.query.options(
            orm.joinedload(Roster.contact),
            orm.joinedload(Roster.ticket),
            orm.joinedload(Roster.roles)
        ).filter_by(meeting_id=context.meeting_id).all()
        
        def get_sort_key(entry):
            is_officer = bool(entry.ticket and entry.ticket.name == 'Officer')
            is_paid = bool(not is_officer and entry.order_number is not None)
            if is_paid:
                group_num = 0
            elif not is_officer:
                group_num = 1
            else:
                group_num = 2
            name = entry.contact.Name if entry.contact else ""
            return (group_num, name.lower())
            
        roster_entries.sort(key=get_sort_key)
            
        for entry in roster_entries:
            price = entry.ticket.price if entry.ticket else ""
            roles_str = ", ".join(entry.get_role_names())
            qty = entry.quantity or 1
            
            ws.append([
                entry.contact.Name if entry.contact else '',
                entry.ticket.name if entry.ticket else '',
                price,
                roles_str,
                qty
            ])
        
        # Auto-fit columns for this component
        ExportFormatter.auto_fit_columns(ws)
        return ws.max_row + 1
