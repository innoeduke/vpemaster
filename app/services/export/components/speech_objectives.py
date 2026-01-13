from ..base import BaseExportComponent
from ..formatter import ExportFormatter
import re


class SpeechObjectivesComponent(BaseExportComponent):
    """Renders project objectives for project speeches."""
    def render(self, ws, context, start_row):
        # Component title
        ws.append([])
        ws.append(["PROJECT OBJECTIVES"])
        ExportFormatter.apply_header_style(ws, ws.max_row)
        ws.append([])
        
        # Collect all objectives with their project codes for sorting
        objectives_list = []
        
        for log, st in context.logs:
            # Skip hidden sessions
            if st.Is_Hidden:
                continue
            
            # Only include project speeches with objectives
            if not (st.Valid_for_Project and log.project):
                continue
            
            if log.id not in context.speech_details:
                continue
            
            sd = context.speech_details[log.id]
            if not sd or not sd['project_purpose']:
                continue
            
            # Project type capitalized
            project_type = sd['project_type'].capitalize() if sd['project_type'] else "Other"
            
            # Duration
            duration = ""
            if sd['duration_max']:
                if sd['duration_min'] and sd['duration_min'] > 0 and sd['duration_min'] != sd['duration_max']:
                    duration = f"[{sd['duration_min']}'-{sd['duration_max']}']"
                else:
                    duration = f"[{sd['duration_max']}']"
            
            # First line: <pathway> (<project-code>) <project-title> (Required/Elective) <duration>
            first_line = f"{sd['pathway_name']} ({sd['project_code']}) {sd['project_name']} ({project_type}) {duration}"
            
            # Add to list with sort key
            objectives_list.append({
                'project_code': sd['project_code'],
                'first_line': first_line,
                'purpose': sd['project_purpose']
            })
        
        # Sort objectives by project code
        # Pathway projects (e.g., SR1.2) come before presentations (e.g., PS001)
        def sort_key(obj):
            code = obj['project_code']
            # Check if it's a presentation (all digits after abbreviation)
            # Pathway: SR1.2 (has dots), Presentation: PS001 (no dots)
            if '.' in code:
                # Pathway project: extract numeric part for sorting
                # SR1.2 -> extract "1.2" and convert to sortable format
                match = re.search(r'(\d+)\.(\d+)(?:\.(\d+))?', code)
                if match:
                    level = int(match.group(1))
                    project = int(match.group(2))
                    subproject = int(match.group(3)) if match.group(3) else 0
                    # Sort pathway projects first (0), then by level, project, subproject
                    return (0, level, project, subproject, code)
            # Presentation: sort after all pathway projects
            return (1, 0, 0, 0, code)
        
        objectives_list.sort(key=sort_key)
        
        # Render sorted objectives
        for obj in objectives_list:
            ws.append([obj['first_line']])
            ws.append([obj['purpose']])
            ws.append([])  # Blank line between objectives
        
        # Single-column component - don't auto-fit to avoid interfering with other components
        return ws.max_row + 2  # Add 2 blank lines spacing
