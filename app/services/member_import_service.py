import csv
import io
import openpyxl
from app.models import User, Contact, UserClub, Message, Club
from app.users_routes import _save_user_data
from app import db
from flask_login import current_user

def process_member_file(file_bytes, ext, club_id):
    """
    Processes a CSV or XLSX byte content to import members or invite existing users.
    Returns (success_count, failed_users)
    """
    success_count = 0
    failed_users = []
    
    club = db.session.get(Club, club_id)
    if not club:
        failed_users.append("Invalid club ID.")
        return success_count, failed_users

    rows = []
    if ext == 'csv':
        try:
            stream = io.StringIO(file_bytes.decode("UTF8"), newline=None)
            csv_reader = csv.reader(stream)
            rows = list(csv_reader)[1:] # Skip header row
        except Exception as e:
            failed_users.append(f"Failed to parse CSV: {str(e)}")
            return success_count, failed_users
    elif ext == 'xlsx':
        try:
            stream = io.BytesIO(file_bytes)
            wb = openpyxl.load_workbook(stream, data_only=True)
            sheet = wb.active
            for i, row in enumerate(sheet.iter_rows(values_only=True)):
                if i == 0: 
                    continue # Skip header
                # Convert tuple to list
                rows.append(list(row))
        except Exception as e:
             failed_users.append(f"Failed to parse XLSX: {str(e)}")
             return success_count, failed_users
    else:
        failed_users.append(f"Unsupported file extension: {ext}")
        return success_count, failed_users

    for row in rows:
        # Check if row is completely empty
        if not row or len([x for x in row if x is not None and str(x).strip() != '']) == 0:
            continue

        # Normalize row to ensure we have at least 5 elements, converting all to string
        row_str = [str(x).strip() if x is not None else "" for x in row]
        fullname, username, member_id, email, mentor_name = (row_str + [""]*5)[:5]

        if not fullname or not username:
            failed_users.append(
                f"Skipping row: Fullname and Username are mandatory. Row: {row_str}")
            continue

        # Duplicate detection (users data)
        email = email if email else None
        
        # Try to find existing user globally by email first, then username
        existing_user = None
        if email:
            existing_user = User.query.filter_by(email=email).first()
        if not existing_user:
            existing_user = User.query.filter_by(username=username).first()

        if existing_user:
            # Check if they are already in the current club
            is_in_club = UserClub.query.filter_by(user_id=existing_user.id, club_id=club_id).first()
            if is_in_club:
                failed_users.append(f"Skipping user '{username}': Already a member of this club.")
                continue
                
            # If not in club, send invitation. Do not modify info.
            sender_id = None
            sender_name = "A Club Admin"
            if current_user and current_user.is_authenticated:
                sender_id = current_user.id
                sender_name = current_user.display_name
            else:
                sysadmin = User.query.get(1)
                if sysadmin:
                    sender_id = sysadmin.id

            if sender_id:
                msg = Message(
                    sender_id=sender_id,
                    recipient_id=existing_user.id,
                    subject=f"Invitation to join {club.club_name}",
                    body=f"Hello {existing_user.first_name},\n\n{sender_name} has invited you to join **{club.club_name}**.\n\nPlease respond using the buttons below.\n[CLUB_ID:{club_id}]"
                )
                db.session.add(msg)
                success_count += 1
            else:
                failed_users.append(f"Skipping user '{username}': No sender available to invite existing user.")
            continue
            
        # If new user, create them
        from app.models import AuthRole
        user_role = AuthRole.query.filter_by(name='Member').first()
        role_id = user_role.id if user_role else None

        contact = Contact.query.filter_by(Name=fullname).first()
        contact_id = contact.id if contact else None

        try:
            user = _save_user_data(
                username=username,
                email=email,
                full_name=fullname,
                role_id=role_id,
                contact_id=contact_id,
                club_id=club_id,
                password='toastmasters'
            )
            
            # Update contact record with additional fields (mentor, member_id)
            if (mentor_name or member_id) and user:
                uc = UserClub.query.filter_by(user_id=user.id, club_id=club_id).first()
                if uc and uc.contact_id:
                    contact_record = Contact.query.get(uc.contact_id)
                    if contact_record:
                        if mentor_name:
                            mentor_contact = Contact.query.filter_by(Name=mentor_name.strip()).first()
                            if mentor_contact:
                                contact_record.Mentor_ID = mentor_contact.id
                        if member_id:
                            contact_record.Member_ID = member_id.strip()

            success_count += 1
        except Exception as e:
            failed_users.append(f"Failed to create user '{username}': {str(e)}")

    db.session.commit()
    return success_count, failed_users
