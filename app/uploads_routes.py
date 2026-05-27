import os
import io
import zipfile
import secrets
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, request, jsonify, send_from_directory, current_app, flash, abort, Response
from flask_login import current_user
from werkzeug.utils import secure_filename

from . import db
from .auth.utils import is_authorized
from .auth.permissions import Permissions, permission_required
from .models import UploadLink, Meeting
from .club_context import get_current_club_id

uploads_bp = Blueprint('uploads_bp', __name__)

def generate_random_code(length=8):
    """Generate a random alphanumeric code of specified length."""
    alphabet = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    # Ensure code is unique in database
    while True:
        code = ''.join(secrets.choice(alphabet) for _ in range(length))
        if not UploadLink.query.filter_by(code=code).first():
            return code

def format_size(size_bytes):
    """Format file size in a human-readable format."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"

def get_club_storage_used(club_id):
    """Calculate total storage size in bytes used by all upload links of a club."""
    links = UploadLink.query.filter_by(club_id=club_id).all()
    total_size = 0
    for link in links:
        folder_path = os.path.join(current_app.root_path, 'static', 'uploads', link.code)
        if os.path.exists(folder_path) and os.path.isdir(folder_path):
            for entry in os.scandir(folder_path):
                if entry.is_file() and not entry.name.startswith('.'):
                    total_size += entry.stat().st_size
    return total_size

@uploads_bp.route('/uploads/', methods=['GET'])
@permission_required(Permissions.FILE_UPLOAD_MANAGE)
def manage_uploads():
    club_id = get_current_club_id()
    if not club_id:
        flash("Club context not found.", "error")
        return redirect(url_for('agenda_bp.agenda'))
        
    upload_links = UploadLink.query.filter_by(club_id=club_id).order_by(UploadLink.created_at.desc()).all()
    
    # Get the nearest upcoming meeting to pre-fill the form
    upcoming_meeting = Meeting.query.filter(
        Meeting.club_id == club_id,
        Meeting.status.in_(['not started', 'unpublished', 'running'])
    ).order_by(Meeting.Meeting_Date.asc(), Meeting.id.asc()).first()
    
    default_meeting_number = upcoming_meeting.Meeting_Number if upcoming_meeting else ""
    
    # Generate a sample unique code
    suggested_code = generate_random_code()
    
    # Default 7-day expiration (naive local time for matching HTML datetime-local)
    from datetime import timedelta
    default_expiry = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%dT%H:%M')
    
    # Calculate storage stats
    used_bytes = get_club_storage_used(club_id)
    max_bytes = current_app.config.get('MAX_CLUB_STORAGE', 100 * 1024 * 1024)
    storage_percentage = round((used_bytes / max_bytes) * 100, 1) if max_bytes > 0 else 0
    
    # Calculate file counts and disk usage for each link
    stats = {}
    for link in upload_links:
        folder_path = os.path.join(current_app.root_path, 'static', 'uploads', link.code)
        file_count = 0
        total_size = 0
        if os.path.exists(folder_path) and os.path.isdir(folder_path):
            for entry in os.scandir(folder_path):
                if entry.is_file() and not entry.name.startswith('.'):
                    file_count += 1
                    total_size += entry.stat().st_size
        stats[link.id] = {
            'file_count': file_count,
            'total_size_formatted': format_size(total_size)
        }
        
    return render_template(
        'uploads/manage.html',
        upload_links=upload_links,
        default_meeting_number=default_meeting_number,
        suggested_code=suggested_code,
        default_expiry=default_expiry,
        stats=stats,
        storage_used=format_size(used_bytes),
        storage_max=format_size(max_bytes),
        storage_percentage=storage_percentage
    )

@uploads_bp.route('/uploads/create', methods=['POST'])
@permission_required(Permissions.FILE_UPLOAD_MANAGE)
def create_upload_link():
    club_id = get_current_club_id()
    if not club_id:
        flash("Club context not found.", "error")
        return redirect(url_for('uploads_bp.manage_uploads'))
        
    description = request.form.get('description', '').strip()
    meeting_number = request.form.get('meeting_number', '').strip()
    expires_at_str = request.form.get('expires_at', '').strip()
    max_files = request.form.get('max_files', '').strip()
    max_file_size = request.form.get('max_file_size', '').strip()
    
    # Implicitly generate the upload code
    code = generate_random_code()
    
    # Resolve meeting number
    meeting_id = None
    if meeting_number:
        try:
            meeting = Meeting.query.filter_by(club_id=club_id, Meeting_Number=int(meeting_number)).first()
            if meeting:
                meeting_id = meeting.id
            else:
                flash(f"Meeting #{meeting_number} does not exist in this club. Linked meeting defaulted to none.", "info")
        except ValueError:
            flash("Meeting number must be an integer. Linked meeting defaulted to none.", "error")
            
    # Set title based on meeting resolution
    if meeting_id:
        title = f"Meeting #{meeting_number}"
    else:
        title = "Unspecified"
            
    # Parse expiration date (default to 7 days if empty)
    expires_at = None
    if expires_at_str:
        try:
            expires_at = datetime.strptime(expires_at_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            flash("Invalid expiration date format.", "error")
    
    if expires_at is None:
        from datetime import timedelta
        expires_at = datetime.now() + timedelta(days=7)
            
    # Parse max files (default to 5 if empty)
    max_files_int = 5
    if max_files:
        try:
            max_files_int = int(max_files)
        except ValueError:
            pass
            
    # Parse max file size (default to 10 MB if empty)
    max_file_size_int = 10
    if max_file_size:
        try:
            max_file_size_int = int(max_file_size)
        except ValueError:
            pass
            
    link = UploadLink(
        code=code,
        title=title,
        description=description if description else None,
        club_id=club_id,
        meeting_id=meeting_id,
        created_by_id=current_user.id if current_user.is_authenticated else None,
        expires_at=expires_at,
        max_files=max_files_int,
        max_file_size=max_file_size_int,
        is_active=True
    )
    
    db.session.add(link)
    db.session.commit()
    
    # Ensure uploads subfolder exists
    folder_path = os.path.join(current_app.root_path, 'static', 'uploads', code)
    os.makedirs(folder_path, exist_ok=True)
    
    return redirect(url_for('uploads_bp.manage_uploads'))

@uploads_bp.route('/uploads/edit/<int:link_id>', methods=['POST'])
@permission_required(Permissions.FILE_UPLOAD_MANAGE)
def edit_upload_link(link_id):
    club_id = get_current_club_id()
    link = UploadLink.query.filter_by(id=link_id, club_id=club_id).first_or_404()
    
    description = request.form.get('description', '').strip()
    meeting_number = request.form.get('meeting_number', '').strip()
    expires_at_str = request.form.get('expires_at', '').strip()
    max_files = request.form.get('max_files', '').strip()
    max_file_size = request.form.get('max_file_size', '').strip()
    
    # Resolve meeting number
    meeting_id = None
    if meeting_number:
        try:
            meeting = Meeting.query.filter_by(club_id=club_id, Meeting_Number=int(meeting_number)).first()
            if meeting:
                meeting_id = meeting.id
            else:
                flash(f"Meeting #{meeting_number} does not exist in this club. Linked meeting set to none.", "info")
        except ValueError:
            flash("Meeting number must be an integer. Linked meeting set to none.", "error")
            
    # Set title based on meeting resolution
    if meeting_id:
        title = f"Meeting #{meeting_number}"
    else:
        title = "Unspecified"
            
    # Parse expiration date
    expires_at = None
    if expires_at_str:
        try:
            expires_at = datetime.strptime(expires_at_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            flash("Invalid expiration date format.", "error")
            
    # Parse constraints
    max_files_int = None
    if max_files:
        try:
            max_files_int = int(max_files)
        except ValueError:
            pass
            
    max_file_size_int = None
    if max_file_size:
        try:
            max_file_size_int = int(max_file_size)
        except ValueError:
            pass
            
    link.title = title
    link.description = description if description else None
    link.meeting_id = meeting_id
    link.expires_at = expires_at
    link.max_files = max_files_int
    link.max_file_size = max_file_size_int
    
    db.session.commit()
    flash("Upload link updated successfully.", "success")
    return redirect(url_for('uploads_bp.manage_uploads'))

@uploads_bp.route('/uploads/toggle/<int:link_id>', methods=['POST'])
@permission_required(Permissions.FILE_UPLOAD_MANAGE)
def toggle_upload_link(link_id):
    club_id = get_current_club_id()
    link = UploadLink.query.filter_by(id=link_id, club_id=club_id).first_or_404()
    
    link.is_active = not link.is_active
    db.session.commit()
    
    state = "activated" if link.is_active else "deactivated"
    return jsonify(success=True, is_active=link.is_active, message=f"Upload link {state} successfully.")

@uploads_bp.route('/uploads/delete/<int:link_id>', methods=['POST'])
@permission_required(Permissions.FILE_UPLOAD_MANAGE)
def delete_upload_link(link_id):
    club_id = get_current_club_id()
    link = UploadLink.query.filter_by(id=link_id, club_id=club_id).first_or_404()
    
    # Remove files from disk
    folder_path = os.path.join(current_app.root_path, 'static', 'uploads', link.code)
    if os.path.exists(folder_path) and os.path.isdir(folder_path):
        try:
            import shutil
            shutil.rmtree(folder_path)
        except OSError as e:
            current_app.logger.error(f"Failed to delete upload folder {folder_path}: {e}")
            
    db.session.delete(link)
    db.session.commit()
    
    flash("Upload link and files deleted successfully.", "success")
    return redirect(url_for('uploads_bp.manage_uploads'))

@uploads_bp.route('/uploads/<code>/files', methods=['GET'])
@permission_required(Permissions.FILE_UPLOAD_MANAGE)
def view_upload_files(code):
    club_id = get_current_club_id()
    link = UploadLink.query.filter_by(code=code, club_id=club_id).first_or_404()
    
    folder_path = os.path.join(current_app.root_path, 'static', 'uploads', code)
    files = []
    total_size = 0
    
    if os.path.exists(folder_path) and os.path.isdir(folder_path):
        for entry in os.scandir(folder_path):
            if entry.is_file() and not entry.name.startswith('.'):
                stat = entry.stat()
                file_size = stat.st_size
                total_size += file_size
                mtime = datetime.fromtimestamp(stat.st_mtime)
                
                # Deduce file type icon
                ext = os.path.splitext(entry.name)[1].lower()
                icon = "fa-file"
                if ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                    icon = "fa-file-image"
                elif ext in ['.pdf']:
                    icon = "fa-file-pdf"
                elif ext in ['.doc', '.docx']:
                    icon = "fa-file-word"
                elif ext in ['.xls', '.xlsx']:
                    icon = "fa-file-excel"
                elif ext in ['.zip', '.rar', '.tar', '.gz']:
                    icon = "fa-file-archive"
                elif ext in ['.mp4', '.avi', '.mov', '.mkv']:
                    icon = "fa-file-video"
                elif ext in ['.mp3', '.wav', '.ogg']:
                    icon = "fa-file-audio"
                elif ext in ['.txt', '.md']:
                    icon = "fa-file-alt"
                    
                files.append({
                    'name': entry.name,
                    'size': format_size(file_size),
                    'size_bytes': file_size,
                    'mtime': mtime,
                    'icon': icon
                })
                
    # Sort files by newest first
    files.sort(key=lambda x: x['mtime'], reverse=True)
    
    return render_template(
        'uploads/view_files.html',
        link=link,
        files=files,
        total_files=len(files),
        total_size_formatted=format_size(total_size)
    )

@uploads_bp.route('/uploads/<code>/download/<path:filename>', methods=['GET'])
@permission_required(Permissions.FILE_UPLOAD_MANAGE)
def download_file(code, filename):
    club_id = get_current_club_id()
    # Verify ownership
    UploadLink.query.filter_by(code=code, club_id=club_id).first_or_404()
    
    directory = os.path.join(current_app.root_path, 'static', 'uploads', code)
    # Secure transmission using send_from_directory
    return send_from_directory(directory, filename, as_attachment=True)

@uploads_bp.route('/uploads/<code>/delete-files', methods=['POST'])
@permission_required(Permissions.FILE_UPLOAD_MANAGE)
def delete_files(code):
    club_id = get_current_club_id()
    # Verify ownership
    UploadLink.query.filter_by(code=code, club_id=club_id).first_or_404()
    
    data = request.get_json()
    if not data or 'filenames' not in data:
        return jsonify(success=False, error="Invalid request payload."), 400
        
    filenames = data['filenames']
    folder_path = os.path.join(current_app.root_path, 'static', 'uploads', code)
    
    deleted_count = 0
    errors = []
    
    for filename in filenames:
        # Clean filename to prevent path traversal
        clean_name = secure_filename(filename)
        if not clean_name:
            continue
            
        file_path = os.path.join(folder_path, clean_name)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            try:
                os.remove(file_path)
                deleted_count += 1
            except OSError as e:
                errors.append(f"Could not delete '{clean_name}': {str(e)}")
        else:
            errors.append(f"File '{clean_name}' not found.")
            
    if errors:
        return jsonify(
            success=deleted_count > 0,
            deleted_count=deleted_count,
            message=f"Deleted {deleted_count} files. Some errors occurred.",
            errors=errors
        )
    return jsonify(success=True, deleted_count=deleted_count, message=f"Successfully deleted {deleted_count} files.")

@uploads_bp.route('/uploads/<code>/zip', methods=['GET'])
@permission_required(Permissions.FILE_UPLOAD_MANAGE)
def download_zip(code):
    club_id = get_current_club_id()
    link = UploadLink.query.filter_by(code=code, club_id=club_id).first_or_404()
    
    folder_path = os.path.join(current_app.root_path, 'static', 'uploads', code)
    
    if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
        abort(404)
        
    zip_data = io.BytesIO()
    file_count = 0
    with zipfile.ZipFile(zip_data, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for entry in os.scandir(folder_path):
            if entry.is_file() and not entry.name.startswith('.'):
                file_path = os.path.join(folder_path, entry.name)
                # Keep direct name as archive name (do not nest folders)
                zipf.write(file_path, entry.name)
                file_count += 1
                
    if file_count == 0:
        flash("No files to package for download.", "info")
        return redirect(url_for('uploads_bp.view_upload_files', code=code))
        
    # Get buffer size and reset cursor
    size = zip_data.tell()
    zip_data.seek(0)
    
    # Format filename safely
    safe_title = secure_filename(link.title).replace('_', ' ')
    if not safe_title:
        safe_title = f"uploads_{code}"
        
    filename = f"{safe_title}.zip"
    
    return Response(
        zip_data.read(),
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Content-Length': str(size),
            'Content-Type': 'application/zip',
            'Cache-Control': 'no-cache'
        }
    )

@uploads_bp.route('/upload/<code>', methods=['GET'])
def upload_page(code):
    link = UploadLink.query.filter_by(code=code).first_or_404()
    
    # Perform status validations
    if not link.is_active:
        return render_template('uploads/upload.html', link=link, error_message="This upload link has been disabled by the administrator.")
        
    if link.is_expired:
        return render_template('uploads/upload.html', link=link, error_message="This upload link has expired.")
        
    # Check club storage limit
    max_bytes = current_app.config.get('MAX_CLUB_STORAGE', 100 * 1024 * 1024)
    if get_club_storage_used(link.club_id) >= max_bytes:
        return render_template('uploads/upload.html', link=link, error_message="This upload link is currently unavailable because the club's storage quota has been exceeded.")
        
    return render_template('uploads/upload.html', link=link)

@uploads_bp.route('/upload/<code>', methods=['POST'])
def upload_file(code):
    link = UploadLink.query.filter_by(code=code).first_or_404()
    
    if not link.is_active or link.is_expired:
        return jsonify(success=False, error="This upload link is inactive or has expired."), 403
        
    if 'files[]' not in request.files:
        return jsonify(success=False, error="No files were uploaded."), 400
        
    uploaded_files = request.files.getlist('files[]')
    
    if not uploaded_files or (len(uploaded_files) == 1 and uploaded_files[0].filename == ''):
        return jsonify(success=False, error="No files selected."), 400
        
    # Check club storage limit and reject incoming size
    max_bytes = current_app.config.get('MAX_CLUB_STORAGE', 100 * 1024 * 1024)
    used_bytes = get_club_storage_used(link.club_id)
    
    incoming_size = 0
    for file in uploaded_files:
        if file:
            file.seek(0, os.SEEK_END)
            incoming_size += file.tell()
            file.seek(0) # Reset stream pointer
            
    if used_bytes + incoming_size > max_bytes:
        return jsonify(success=False, error=f"Upload refused. Your club has exceeded its maximum storage limit of {format_size(max_bytes)} (Currently using: {format_size(used_bytes)}, trying to upload: {format_size(incoming_size)})."), 400
        
    folder_path = os.path.join(current_app.root_path, 'static', 'uploads', code)
    os.makedirs(folder_path, exist_ok=True)
    
    # 1. Enforce max_files validation if specified
    if link.max_files is not None:
        # Count existing files
        existing_count = 0
        for entry in os.scandir(folder_path):
            if entry.is_file() and not entry.name.startswith('.'):
                existing_count += 1
        if existing_count + len(uploaded_files) > link.max_files:
            space_left = max(0, link.max_files - existing_count)
            return jsonify(success=False, error=f"Max file limit exceeded. This link allows up to {link.max_files} files. You already have {existing_count} and tried to add {len(uploaded_files)} (Space left: {space_left})."), 400
            
    saved_files = []
    errors = []
    
    for file in uploaded_files:
        if not file.filename:
            continue
            
        # 2. Enforce max_file_size validation if specified
        if link.max_file_size is not None:
            # Check content length from request headers, or read file bytes to check
            file.seek(0, os.SEEK_END)
            file_size_bytes = file.tell()
            file.seek(0) # Reset stream
            
            max_size_bytes = link.max_file_size * 1024 * 1024
            if file_size_bytes > max_size_bytes:
                errors.append(f"'{file.filename}' exceeds size limit of {link.max_file_size} MB.")
                continue
                
        filename = secure_filename(file.filename)
        if not filename:
            errors.append("Invalid filename.")
            continue
            
        file_path = os.path.join(folder_path, filename)
        
        # Check if file already exists to avoid overwriting or append suffix
        if os.path.exists(file_path):
            base, extension = os.path.splitext(filename)
            counter = 1
            while os.path.exists(os.path.join(folder_path, f"{base}_{counter}{extension}")):
                counter += 1
            filename = f"{base}_{counter}{extension}"
            file_path = os.path.join(folder_path, filename)
            
        try:
            file.save(file_path)
            saved_files.append(filename)
        except OSError as e:
            errors.append(f"Failed to save '{file.filename}': {str(e)}")
            
    if errors and not saved_files:
        return jsonify(success=False, error="; ".join(errors)), 400
        
    return jsonify(
        success=True,
        saved_files=saved_files,
        message=f"Uploaded {len(saved_files)} files successfully.",
        errors=errors if errors else None
    )
