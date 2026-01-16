import click
from flask.cli import with_appcontext
from app import db
from app.models import User, Contact


@click.command('create-admin')
@click.option('--username', prompt=True, help='Admin username')
@click.option('--email', prompt=True, help='Admin email')
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, help='Admin password')
@click.option('--contact-name', default=None, help='Contact name (defaults to username)')
@click.option('--club', default='', help='Club name (defaults to "")')
@with_appcontext
def create_admin(username, email, password, contact_name, club):
    """Create an admin user with associated contact."""
    
    # Check if user already exists
    existing_user = User.query.filter_by(Username=username).first()
    if existing_user:
        click.echo(f"❌ Error: User '{username}' already exists.", err=True)
        return
    
    # Check if email already exists
    existing_email = User.query.filter_by(Email=email).first()
    if existing_email:
        click.echo(f"❌ Error: Email '{email}' is already in use.", err=True)
        return
    
    try:
        # Use username as contact name if not provided
        if not contact_name:
            contact_name = username
        
        # Get SysAdmin role
        from app.models import AuthRole
        sysadmin_role = AuthRole.query.filter_by(name='SysAdmin').first()
        if not sysadmin_role:
            click.echo("❌ Error: 'SysAdmin' role not found in database. Please run seed data first.", err=True)
            return

        # Generate a unique Member_ID for admin
        admin_count = User.query.join(User.roles).filter(AuthRole.name == 'SysAdmin').count()
        member_id = f"ADMIN{admin_count + 1:03d}"
        
        # Create contact first
        contact = Contact(
            Name=contact_name,
            Email=email,
            Type='Member',
            Club=club,
            Member_ID=member_id,
            Completed_Paths=''
        )
        db.session.add(contact)
        db.session.flush()  # Get the contact ID
        
        # Create admin user
        admin = User(
            Username=username,
            Email=email,
            Status='active',
            Contact_ID=contact.id
        )
        admin.set_password(password)
        admin.add_role(sysadmin_role)
        db.session.add(admin)
        
        # Commit the transaction
        db.session.commit()
        
        click.echo(f"✅ Admin user '{username}' created successfully!")
        click.echo(f"   Email: {email}")
        click.echo(f"   Contact: {contact_name}")
        click.echo(f"   Member ID: {member_id}")
        click.echo(f"   Club: {club}")
        
    except Exception as e:
        db.session.rollback()
        click.echo(f"❌ Error creating admin user: {str(e)}", err=True)
        raise
