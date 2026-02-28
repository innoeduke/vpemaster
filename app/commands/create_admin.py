import click
from flask.cli import with_appcontext
from app import db
from app.models import User, Contact, Club, UserClub, ContactClub, AuthRole


@click.command('create-admin')
@click.option('--username', prompt=True, help='Admin username')
@click.option('--email', prompt=True, help='Admin email')
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, help='Admin password')
@click.option('--contact-name', default=None, help='Contact name (defaults to username)')
@click.option('--club-no', default='000001', help='Club number (defaults to "000001")')
@with_appcontext
def create_admin(username, email, password, contact_name, club_no):
    """Create an admin user with associated contact."""
    
    # Paranoid Input Cleaning (Apply immediately)
    username = str(username).strip()
    email = str(email).strip().lower() # Ensure email is lowercase
    if contact_name:
        contact_name = str(contact_name).strip()
    
    # Check if user already exists
    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        click.echo(f"❌ Error: User '{username}' already exists.", err=True)
        return
    
    # Check if email already exists
    # Fix: User model uses lowercase 'email'
    existing_email = User.query.filter_by(email=email).first()
    if existing_email:
        click.echo(f"❌ Error: Email '{email}' is already in use.", err=True)
        return
    
    try:
        # Use username as contact name if not provided
        if not contact_name:
            contact_name = username
        
        # SysAdmin role is no longer used in the database.
        # Administrative powers are restricted to the 'sysadmin' account.
        if username != 'sysadmin':
            click.echo("⚠️  Warning: Global administrative powers are only granted to the 'sysadmin' account.", err=True)

        # Validate Club or Create Gossip
        club_obj = None
        if club_no:
            club_obj = Club.query.filter_by(club_no=club_no).first()
            if not club_obj:
               click.echo(f"⚠️  Warning: Club with number '{club_no}' not found. Falling back to default logic.", err=True)
        
        if not club_obj:
            club_obj = Club.query.first()
            
        if not club_obj:
            # Create Gossip club if no clubs exist
            click.echo("ℹ️ No clubs found. Creating default 'Gossip' club...", err=True)
            from datetime import date
            club_obj = Club(
                club_name='Gossip',
                club_no='000000',
                district='00',
                founded_date=date.today()
            )
            db.session.add(club_obj)
            db.session.flush()

        # Generate a unique Member_ID for admin
        admin_count = User.query.filter(User.username.like('admin%')).count()
        member_id = f"ADMIN{admin_count + 1:03d}"
        
        # Create contact first
        contact = Contact(
            Name=contact_name,
            Email=email, # Contact uses Capitalized Email
            Type='Member',
            Member_ID=member_id,
            Completed_Paths=''
        )
        db.session.add(contact)
        db.session.flush()  # Get the contact ID
        

        # Create admin user
        admin = User(
            username=username,
            email=email,
            status='active'
        )
        
        admin.set_password(password)
        # Note: admin.add_role(sysadmin_role) is unnecessary/ineffective as User.roles is view-only derived from UserClub
        db.session.add(admin)
        db.session.flush() # Get user ID
        
        # Create UserClub linkage
        # We assign level 4 (ClubAdmin) as a base for the sysadmin account in this club
        # although they have global powers anyway.
        uc = UserClub(
            user_id=admin.id,
            club_id=club_obj.id,
            contact_id=contact.id,
            is_home=True,
            club_role_level=4 # Assign ClubAdmin level
        )
        db.session.add(uc)

        # Create ContactClub linkage
        cc = ContactClub(
            contact_id=contact.id,
            club_id=club_obj.id
        )
        db.session.add(cc)
        
        # Commit the transaction
        db.session.commit()
        
        click.echo(f"✅ Admin user '{admin.username}' created successfully!")
        click.echo(f"   Email: {email}")
        click.echo(f"   Contact: {contact_name}")
        click.echo(f"   Member ID: {member_id}")
        click.echo(f"   Club: {club_obj.club_name}")
        
    except Exception as e:
        db.session.rollback()
        click.echo(f"❌ Error creating admin user: {str(e)}", err=True)
        raise
