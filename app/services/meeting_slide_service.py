import io
import os
import re
import copy
import traceback
import math
from flask import current_app
from pptx import Presentation
from pptx.oxml.xmlchemy import OxmlElement
from pptx.util import Inches, Pt, Cm
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor
from PIL import Image

from .export.context import MeetingExportContext
from ..utils import derive_credentials

class MeetingSlideService:
    """Service to generate meeting PowerPoint slides."""

    @staticmethod
    def add_event_template_slide(club_id, slide_title, host, extra_contacts, duration_info, event_type=None, slide_number=None):
        """
        Add a template slide for a specific event to the slides-template.pptx of a specified club.
        :param host: dict with 'name', 'credential', 'role', 'avatar-url'
        :param extra_contacts: list of dicts with 'name', 'credential', 'role', 'avatar-url'
        :param slide_number: optional 1-indexed position to move the slide to
        """
        template_path = os.path.join(current_app.static_folder, 'club_resources', str(club_id), 'slides_template.pptx')
        if not os.path.exists(template_path):
            current_app.logger.error(f"PPTX Template not found at: {template_path}")
            return False

        try:
            prs = Presentation(template_path)
            
            # Use Layout 5 "Title Only" to preserve footer
            layout = None
            for l in prs.slide_layouts:
                if l.name == "Title Only":
                    layout = l
                    break
            if not layout:
                layout = prs.slide_layouts[0] # Fallback
            
            slide = prs.slides.add_slide(layout)
            
            # Move slide if slide_number is provided
            if slide_number is not None and isinstance(slide_number, int):
                # 1-indexed to 0-indexed
                target_idx = max(0, min(slide_number - 1, len(prs.slides) - 1))
                # Internal move logic
                xml_slides = prs.slides._sldIdLst
                slide_id = xml_slides[-1]
                xml_slides.remove(slide_id)
                xml_slides.insert(target_idx, slide_id)

            # 1. Set Title (Capitalized, Centered, Gotham, 54px/40.5pt)
            title_shape = slide.shapes.title
            if title_shape:
                title_shape.text = slide_title.upper() if slide_title else ""
                if title_shape.has_text_frame:
                    tf = title_shape.text_frame
                    p = tf.paragraphs[0]
                    p.alignment = PP_ALIGN.CENTER
                    if p.runs:
                        run = p.runs[0]
                        run.font.name = "Gotham"
                        run.font.size = Pt(40.5) # 54px * 0.75
                        # Set color to #F2DF74
                        run.font.color.rgb = RGBColor.from_string('F2DF74')
            
            font_name = "Gotham"
            maroon_color = RGBColor(119, 36, 50) # Toastmasters Maroon
            tm_red = RGBColor(228, 31, 53) # Toastmasters Red

            # 2. Duration with Background (Top-left 1cm, 1cm)
            dur_left = Cm(1.0)
            dur_top = Cm(1.0)
            dur_width = Cm(4.23)
            dur_height = Cm(1.16)
            
            bg_rect = slide.shapes.add_shape(5, dur_left, dur_top, dur_width, dur_height)
            bg_rect.fill.solid()
            bg_rect.fill.fore_color.rgb = tm_red
            bg_rect.line.width = 0
            
            dur_box = slide.shapes.add_textbox(dur_left, dur_top, dur_width, dur_height)
            tf = dur_box.text_frame
            tf.text = duration_info if duration_info and "{{" not in duration_info else "{{slide_duration}}"
            tf.vertical_anchor = 3 # Middle
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.CENTER
            p.runs[0].font.name = font_name
            p.runs[0].font.size = Pt(12)
            p.runs[0].font.color.rgb = RGBColor(255, 255, 255)

            # 3. Host Section (2.5cm, 7cm, 5x5cm)
            host_size = Cm(5.0)
            host_left = Cm(2.5)
            host_top = Cm(7.0)
            
            # 4. Extra Contacts (Grid area: 11cm, 4cm, 32cm, 16cm)
            grid_x = Cm(11.0)
            grid_y = Cm(4.0)
            grid_w = Cm(21.0) # 32 - 11
            grid_h = Cm(12.0) # 16 - 4
            
            num_extra = len(extra_contacts)
            rows = 1
            max_cols = num_extra
            if num_extra > 0:
                rows = 1 if num_extra <= 3 else 2
                items_p_row = [num_extra] if rows == 1 else [math.ceil(num_extra/2), num_extra - math.ceil(num_extra/2)]
                max_cols = max(items_p_row)
            
            # Synchronized font size based on max columns
            if max_cols <= 1:
                contact_font_size = Pt(18)
            elif max_cols == 2:
                contact_font_size = Pt(16)
            elif max_cols == 3:
                contact_font_size = Pt(14)
            else:
                contact_font_size = Pt(12)

            # Add Host Avatar
            host_pic_placeholder = slide.shapes.add_shape(
                9, # msoShapeOval
                host_left, host_top, host_size, host_size
            )
            host_pic_placeholder.name = "host_avatar"
            host_pic_placeholder.line.color.rgb = maroon_color
            host_pic_placeholder.line.width = Pt(3)
            
            # Add Host Info
            host_info_box = slide.shapes.add_textbox(host_left - Cm(1.0), host_top + host_size + Cm(0.2), host_size + Cm(2.0), Cm(1.0))
            tf = host_info_box.text_frame
            host_role = host.get('role', 'host').lower().replace(' ', '_')
            tf.text = f"{{{{{host_role}_info}}}}"
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.CENTER
            p.runs[0].font.name = font_name
            p.runs[0].font.size = contact_font_size

            if num_extra > 0:
                # Dynamic avatar size: 5x5cm for 1 row, 4.5x4.5cm for 2 rows
                contact_size = Cm(5.0) if rows == 1 else Cm(4.5)
                
                for r_idx, count in enumerate(items_p_row):
                    # Calculate gap: max gap is 3cm, but try to fill grid_w
                    remaining_w = grid_w - (count * contact_size)
                    num_gaps = count - 1
                    gap = min(remaining_w / num_gaps, Cm(3.0)) if num_gaps > 0 else 0
                    
                    total_row_w = count * contact_size + num_gaps * gap
                    start_x = grid_x + (grid_w - total_row_w) / 2
                    
                    # Fine-tuned row vertical positioning
                    if rows == 1:
                        y = grid_y + (grid_h - contact_size) / 2 - Cm(0.5)
                    else:
                        if r_idx == 0:
                            y = grid_y
                        else:
                            # Position Row 2 at the bottom, accounting for info box height
                            y = grid_y + grid_h - contact_size - Cm(1.1)
                    
                    for c_idx in range(count):
                        i = sum(items_p_row[:r_idx]) + c_idx
                        contact = extra_contacts[i]
                        x = start_x + c_idx * (contact_size + gap)
                        
                        # Avatar
                        contact_placeholder = slide.shapes.add_shape(
                            9, # msoShapeOval
                            x, y, contact_size, contact_size
                        )
                        contact_placeholder.name = f"contact{i+1}_avatar"
                        contact_placeholder.line.color.rgb = maroon_color
                        contact_placeholder.line.width = Pt(2)
                        
                        # Info
                        info_box = slide.shapes.add_textbox(x - Cm(0.5), y + contact_size + Cm(0.1), contact_size + Cm(1.0), Cm(1.0))
                        tf = info_box.text_frame
                        contact_role = contact.get('role', f'contact{i+1}').lower().replace(' ', '_')
                        placeholder_name = contact_role if any(c.isdigit() for c in contact_role) else f"{contact_role}{i+1}"
                        tf.text = f"{{{{{placeholder_name}_info}}}}"
                        p = tf.paragraphs[0]
                        p.alignment = PP_ALIGN.CENTER
                        p.runs[0].font.name = font_name
                        p.runs[0].font.size = contact_font_size

            prs.save(template_path)
            return True
        except Exception as e:
            current_app.logger.error(f"Error adding event template slide: {e}\n{traceback.format_exc()}")
            return False

    @staticmethod
    def generate_meeting_pptx(meeting_id):
        """Generate PowerPoint presentation for a meeting."""
        context = MeetingExportContext(meeting_id)
        meeting = context.meeting
        if not meeting:
            return None

        # Define formatting helpers
        def info_fmt(name, creds):
            if not name: return ""
            return f"{name}\n{creds}" if creds else name

        def dur_fmt(log):
            if not log: return ""
            dmin, dmax = log.Duration_Min, log.Duration_Max
            if dmin is not None and dmax is not None:
                if dmin == 0:
                    return f"{dmax} '"
                return f"{dmin} ~ {dmax} '"
            val = dmax if dmax is not None else dmin
            return f"{val} '" if val is not None else ""

        # Initialize and populate all placeholders
        replacements = MeetingSlideService._initialize_placeholders(meeting)
        
        # Pre-populate avatar_map with all standard placeholder prefixes as keys
        avatar_map = {
            "saa_avatar": None, "welcome-officer_avatar": None, "president_avatar": None,
            "vpm_avatar": None, "vpe_avatar": None, "vppr_avatar": None,
            "treasurer_avatar": None, "secretary_avatar": None, "tme_avatar": None,
            "timer_avatar": None, "ah-counter_avatar": None, "grammarian_avatar": None,
            "topicsmaster_avatar": None, "ge_avatar": None, "photographer_avatar": None,
            "keynote-speaker_avatar": None
        }
        for i in range(1, 7):
            avatar_map[f"ps{i}_avatar"] = None
            avatar_map[f"ie{i}_avatar"] = None
        
        MeetingSlideService._populate_standard_roles(context, meeting, replacements, info_fmt, dur_fmt, avatar_map)
        MeetingSlideService._populate_speakers(context, replacements, info_fmt, dur_fmt, avatar_map)
        MeetingSlideService._populate_evaluators(context, replacements, info_fmt, dur_fmt, avatar_map)
        MeetingSlideService._populate_panel_discussion(context, replacements, info_fmt, dur_fmt, avatar_map)
        MeetingSlideService._populate_featured_session(context, meeting, replacements, info_fmt, dur_fmt, avatar_map)
        MeetingSlideService._populate_table_topics(context, replacements, dur_fmt)

        # Load template and perform replacements
        template_path = os.path.join(current_app.static_folder, 'club_resources', str(meeting.club_id), 'slides_template.pptx')
        if not os.path.exists(template_path):
            current_app.logger.error(f"PPTX Template not found at: {template_path}")
            return None

        try:
            prs = Presentation(template_path)
            MeetingSlideService._perform_replacements(prs, replacements, avatar_map)
            MeetingSlideService._replace_avatar_shapes(prs, avatar_map)
            
            output = io.BytesIO()
            prs.save(output)
            output.seek(0)
            return output

        except Exception as e:
            current_app.logger.error(f"Error generating PPTX: {e}\n{traceback.format_exc()}")
            return None

    @staticmethod
    def _initialize_placeholders(meeting):
        """Initialize all PPTX placeholders with empty values."""
        replacements = {
            "{{meeting_number}}": str(meeting.Meeting_Number),
            "{{meeting_date}}": meeting.Meeting_Date.strftime('%d-%b-%Y') if meeting.Meeting_Date else "",
            "{{club_name}}": (meeting.club.club_name if meeting.club else ""),
        }
        
        # Role placeholders (info + duration)
        for p in ["saa", "welcome-officer", "president", "vpm", "vpe", "vppr", "treasurer", "secretary", 
                  "tme", "timer", "ah-counter", "grammarian", "topicsmaster", "ge", "photographer"]:
            replacements["{{" + p + "_info}}"] = ""
            replacements["{{" + p + "_duration}}"] = ""
        
        # Speaker placeholders (up to 6)
        for i in range(1, 7):
            replacements.update({
                f"{{{{ps{i}}}}}": "", f"{{{{ps{i}_title}}}}": "", 
                f"{{{{ps{i}-project_info}}}}": "", f"{{{{ps{i}_info}}}}": "", 
                f"{{{{ps{i}_duration}}}}": ""
            })
        
        # Evaluator placeholders (up to 6)
        for i in range(1, 7):
            replacements.update({
                f"{{{{ie{i}_info}}}}": "", f"{{{{ie{i}_duration}}}}": ""
            })
        
        # Panel Discussion placeholders
        replacements.update({
            "{{moderator_info}}": "",
            "{{panelist1_info}}": "", "{{panelist2_info}}": "",
            "{{panelist3_info}}": "", "{{panelist4_info}}": "",
            "{{panel-discussion_duration}}": ""
        })
        
        # Featured session and table topics
        replacements.update({
            "{{keynote_title}}": "", "{{keynote_duration}}": "", "{{keynote-speaker_info}}": "",
            "{{table-topics_duration}}": ""
        })
        
        return replacements

    @staticmethod
    def _populate_standard_roles(context, meeting, replacements, info_fmt, dur_fmt, avatar_map=None):
        """Populate standard role information from meeting logs and ExComm."""
        def populate_role(role_pattern=None, title_pattern=None, info_key=None, dur_key=None):
            last_match = None
            for log, st in context.logs:
                if not log.owner: continue
                role_name = (st.role.name if st.role else st.Title)
                if (role_pattern and role_name and re.search(role_pattern, role_name, re.I)) or \
                   (title_pattern and log.Session_Title and re.search(title_pattern, log.Session_Title, re.I)):
                    last_match = (log, st)
            
            if last_match:
                log, st = last_match
                if info_key: 
                    replacements[info_key] = info_fmt(log.owner.Name, derive_credentials(log.owner))
                    if avatar_map is not None:
                        prefix = info_key.replace("{{", "").replace("_info}}", "")
                        avatar_map[f"{prefix}_avatar"] = log.owner

                if dur_key: replacements[dur_key] = dur_fmt(log)
                return True
            return False
        
        # Populate from meeting logs
        roles_config = [
            ("saa", None, "SAA Introduction"), ("president", None, "President's Address"),
            ("welcome-officer", "Welcome Officer", None), ("tme", "Toastmaster", None),
            ("timer", "Timer", None), ("ah-counter", "Ah-Counter", None),
            ("grammarian", "Grammarian", None), ("topicsmaster", "Topicsmaster", None),
            ("ge", "General Evaluator", None), ("photographer", "Photographer", None)
        ]
        for prefix, role_p, title_p in roles_config:
            populate_role(role_p, title_p, "{{" + prefix + "_info}}", "{{" + prefix + "_duration}}")
        
        # Fallback to ExComm for missing info
        excomm = meeting.get_excomm()
        if excomm:
            officers = excomm.get_officers()
            role_to_prefix = {
                "President": "president", "VPE": "vpe", "VPM": "vpm", "VPPR": "vppr",
                "Secretary": "secretary", "Treasurer": "treasurer", "SAA": "saa",
                "Welcome Officer": "welcome-officer"
            }
            for role_name, contact in officers.items():
                prefix = role_to_prefix.get(role_name)
                key = "{{" + prefix + "_info}}" if prefix else None
                if prefix and contact and key and not replacements.get(key):
                    replacements[key] = info_fmt(contact.Name, derive_credentials(contact))
                    if avatar_map is not None:
                        avatar_map[f"{prefix}_avatar"] = contact

    @staticmethod
    def _populate_panel_discussion(context, replacements, info_fmt, dur_fmt, avatar_map=None):
        """Populate Moderator and Panelist information."""
        # Moderator - check for single owner
        moderator_log = next((log for log, st in context.logs if st.role and st.role.name == "Moderator"), None)
        if moderator_log:
            replacements["{{panel-discussion_duration}}"] = dur_fmt(moderator_log)
            if moderator_log.owner:
                replacements["{{moderator_info}}"] = info_fmt(moderator_log.owner.Name, derive_credentials(moderator_log.owner))
                if avatar_map is not None:
                    avatar_map["moderator_avatar"] = moderator_log.owner

        # Panelists - can be multiple
        panelists = []
        for log, st in context.logs:
            if st.role and st.role.name == "Panelist":
                # A log can have multiple owners, or we might have multiple logs
                if log.owners:
                    panelists.extend(log.owners)
                elif log.owner:
                    panelists.append(log.owner)
        
        # Unique list preservation order
        seen = set()
        unique_panelists = []
        for p in panelists:
            if p.id not in seen:
                unique_panelists.append(p)
                seen.add(p.id)

        for i, panelist in enumerate(unique_panelists[:4], 1):
            replacements[f"{{{{panelist{i}_info}}}}"] = info_fmt(panelist.Name, derive_credentials(panelist))
            if avatar_map is not None:
                avatar_map[f"panelist{i}_avatar"] = panelist

    @staticmethod
    def _populate_speakers(context, replacements, info_fmt, dur_fmt, avatar_map=None):
        """Populate prepared speaker information (up to 6 speakers)."""
        speakers = [(log, st) for log, st in context.logs if (st.role and st.role.name == "Prepared Speaker" and log.owner)]
        for i, (log, st) in enumerate(speakers[:6], 1):
            replacements[f"{{{{ps{i}}}}}"] = log.owner.Name
            replacements[f"{{{{ps{i}_info}}}}"] = info_fmt(log.owner.Name, derive_credentials(log.owner))
            replacements[f"{{{{ps{i}_duration}}}}"] = dur_fmt(log)
            if avatar_map is not None:
                avatar_map[f"ps{i}_avatar"] = log.owner
            
            details = context.speech_details.get(log.id)
            if details:
                replacements[f"{{{{ps{i}_title}}}}"] = details['speech_title'] or details['project_name'] or ""
                replacements[f"{{{{ps{i}-project_info}}}}"] = f"{details['project_code']} - {details['project_name']}" if details['project_code'] and details['project_name'] else (details['project_name'] or "")
            else:
                replacements[f"{{{{ps{i}_title}}}}"] = log.Session_Title or ""

    @staticmethod
    def _populate_evaluators(context, replacements, info_fmt, dur_fmt, avatar_map=None):
        """Populate individual evaluator information (up to 6 evaluators)."""
        evaluators = [(log, st) for log, st in context.logs if (st.role and st.role.name == "Individual Evaluator" and log.owner)]
        for i, (log, st) in enumerate(evaluators[:6], 1):
            replacements[f"{{{{ie{i}_info}}}}"] = info_fmt(log.owner.Name, derive_credentials(log.owner))
            replacements[f"{{{{ie{i}_duration}}}}"] = dur_fmt(log)
            if avatar_map is not None:
                avatar_map[f"ie{i}_avatar"] = log.owner

    @staticmethod
    def _populate_featured_session(context, meeting, replacements, info_fmt, dur_fmt, avatar_map=None):
        """Populate keynote/featured session based on meeting type."""
        featured = None
        m_type = (meeting.type or "").strip().lower()
        
        for l, s in context.logs:
            if m_type and ((s.Title and s.Title.strip().lower() == m_type) or 
                          (l.Session_Title and l.Session_Title.strip().lower() == m_type)):
                featured = (l, s)
                break
        
        if not featured:
            featured = next(((l, s) for l, s in context.logs if s.role and s.role.name == "Keynote Speaker"), None)
        
        if not featured:
            featured = next(((l, s) for l, s in context.logs if s.role and s.role.name in ["Moderator", "Workshop Presenter", "Moderator-Host"]), None)
        
        if featured:
            replacements["{{keynote_title}}"] = featured[0].Session_Title or meeting.type or "Featured Session"
            replacements["{{keynote_duration}}"] = dur_fmt(featured[0])
            if featured[0].owner:
                replacements["{{keynote-speaker_info}}"] = info_fmt(featured[0].owner.Name, derive_credentials(featured[0].owner))
                if avatar_map is not None:
                    avatar_map["keynote-speaker_avatar"] = featured[0].owner
        else:
            replacements["{{keynote_title}}"] = meeting.type or ""

    @staticmethod
    def _populate_table_topics(context, replacements, dur_fmt):
        """Populate table topics duration."""
        tt = next(((l, s) for l, s in context.logs if (s.Title == "Table Topics" or (s.role and s.role.name == "Topicsmaster"))), (None, None))
        if tt[0]:
            replacements["{{table-topics_duration}}"] = dur_fmt(tt[0])

    @staticmethod
    def _perform_replacements(prs, replacements, avatar_map=None):
        """Apply all placeholder replacements to PowerPoint presentation."""
        def robust_replace(text):
            text = re.sub(r'Evaluator\s*for', 'Evaluator for', text, flags=re.I)
            text = re.sub(r'INDIVIDUAL EVALUATOR\s*for', 'INDIVIDUAL EVALUATOR for', text, flags=re.I)
            for key, val in replacements.items():
                if key in text:
                    text = text.replace(key, str(val))
            return text
        
        for slide in prs.slides:
            for shape in slide.shapes:
                if shape.name in avatar_map:
                    continue
                if not shape.has_text_frame:
                    continue
                for paragraph in shape.text_frame.paragraphs:
                    full_text = "".join(run.text for run in paragraph.runs)
                    updated_text = robust_replace(full_text)
                    if updated_text != full_text:
                        if paragraph.runs:
                            paragraph.runs[0].text = updated_text
                            for i in range(1, len(paragraph.runs)):
                                paragraph.runs[i].text = ""
                        else:
                            paragraph.text = updated_text

    @staticmethod
    def _crop_image_to_aspect_ratio(image_path, target_width, target_height):
        """Crops an image to match the target aspect ratio (center crop)."""
        try:
            im = Image.open(image_path)
            img_w, img_h = im.size
            
            target_ratio = target_width / target_height
            img_ratio = img_w / img_h
            
            if img_ratio > target_ratio:
                new_width = int(img_h * target_ratio)
                left = (img_w - new_width) // 2
                box = (left, 0, left + new_width, img_h)
            else:
                new_height = int(img_w / target_ratio)
                top = (img_h - new_height) // 2
                box = (0, top, img_w, top + new_height)
                
            cropped_im = im.crop(box)
            
            if cropped_im.mode in ('RGBA', 'LA'):
                background = Image.new(cropped_im.mode[:-1], cropped_im.size, (255, 255, 255))
                background.paste(cropped_im, mask=cropped_im.split()[-1])
                cropped_im = background.convert('RGB')
            elif cropped_im.mode != 'RGB':
                cropped_im = cropped_im.convert('RGB')

            base, ext = os.path.splitext(image_path)
            cropped_path = f"{base}_cropped.jpg"
            cropped_im.save(cropped_path, 'JPEG', quality=95)
            return cropped_path
        except Exception as e:
            current_app.logger.error(f"Error cropping image: {e}")
            return None

    @staticmethod
    def _fill_shape_with_image(slide, shape, image_path):
        """Fills an existing AutoShape with an image by injecting a blipFill."""
        try:
            dummy_pic = slide.shapes.add_picture(image_path, 0, 0, 0, 0)
            rId = dummy_pic._element.blipFill.blip.rEmbed
            slide.shapes._spTree.remove(dummy_pic._element)
            
            spPr = shape._element.spPr
            for child in list(spPr):
                if child.tag.endswith(('solidFill', 'gradFill', 'noFill', 'blipFill', 'pattFill', 'grpFill')):
                    spPr.remove(child)
            
            ns_r = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
            blipFill = OxmlElement('a:blipFill')
            blipFill.set('rotWithShape', '1')
            
            blip = OxmlElement('a:blip')
            blip.set(f'{{{ns_r}}}embed', rId)
            blipFill.append(blip)
            
            stretch = OxmlElement('a:stretch')
            fillRect = OxmlElement('a:fillRect')
            stretch.append(fillRect)
            blipFill.append(stretch)
            
            insert_idx = 0
            for i, child in enumerate(spPr):
                if child.tag.endswith(('prstGeom', 'custGeom', 'xfrm')):
                     insert_idx = i + 1
            spPr.insert(insert_idx, blipFill)
            
        except Exception as e:
            current_app.logger.error(f"Error filling shape {shape.name}: {e}")

    @staticmethod
    def _replace_avatar_shapes(prs, avatar_map):
        """Replace placeholder shapes with avatar images (using fill)."""
        if not avatar_map:
            return

        normalized_map = {k.strip().lower(): v for k, v in avatar_map.items()}

        for slide in prs.slides:
            for shape in slide.shapes:
                shape_name_clean = (shape.name or "").strip().lower()
                if shape_name_clean in normalized_map:
                    data = normalized_map[shape_name_clean]
                    avatar_url = data.Avatar_URL if data and hasattr(data, 'Avatar_URL') else None
                    
                    image_path = None
                    if avatar_url:
                        if avatar_url.startswith('/static/'):
                            avatar_url = avatar_url[8:]
                        elif avatar_url.startswith('static/'):
                            avatar_url = avatar_url[7:]
                        
                        if '/' not in avatar_url and '\\' not in avatar_url:
                            root = current_app.config.get('AVATAR_ROOT_DIR', 'uploads/avatars')
                            avatar_url = os.path.join(root, avatar_url)
                        
                        rel_path = avatar_url.lstrip('/')
                        image_path = os.path.join(current_app.static_folder, rel_path)
                        
                        if not os.path.exists(image_path):
                            image_path = None
                            
                    if not image_path:
                        for default_name in ["default_avatar.jpg", "default_avatar.png", "avatar_default.jpg"]:
                            temp_path = os.path.join(current_app.static_folder, default_name)
                            if os.path.exists(temp_path):
                                image_path = temp_path
                                break
                        
                        if not image_path:
                             root = current_app.config.get('AVATAR_ROOT_DIR', 'uploads/avatars')
                             temp_path = os.path.join(current_app.static_folder, root, "default.jpg")
                             if os.path.exists(temp_path):
                                 image_path = temp_path

                    try:
                        cropped_path = MeetingSlideService._crop_image_to_aspect_ratio(
                            image_path, shape.width, shape.height
                        )
                        if not cropped_path:
                            continue
                            
                        MeetingSlideService._fill_shape_with_image(slide, shape, cropped_path)
                        try: os.remove(cropped_path)
                        except: pass
                        
                    except Exception as e:
                        current_app.logger.error(f"Error processing avatar for {shape.name}: {e}")
