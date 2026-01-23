import sqlite3
import re
import os
from datetime import datetime
from flask import current_app
from app.models.base import db
from app.models.contact import Contact
from app.models.user import User
from app.models.club import Club
from app.models.user_club import UserClub
from app.models.contact_club import ContactClub
from app.models.role import Role
# Import other necessary models as we need them

class LegacyMigrationService:
    def __init__(self, sql_path, target_club_id):
        self.sql_path = sql_path
        self.target_club_id = target_club_id
        self.conn = None
        self.cursor = None
        self._contact_id_map = {}  # v1_id -> v2_id
        self._meeting_id_map = {}  # v1_meeting_number -> v2_id (Meeting Number is the unique key)

    def load_v1_data(self):
        """Loads the V1 SQL dump into an in-memory SQLite database."""
        if not os.path.exists(self.sql_path):
            raise FileNotFoundError(f"SQL dump not found at {self.sql_path}")

        print("Creating in-memory SQLite database...")
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

        print("Sanitizing and executing SQL dump...")
        with open(self.sql_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()

        # Sanitize SQL for SQLite compatibility
        # 1. Remove LOCK TABLES / UNLOCK TABLES
        sql_content = re.sub(r'LOCK TABLES `\w+` WRITE;', '', sql_content)
        sql_content = re.sub(r'UNLOCK TABLES;', '', sql_content)
        
        # 2. Remove ENGINE=InnoDB and charset stuff at end of CREATE TABLE
        sql_content = re.sub(r'ENGINE=InnoDB.*?;', ';', sql_content)
        sql_content = re.sub(r'DEFAULT CHARSET=.*?;', ';', sql_content)
        
        # 3. Remove MySQL specific integer display widths (e.g. int(11))
        sql_content = re.sub(r'int\(\d+\)', 'integer', sql_content)
        
        # 4. Handle enum (replace with text/varchar)
        sql_content = re.sub(r"enum\(.*?\)", "text", sql_content)
        
        # 5. Remove 'UNSIGNED'
        sql_content = re.sub(r'UNSIGNED', '', sql_content, flags=re.IGNORECASE)
        
        # 6. Remove ON UPDATE CURRENT_TIMESTAMP
        sql_content = re.sub(r'ON UPDATE CURRENT_TIMESTAMP', '', sql_content, flags=re.IGNORECASE)

        # 7. Replace MySQL escape slashes if necessary (SQLite can handle standard SQL, but mysqldump often uses \')
        # This might be tricky, let's hope standard execute script handles it or minimal escaping is used.
        # SQLite uses '' for escaping single quotes, MySQL uses \' often. 
        # Using a simplistic replace for now:
        sql_content = sql_content.replace("\\'", "''")
        
        # Split into statements, cautiously, or just use executescript
        try:
            self.cursor.executescript(sql_content)
            self.conn.commit()
            print("Legacy data loaded into memory successfully.")
        except Exception as e:
            print(f"Error executing SQL script: {e}")
            raise

    def migrate_all(self):
        """Orchestrates the migration process."""
        try:
            self.load_v1_data()
            
            print("Migrating Contacts...")
            self.migrate_contacts()
            
            print("Migrating Users...")
            self.migrate_users()
            
            print("Migrating Meetings...")
            self.migrate_meetings()
            
            print("Migrating Roster...")
            self.migrate_roster()
            
            print("Migrating Votes...")
            self.migrate_votes()
            
            db.session.commit()
            print("Migration completed successfully!")
            
        finally:
            if self.conn:
                self.conn.close()

    def migrate_contacts(self):
        """Migrate contacts from v1 Contacts table."""
        rows = self.cursor.execute("SELECT * FROM `Contacts`").fetchall()
        
        for row in rows:
            v1_id = row['id']
            name = row['Name']
            email = row['Email']
            
            # Name splitting
            first_name = None
            last_name = None
            if name:
                parts = name.strip().split(' ', 1)
                first_name = parts[0]
                last_name = parts[1] if len(parts) > 1 else ''

            # Try to find existing contact in this club context
            # Strategy: Match by Name OR Email within the target club
            existing_contact = None
            
            # 1. Try Email match first if available
            if email:
                existing_contact = Contact.query.join(ContactClub).filter(
                    ContactClub.club_id == self.target_club_id,
                    Contact.Email == email
                ).first()
            
            # 2. Try Name match
            if not existing_contact:
                existing_contact = Contact.query.join(ContactClub).filter(
                    ContactClub.club_id == self.target_club_id,
                    Contact.Name == name
                ).first()
            
            if existing_contact:
                print(f"Updating existing contact: {name} (ID: {existing_contact.id})")
                # Update logic (merging fields if empty?)
                # For now, we update specific fields if they are present in legacy
                if not existing_contact.first_name: existing_contact.first_name = first_name
                if not existing_contact.last_name: existing_contact.last_name = last_name
                if not existing_contact.Email: existing_contact.Email = email
                # Map ID
                self._contact_id_map[v1_id] = existing_contact.id
            else:
                print(f"Creating new contact: {name}")
                new_contact = Contact(
                    Name=name,
                    first_name=first_name,
                    last_name=last_name,
                    Email=email,
                    # Map other columns if they match v1 -> v2 names
                    Member_ID=row['Member_ID'] if 'Member_ID' in row.keys() else None,
                    Type=row['Type'] if 'Type' in row.keys() else 'Guest',
                    Phone_Number=row['Phone_Number'] if 'Phone_Number' in row.keys() else None,
                    Bio=row['Bio'] if 'Bio' in row.keys() else None
                )
                db.session.add(new_contact)
                db.session.flush() # Get ID
                
                # Link to Club
                cc = ContactClub(contact_id=new_contact.id, club_id=self.target_club_id)
                db.session.add(cc)
                
                self._contact_id_map[v1_id] = new_contact.id

        db.session.commit()

    def migrate_users(self):
        """Migrate users and map roles."""
        users = self.cursor.execute("SELECT * FROM `Users`").fetchall()
        
        # Load map of v1 user_id -> list[role_name/level]
        # v1 auth_roles: 1=Admin(8), 2=Operator(4), 3=Staff(2), 4=User(1)
        role_map = {
            1: 'SysAdmin', # or ClubAdmin based on plan
            2: 'ClubAdmin',
            3: 'Staff',
            4: 'User'
        }
        
        user_roles_v1 = {}
        try:
            ur_rows = self.cursor.execute("SELECT * FROM `user_roles`").fetchall()
            for ur in ur_rows:
                uid = ur['user_id']
                rid = ur['role_id']
                if uid not in user_roles_v1:
                    user_roles_v1[uid] = []
                user_roles_v1[uid].append(role_map.get(rid, 'User'))
        except Exception:
            print("Warning: Could not read user_roles table. Skipping role mapping.")

        for user_row in users:
            username = user_row['username']
            email = user_row['email']
            v1_uid = user_row['id']
            
            # Check exist
            user = User.query.filter((User.username == username) | (User.email == email)).first()
            
            if not user:
                print(f"Creating user: {username}")
                # Handle potential missing Created_At
                created_at = None
                if user_row['created_at']:
                    try:
                        created_at = datetime.strptime(user_row['created_at'], '%Y-%m-%d %H:%M:%S')
                    except:
                        try:
                           created_at = datetime.strptime(user_row['created_at'], '%Y-%m-%d') 
                        except:
                            pass

                user = User(
                    username=username,
                    email=email,
                    password_hash=user_row['password_hash'], # Assuming compatible hash or reset needed
                    created_at=created_at,
                    status=user_row['status'] if 'status' in user_row.keys() else 'active'
                )
                db.session.add(user)
                db.session.flush()
            
            # Link to Club and Assign Role
            # Determine highest role level from v1 for this club
            roles = user_roles_v1.get(v1_uid, ['User'])
            
            # Calculate v2 bitmask
            # Admin(8) -> ClubAdmin in v2 context
            # Operator(4) -> ClubAdmin
            # Staff(2) -> Staff
            # User(1) -> Member
            
            target_mask = 0
            
            # Fetch v2 Role objects to get correct levels
            # Permissions.CLUBADMIN etc are defined in code, we need to query DB or use constants if available
            # Let's simple-query
            role_objects = {r.name: r for r in Role.query.all()}
            
            for rname in roles:
                if rname == 'SysAdmin': 
                    # If we trust the dump, map to ClubAdmin for safety, or prompt. 
                    # Plan says: Map to ClubAdmin for target club.
                    r_obj = role_objects.get('ClubAdmin')
                    if r_obj: target_mask |= r_obj.level
                elif rname == 'ClubAdmin':
                    r_obj = role_objects.get('ClubAdmin')
                    if r_obj: target_mask |= r_obj.level
                elif rname == 'Staff':
                    r_obj = role_objects.get('Staff')
                    if r_obj: target_mask |= r_obj.level
                elif rname == 'User':
                    r_obj = role_objects.get('User') # Usually 'User' or 'Member'? v2 default is 'User' role usually level 1
                    if r_obj: target_mask |= r_obj.level
            
            # Ensure at least 'User' level
            if target_mask == 0:
                 r_obj = role_objects.get('User')
                 if r_obj: target_mask = r_obj.level

            user.set_club_role(self.target_club_id, target_mask)
            
            # Link user to contact if possible
            # Logic: If this user matches a contact we just migrated (by name/email), link them in UserClub
            # The User.ensure_contact method does exactly this logic!
            user.ensure_contact(club_id=self.target_club_id)
            
        db.session.commit()

    def migrate_meetings(self):
        """Migrate Meetings table."""
        pass # To be implemented

    def migrate_roster(self):
        """Migrate Roster table."""
        pass # To be implemented
        
    def migrate_votes(self):
        """Migrate Votes table."""
        pass # To be implemented
