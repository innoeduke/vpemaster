from app import db
from app.models.message import Message
from app.models.user import User

def send_system_message(recipient_id, subject, body):
    """
    Send a system message to a specific user.
    System messages have sender_id=None.
    """
    recipient = db.session.get(User, recipient_id)
    if not recipient:
        return False, "Recipient not found"
        
    msg = Message(
        sender_id=None,
        recipient_id=recipient_id,
        subject=subject,
        body=body
    )
    
    try:
        db.session.add(msg)
        db.session.commit()
        return True, "Message sent"
    except Exception as e:
        db.session.rollback()
        return False, str(e)

def broadcast_system_message(subject, body, exclude_users=None):
    """
    Send a system message to ALL users.
    """
    if exclude_users is None:
        exclude_users = []
        
    users = User.query.filter(User.Status == 'active').all() # Example filter
    count = 0
    
    for user in users:
        if user.id in exclude_users:
            continue
            
        msg = Message(
            sender_id=None,
            recipient_id=user.id,
            subject=subject,
            body=body
        )
        db.session.add(msg)
        count += 1
        
    try:
        db.session.commit()
        return True, f"Broadcast sent to {count} users"
    except Exception as e:
        db.session.rollback()
        return False, str(e)
