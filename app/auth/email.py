from flask import render_template, current_app, url_for
from flask_mail import Message
from .. import mail
import time

def _send_mail_with_retry(msg, retries=3, delay=2):
    """Sends email with retry logic to mitigate transient network/SSL EOF issues."""
    for attempt in range(retries):
        try:
            mail.send(msg)
            return True
        except Exception as e:
            print(f"DEBUG: SMTP send attempt {attempt + 1} failed: {e}")
            if attempt == retries - 1:
                raise e
            time.sleep(delay)

def send_reset_email(user):
    token = user.get_reset_token()
    msg = Message('Password Reset Request',
                  sender=current_app.config['MAIL_DEFAULT_SENDER'],
                  recipients=[user.email])
    
    # We'll use a simple string body for now to ensure it works, or a template if available.
    # Plan calls for reset_password.html template.
    
    reset_url = url_for('auth_bp.reset_token', token=token, _external=True)
    
    msg.body = f'''To reset your password, visit the following link:
{reset_url}

If you did not make this request then simply ignore this email and no changes will be made.
'''
    # Start with text only for simplicity, can add html later if needed or if template created.
    # If we want to use the template immediately:
    # msg.html = render_template('auth/reset_password.html', user=user, token=token)
    
    # For now, let's stick to the text body or just log it if mail server not configured.
    # But usually mail.send(msg) is what we want.
    
    # NOTE: Since we are in development and might not have a real mail server, 
    # printing to console is helpful.
    print(f"DEBUG: Password Reset Link for {user.username}: {reset_url}")
    
    try:
        _send_mail_with_retry(msg)
    except Exception as e:
        print(f"Error sending email: {e}")
        # Make sure to re-raise or handle appropriately if email is critical.
        # usually we don't want to crash the app, but user needs to know.
        raise e

def send_verification_email(user):
    token = user.get_verification_token()
    msg = Message('Verify Your Email Address',
                  sender=current_app.config['MAIL_DEFAULT_SENDER'],
                  recipients=[user.email])
    
    verify_url = url_for('auth_bp.verify_email', token=token, _external=True)
    
    msg.body = f'''Hello {user.username},
    
Please click on the following link to verify your email address and activate your account:
{verify_url}

If you did not register for an account, please ignore this email.
'''
    print(f"DEBUG: Email Verification Link for {user.username}: {verify_url}")
    
    try:
        _send_mail_with_retry(msg)
    except Exception as e:
        print(f"Error sending email: {e}")
        raise e
