from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_bcrypt import Bcrypt

import os


# 1. Create extension instances WITHOUT an app
# They will be "connected" to the app inside the factory
db = SQLAlchemy()
bcrypt = Bcrypt()
migrate = Migrate()
from flask_mail import Mail
mail = Mail()
from .assets import assets

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
    
    # Set up identity loader for Flask-Principal
    from flask_login import user_loaded_from_request, user_loaded_from_cookie
    from flask_principal import identity_changed, RoleNeed, UserNeed
    
    @user_loaded_from_cookie.connect_via(app)
    @user_loaded_from_request.connect_via(app)
    def on_user_loaded(sender, user):
        """Load user identity when user logs in."""
        identity_changed.send(sender, identity=Identity(user.id))
    
    @identity_loaded.connect_via(app)
    def on_identity_loaded(sender, identity):
        """Load user permissions into identity."""
        from .models import User
        
        # Set the identity user object
        identity.user = User.query.get(identity.id)
        
        if identity.user:
            # Add UserNeed
            identity.provides.add(UserNeed(identity.id))
            
            # Add role needs
            for role in identity.user.roles:
                identity.provides.add(RoleNeed(role.name))
            
            # Add permission needs
            for permission_name in identity.user.get_permissions():
                from flask_principal import Permission as PrincipalPermission
                identity.provides.add(('permission', permission_name))

    # Register context processors
    from .auth.utils import is_authorized

    @app.context_processor
    def inject_global_vars():
        from .models import Meeting
        # Check if at least one meeting exists
        has_meetings = db.session.query(Meeting.id).first() is not None
        return dict(
            is_authorized=is_authorized,
            has_meetings=has_meetings
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
        from .roster_routes import roster_bp
        from .lucky_draw_routes import lucky_draw_bp
        from .achievements_routes import achievements_bp

        # Import models so SQLAlchemy knows about them
        from . import models
        from .utils import load_all_settings, get_meeting_types

        all_settings = load_all_settings()
        meeting_types = get_meeting_types(all_settings)
        if meeting_types:
            app.config['MEETING_TYPES'] = meeting_types

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
        app.register_blueprint(roster_bp, url_prefix='/roster')
        app.register_blueprint(lucky_draw_bp, url_prefix='/lucky_draw')
        app.register_blueprint(achievements_bp)

    # Register CLI commands
    from scripts.create_admin import create_admin
    app.cli.add_command(create_admin)

    # 7. Return the configured app instance
    return app
