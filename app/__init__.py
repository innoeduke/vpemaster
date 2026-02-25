from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import MetaData
from flask_migrate import Migrate
from flask_bcrypt import Bcrypt

import os


# 1. Create extension instances WITHOUT an app
# They will be "connected" to the app inside the factory

# Define naming convention for SQLAlchemy
convention = {
    "ix": 'ix_%(column_0_label)s',
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}
metadata = MetaData(naming_convention=convention)

db = SQLAlchemy(metadata=metadata)
bcrypt = Bcrypt()
migrate = Migrate()
from flask_mail import Mail
mail = Mail()
from .assets import assets
from flask_caching import Cache
cache = Cache()


from flask_login import LoginManager
login_manager = LoginManager()
login_manager.login_view = 'auth_bp.login'
login_manager.login_message_category = 'info'

from flask_principal import Principal, Identity, AnonymousIdentity, identity_loaded
principal = Principal()


def create_app(config_class='config.Config'):
    """
    Application Factory Function
    """

    app = Flask(__name__, instance_relative_config=True)

    # Load configuration from the config.py file
    app.config.from_object(config_class)

    # (Optional) Load instance-specific config, e.g., /instance/config.py
    # app.config.from_pyfile('config.py', silent=True)

    db.init_app(app)
    bcrypt.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    principal.init_app(app)
    mail.init_app(app)
    assets.init_app(app)
    cache.init_app(app)
    
    # Set up identity loader for Flask-Principal
    from flask_login import user_loaded_from_request, user_loaded_from_cookie, user_logged_in
    from flask_principal import identity_changed, RoleNeed, UserNeed
    
    @user_logged_in.connect_via(app)
    @user_loaded_from_cookie.connect_via(app)
    @user_loaded_from_request.connect_via(app)
    def on_user_loaded(sender, user, **extra):
        """Load user identity when user logs in."""
        identity_changed.send(sender, identity=Identity(user.id))
    
    @identity_loaded.connect_via(app)
    def on_identity_loaded(sender, identity):
        """Load user permissions into identity."""
        from .models import User
        
        # Set the identity user object
        identity.user = db.session.get(User, identity.id)
        
        if identity.user:
            # Add UserNeed
            identity.provides.add(UserNeed(identity.id))
            
            # Add role needs
            for role in identity.user.roles:
                identity.provides.add(RoleNeed(role.name))
            
            # Add permission needs
            for permission_name in identity.user.get_permissions():
                identity.provides.add(('permission', permission_name))

    # Register context processors
    from .auth.utils import is_authorized

    @app.context_processor
    def inject_global_vars():
        from .models import Meeting, Club
        from .auth.permissions import Permissions
        from .club_context import get_or_set_default_club, get_current_club_id
        
        # Ensure club context is initialized
        club_id = get_or_set_default_club()
        
        # Get current club object
        club = db.session.get(Club, club_id) if club_id else None
        
        # Check if at least one meeting exists for this club
        has_meetings = False
        if club_id:
            has_meetings = db.session.query(Meeting.id).filter(Meeting.club_id == club_id).first() is not None
            
        return dict(
            is_authorized=is_authorized,
            has_meetings=has_meetings,
            Permissions=Permissions,
            club=club,
            get_current_club_id=get_current_club_id
        )

    # Register Blueprints
    # Imports are *inside* the factory to avoid circular import issues
    with app.app_context():
        from .agenda_routes import agenda_bp
        from .contacts_routes import contacts_bp
        from .speech_logs_routes import speech_logs_bp
        from .users_routes import users_bp
        from .main_routes import main_bp
        from .auth.routes import auth_bp
        from .pathways_routes import pathways_bp
        from .settings_routes import settings_bp
        from .booking_routes import booking_bp
        from .voting_routes import voting_bp
        from .tools_routes import tools_bp
        from .achievements_routes import achievements_bp
        from .roster_routes import roster_bp
        from .lucky_draw_routes import lucky_draw_bp
        from .planner_routes import planner_bp

        # Import models so SQLAlchemy knows about them
        from . import models

        app.register_blueprint(agenda_bp)
        app.register_blueprint(auth_bp)
        app.register_blueprint(contacts_bp)
        app.register_blueprint(speech_logs_bp)
        app.register_blueprint(users_bp)
        app.register_blueprint(main_bp)
        app.register_blueprint(pathways_bp)
        app.register_blueprint(settings_bp)
        app.register_blueprint(booking_bp)
        app.register_blueprint(voting_bp)
        app.register_blueprint(tools_bp, url_prefix='/tools')
        app.register_blueprint(roster_bp, url_prefix='/roster')
        app.register_blueprint(lucky_draw_bp, url_prefix='/lucky_draw')
        from .clubs_routes import clubs_bp
        app.register_blueprint(clubs_bp)
        app.register_blueprint(achievements_bp)
        from .messages_routes import messages_bp
        app.register_blueprint(messages_bp)
        app.register_blueprint(planner_bp)
        from .about_club_routes import about_club_bp
        app.register_blueprint(about_club_bp)

    # Register CLI commands
    from app.commands.create_admin import create_admin
    from app.commands.import_data import import_data, fix_home_club_command
    from app.commands.manage_metadata import metadata
    from app.commands.cleanup_data import cleanup_data
    from app.commands.create_club import create_club
    from app.commands.pack_unpack import pack, unpack

    app.cli.add_command(create_admin)
    app.cli.add_command(import_data)
    app.cli.add_command(metadata)
    app.cli.add_command(cleanup_data)
    app.cli.add_command(create_club)
    app.cli.add_command(fix_home_club_command)
    app.cli.add_command(pack)
    app.cli.add_command(unpack)


    # 7. Return the configured app instance
    return app
