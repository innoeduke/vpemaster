from ..base import BaseExportComponent
from ..formatter import ExportFormatter


class VotesComponent(BaseExportComponent):
    """Renders the Votes table."""
    def render(self, ws, context, start_row):
        headers = ['Best Speaker', 'Best Evaluator', 'Best Table Topic', 'Best Role Taker', 'NPS', 'Feedback']
        ws.append(headers)
        ExportFormatter.apply_header_style(ws, ws.max_row)
        
        voter_data = {}
        NS_QUESTION = "How likely are you to recommend this meeting to a friend or colleague?"
        FEEDBACK_QUESTION = "More feedback/comments"
        
        for v in context.votes:
            if v.voter_identifier not in voter_data:
                voter_data[v.voter_identifier] = {}
            
            if v.award_category:
                contact_name = v.contact.Name if v.contact else ""
                if v.award_category == 'role-taker' and v.contact_id in context.role_map:
                    voter_data[v.voter_identifier][v.award_category] = f"{context.role_map[v.contact_id]}: {contact_name}"
                else:
                    voter_data[v.voter_identifier][v.award_category] = contact_name
            elif v.question == NS_QUESTION:
                voter_data[v.voter_identifier]['nps'] = v.score
            elif v.question == FEEDBACK_QUESTION:
                voter_data[v.voter_identifier]['feedback'] = v.comments
                
        for voter_id, data in voter_data.items():
            row = [
                data.get('speaker', ''),
                data.get('evaluator', ''),
                data.get('table-topic', ''),
                data.get('role-taker', ''),
                data.get('nps', ''),
                data.get('feedback', '')
            ]
            ws.append(row)
            if data.get('feedback'):
                ExportFormatter.apply_wrap_text(ws.cell(row=ws.max_row, column=6))
        
        ws.column_dimensions['F'].width = 40
        
        # Auto-fit columns for this component
        ExportFormatter.auto_fit_columns(ws)
        return ws.max_row + 1
