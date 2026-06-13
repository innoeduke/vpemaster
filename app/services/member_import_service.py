import csv
import io
import openpyxl
import re
import string
import random
from app.models import User, Contact, UserClub, Message, Club, ContactClub
from app.users_routes import _save_user_data
from app import db
from flask_login import current_user


def normalize_header(h):
    """
    Normalizes a header string by converting to lowercase, stripping whitespace,
    and removing '*', '(optional)', and '(required)'.
    """
    if h is None:
        return ""
    s = str(h).strip().lower()
    s = s.replace("*", "").replace("(optional)", "").replace("(required)", "").strip()
    return s


def validate_headers(headers):
    """
    Validates that the file has exactly 6 columns and they match the expected header names in order.
    """
    if not headers or len(headers) != 6:
        return False

    expected = [
        ['fullname'],
        ['username'],
        ['member number', 'member id'],
        ['email', 'email address', 'email_address'],
        ['phone', 'phone number', 'phone_number'],
        ['mentor name', 'mentor_name']
    ]

    for i, expected_names in enumerate(expected):
        val = normalize_header(headers[i])
        if val not in expected_names:
            return False

    return True


def generate_username(fullname):
    """
    Generates a unique username of exactly 8 characters based on the fullname.
    Tries 8 letters first, and only replaces trailing letters with digits sequentially
    on collision.
    """
    # Clean fullname to only lowercase letters
    letters = [c.lower() for c in fullname if c.isalpha()]
    if not letters:
        letters = list("user")

    # Base candidate: exactly 8 lowercase letters
    candidate = "".join(letters[:8])
    if len(candidate) < 8:
        needed = 8 - len(candidate)
        candidate += "".join(random.choices(string.ascii_lowercase, k=needed))

    # 1. Check if the 8-letter candidate is already unique
    if not User.query.filter_by(username=candidate).first():
        return candidate

    # 2. Try replacing last N characters with digits (N starting from 1 up to 7)
    for n in range(1, 8):
        prefix = candidate[:-n]
        max_val = 10**n
        fmt = f"0{n}d"
        for i in range(max_val):
            suffix = f"{i:{fmt}}"
            username = prefix + suffix
            if not User.query.filter_by(username=username).first():
                return username

    return candidate


def process_member_file(file_bytes, ext, club_id):
    """
    Processes a CSV or XLSX byte content to import members or invite existing users.

    Returns a report dict:
        {
            'added':    [{'fullname': ..., 'username': ..., 'email': ...}, ...],
            'invited':  [{'fullname': ..., 'username': ..., 'email': ...}, ...],
            'failed':   [string, ...]   # one human-readable error per row
        }
    """
    report = {'added': [], 'invited': [], 'failed': []}

    club = db.session.get(Club, club_id)
    if not club:
        report['failed'].append("Invalid club ID.")
        return report

    rows = []
    if ext == 'csv':
        try:
            stream = io.StringIO(file_bytes.decode("UTF8"), newline=None)
            csv_reader = csv.reader(stream)
            all_rows = list(csv_reader)
            if not all_rows:
                report['failed'].append("The file is empty.")
                return report
            headers = all_rows[0]
            if not validate_headers(headers):
                report['failed'].append("Invalid column headers. Expected: Fullname*, Username, Member Number, Email*, Phone, Mentor Name.")
                return report
            rows = all_rows[1:] # Skip header row
        except Exception as e:
            report['failed'].append(f"Failed to parse CSV: {str(e)}")
            return report
    elif ext == 'xlsx':
        try:
            stream = io.BytesIO(file_bytes)
            wb = openpyxl.load_workbook(stream, data_only=True)
            sheet = wb.active
            all_rows = list(sheet.iter_rows(values_only=True))
            if not all_rows:
                report['failed'].append("The file is empty.")
                return report
            headers = all_rows[0]
            if not validate_headers(headers):
                report['failed'].append("Invalid column headers. Expected: Fullname*, Username, Member Number, Email*, Phone, Mentor Name.")
                return report
            rows = [list(r) for r in all_rows[1:]]
        except Exception as e:
             report['failed'].append(f"Failed to parse XLSX: {str(e)}")
             return report
    else:
        report['failed'].append(f"Unsupported file extension: {ext}")
        return report

    imported_emails = set()
    imported_usernames = set()
    imported_phones = set()
    imported_member_ids = set()

    for row in rows:
        # Check if row is completely empty
        if not row or len([x for x in row if x is not None and str(x).strip() != '']) == 0:
            continue

        # Normalize row to ensure we have at least 6 elements, converting all to string
        row_str = [str(x).strip() if x is not None else "" for x in row]
        fullname, username, member_id, email, phone, mentor_name = (row_str + [""]*6)[:6]

        # Field Validations
        errors = []
        if not fullname:
            errors.append("Fullname is required")
        elif len(fullname) > 100:
            errors.append("Fullname cannot exceed 100 characters")

        if username:
            if len(username) > 50:
                errors.append("Username cannot exceed 50 characters")
            if not re.fullmatch(r'[A-Za-z0-9_]+', username):
                errors.append("Username must contain only letters, digits, and underscores")

        if not email:
            errors.append("Email is required")
        else:
            if len(email) > 120:
                errors.append("Email cannot exceed 120 characters")
            if not re.fullmatch(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', email):
                errors.append(f"Invalid email format: '{email}'")

        if member_id:
            if len(member_id) > 50:
                errors.append("Member Number / ID cannot exceed 50 characters")
            if not re.fullmatch(r'PN-\d+', member_id):
                errors.append(f"Invalid Member Number format: '{member_id}'. Expected format is PN-nnnnn")

        if mentor_name and len(mentor_name) > 100:
            errors.append("Mentor Name cannot exceed 100 characters")

        if phone:
            if len(phone) > 50:
                errors.append("Phone cannot exceed 50 characters")
            if not re.fullmatch(r'[\d\s+\-().]*', phone):
                errors.append(f"Invalid phone format: '{phone}'")

        if errors:
            report['failed'].append(
                f"Row error: {', '.join(errors)}. Row: {row_str}")
            continue

        # File-level Duplication Checks
        if email and email in imported_emails:
            report['failed'].append(f"Row error: Email '{email}' is duplicated in the uploaded file. Row: {row_str}")
            continue
        if username and username in imported_usernames:
            report['failed'].append(f"Row error: Username '{username}' is duplicated in the uploaded file. Row: {row_str}")
            continue
        if phone and phone in imported_phones:
            report['failed'].append(f"Row error: Phone '{phone}' is duplicated in the uploaded file. Row: {row_str}")
            continue
        if member_id and member_id in imported_member_ids:
            report['failed'].append(f"Row error: Member Number '{member_id}' is duplicated in the uploaded file. Row: {row_str}")
            continue

        # Database global checks for existing user
        existing_user = None
        if email:
            existing_user = User.query.filter_by(email=email).first()
        if not existing_user and username:
            existing_user = User.query.filter_by(username=username).first()

        is_invite = False
        if existing_user:
            # Check if this user is already a member of the target club
            is_member = UserClub.query.filter_by(user_id=existing_user.id, club_id=club_id).first()
            if is_member:
                report['failed'].append(
                    f"Skipping '{fullname}': User '{existing_user.username}' is already a member of this club.")
                continue
            is_invite = True

        # Database target-club checks for existing contact
        existing_contact = None
        if email:
            existing_contact = Contact.query.join(ContactClub).filter(
                ContactClub.club_id == club_id,
                Contact.Email == email
            ).first()
        if not existing_contact and phone:
            existing_contact = Contact.query.join(ContactClub).filter(
                ContactClub.club_id == club_id,
                Contact.Phone_Number == phone
            ).first()
        if not existing_contact and member_id:
            existing_contact = Contact.query.join(ContactClub).filter(
                ContactClub.club_id == club_id,
                Contact.Member_ID == member_id
            ).first()

        contact_id = None
        if existing_contact:
            # Check if this contact in the club is already associated with any user
            linked_uc = UserClub.query.filter_by(contact_id=existing_contact.id, club_id=club_id).first()
            if linked_uc:
                report['failed'].append(
                    f"Skipping '{fullname}': Contact already linked to an existing user in this club.")
                continue
            contact_id = existing_contact.id

        # Generate username if blank (only for new users)
        if not username and not is_invite:
            username = generate_username(fullname)

        # For tracking/duplicate checks, use the resolved username and email
        resolved_username = existing_user.username if is_invite else username
        resolved_email = existing_user.email if is_invite else email

        # Track fields to avoid duplicates within same file
        if resolved_email:
            imported_emails.add(resolved_email)
        if resolved_username:
            imported_usernames.add(resolved_username)
        if phone:
            imported_phones.add(phone)
        if member_id:
            imported_member_ids.add(member_id)

        # If new user, create them; if existing user, link/invite them
        from app.models import AuthRole
        user_role = AuthRole.query.filter_by(name='Member').first()
        role_id = user_role.id if user_role else None

        if is_invite:
            try:
                # 1. Create invitation message
                sender_name = current_user.display_name if (current_user and current_user.is_authenticated) else "System"
                sender_id = current_user.id if (current_user and current_user.is_authenticated) else 1
                msg = Message(
                    sender_id=sender_id,
                    recipient_id=existing_user.id,
                    subject=f"Invitation to join {club.club_name}",
                    body=f"Hello {existing_user.first_name or fullname},\n\n{sender_name} has invited you to join **{club.club_name}**.\n\nPlease respond using the buttons below.\n[CLUB_ID:{club_id}]"
                )
                db.session.add(msg)

                report['invited'].append({
                    'fullname': fullname,
                    'username': resolved_username,
                    'email': resolved_email or '',
                })
            except Exception as e:
                report['failed'].append(
                    f"Failed to invite '{fullname}' ({resolved_username}): {str(e)}")
        else:
            try:
                user_kwargs = {
                    'username': resolved_username,
                    'email': resolved_email if resolved_email else None,
                    'full_name': fullname,
                    'role_id': role_id,
                    'contact_id': contact_id,
                    'club_id': club_id,
                    'phone': phone if phone else None
                }
                user_kwargs['password'] = 'toastmasters'

                user = _save_user_data(
                    user=None,
                    **user_kwargs
                )

                # Update contact record with additional fields (mentor, member_id, home_club)
                if user:
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
                            # Set display club to this club
                            if not contact_record.display_club_name:
                                contact_record.display_club_name = club.club_name

                report['added'].append({
                    'fullname': fullname,
                    'username': resolved_username,
                    'email': resolved_email or '',
                })
            except Exception as e:
                report['failed'].append(
                    f"Failed to create '{fullname}' ({resolved_username}): {str(e)}")

    db.session.commit()
    return report
