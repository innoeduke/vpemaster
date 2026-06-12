from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, Response, stream_with_context
from flask_login import login_required, current_user
from app import db
from app.models.message import Message
from app.models.user import User
from datetime import datetime
import queue

messages_bp = Blueprint('messages', __name__)

class MessageAnnouncer:
    def __init__(self):
        self.listeners = {} # user_id -> list of queues

    def listen(self, user_id):
        q = queue.Queue(maxsize=5)
        if user_id not in self.listeners:
            self.listeners[user_id] = []
        self.listeners[user_id].append(q)
        return q

    def announce(self, user_id, message):
        if user_id in self.listeners:
            for q in self.listeners[user_id]:
                try:
                    q.put_nowait(message)
                except queue.Full:
                    pass

    def remove_listener(self, user_id, q):
        if user_id in self.listeners:
            if q in self.listeners[user_id]:
                self.listeners[user_id].remove(q)
            if not self.listeners[user_id]:
                del self.listeners[user_id]

announcer = MessageAnnouncer()

@messages_bp.route('/messages')
@login_required
def messages():
    """Render the main messages page."""
    return render_template('messages.html', title='Messages')

@messages_bp.route('/api/messages/inbox')
@login_required
def get_inbox():
    """Get inbox messages."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    per_page = max(1, min(100, per_page))
    messages = current_user.messages_received.filter(
        Message.deleted_by_recipient == False
    ).order_by(Message.timestamp.desc()).paginate(
        page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'messages': [{
            'id': m.id,
            'sender': m.sender.display_name if m.sender else 'System',
            'sender_id': m.sender_id,
            'subject': m.subject,
            'body': m.body,
            'timestamp': m.timestamp.strftime('%Y-%m-%d %H:%M'),
            'read': m.read,
            'avatar_url': m.sender.full_avatar_url if m.sender else None
        } for m in messages.items],
        'total': messages.total,
        'pages': messages.pages,
        'current_page': page
    })

@messages_bp.route('/api/messages/sent')
@login_required
def get_sent():
    """Get sent messages."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    per_page = max(1, min(100, per_page))
    messages = current_user.messages_sent.filter(
        Message.deleted_by_sender == False
    ).order_by(Message.timestamp.desc()).paginate(
        page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'messages': [{
            'id': m.id,
            'recipient': m.recipient.display_name,
            'recipient_id': m.recipient_id,
            'subject': m.subject,
            'body': m.body,
            'timestamp': m.timestamp.strftime('%Y-%m-%d %H:%M'),
            'read': m.read,
            'avatar_url': m.recipient.full_avatar_url if m.recipient else None
        } for m in messages.items],
        'total': messages.total,
        'pages': messages.pages,
        'current_page': page
    })

@messages_bp.route('/api/messages/trash')
@login_required
def get_trash():
    """Get trash messages."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    per_page = max(1, min(100, per_page))
    from sqlalchemy import or_
    messages = Message.query.filter(
        or_(
            (Message.recipient_id == current_user.id) & (Message.deleted_by_recipient == True) & (Message.permanently_deleted_by_recipient == False),
            (Message.sender_id == current_user.id) & (Message.deleted_by_sender == True) & (Message.permanently_deleted_by_sender == False)
        )
    ).order_by(Message.timestamp.desc()).paginate(
        page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'messages': [{
            'id': m.id,
            'sender': m.sender.display_name if m.sender else 'System',
            'sender_id': m.sender_id,
            'recipient': m.recipient.display_name,
            'recipient_id': m.recipient_id,
            'subject': m.subject,
            'body': m.body,
            'timestamp': m.timestamp.strftime('%Y-%m-%d %H:%M'),
            'read': m.read,
            'avatar_url': (m.sender.full_avatar_url if m.sender else None) if m.recipient_id == current_user.id else (m.recipient.full_avatar_url if m.recipient else None),
            'type': 'inbox' if m.recipient_id == current_user.id else 'sent'
        } for m in messages.items],
        'total': messages.total,
        'pages': messages.pages,
        'current_page': page
    })

@messages_bp.route('/messages/send', methods=['POST'])
@login_required
def send_message():
    """Send a new message to one or more recipients."""
    data = request.get_json() or request.form

    # Accept either recipient_id (legacy single) or recipient_ids (list)
    recipient_ids = data.get('recipient_ids')
    if recipient_ids is None:
        single = data.get('recipient_id')
        recipient_ids = [single] if single else []
    elif not isinstance(recipient_ids, list):
        recipient_ids = [recipient_ids]

    # Coerce to ints and dedupe
    try:
        recipient_ids = list({int(rid) for rid in recipient_ids if rid is not None})
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'Invalid recipient id'}), 400

    subject = data.get('subject')
    body = data.get('body')

    if not recipient_ids or not body:
        return jsonify({'success': False, 'error': 'Recipient and message body are required'}), 400

    # Verify all recipients exist
    recipients = db.session.query(User).filter(User.id.in_(recipient_ids)).all()
    found_ids = {r.id for r in recipients}
    missing = set(recipient_ids) - found_ids
    if missing:
        return jsonify({'success': False, 'error': f'Recipient not found: {sorted(missing)}'}), 404

    sent_count = 0
    for recipient in recipients:
        msg = Message(
            sender=current_user,
            recipient=recipient,
            subject=subject,
            body=body
        )
        db.session.add(msg)
        sent_count += 1

    db.session.commit()

    # Announce new message event to all active recipient listeners
    for rid in recipient_ids:
        announcer.announce(rid, 'new_message')

    return jsonify({
        'success': True,
        'message': f'Message sent to {sent_count} recipient(s)' if sent_count != 1 else 'Message sent successfully',
        'sent_count': sent_count
    })

@messages_bp.route('/messages/<int:id>/read', methods=['POST'])
@login_required
def mark_read(id):
    """Mark a message as read."""
    msg = db.session.get(Message, id)
    if not msg:
        return jsonify({'success': False, 'error': 'Message not found'}), 404
        
    if msg.recipient_id != current_user.id:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
    msg.read = True
    db.session.commit()
    return jsonify({'success': True})

@messages_bp.route('/messages/<int:id>/delete', methods=['POST'])
@login_required
def delete_message(id):
    """Soft delete or permanently delete a message."""
    msg = db.session.get(Message, id)
    if not msg:
        return jsonify({'success': False, 'error': 'Message not found'}), 404
    
    # Optional context param to handle self-messages correctly
    context = request.args.get('context') or request.form.get('context')
    
    deleted = False
    
    if context == 'inbox':
        if msg.recipient_id == current_user.id:
            msg.deleted_by_recipient = True
            deleted = True
    elif context == 'sent':
        if msg.sender_id == current_user.id:
            msg.deleted_by_sender = True
            deleted = True
    elif context == 'trash':
        if msg.recipient_id == current_user.id:
            msg.permanently_deleted_by_recipient = True
            deleted = True
        elif msg.sender_id == current_user.id:
            msg.permanently_deleted_by_sender = True
            deleted = True
    else:
        # Default behavior (legacy/fallback)
        if msg.recipient_id == current_user.id:
            if msg.deleted_by_recipient:
                msg.permanently_deleted_by_recipient = True
            else:
                msg.deleted_by_recipient = True
            deleted = True
        elif msg.sender_id == current_user.id:
            if msg.deleted_by_sender:
                msg.permanently_deleted_by_sender = True
            else:
                msg.deleted_by_sender = True
            deleted = True
            
    if not deleted:
        return jsonify({'success': False, 'error': 'Unauthorized or invalid context'}), 403
        
    db.session.commit()
    return jsonify({'success': True})

@messages_bp.route('/messages/<int:id>/restore', methods=['POST'])
@login_required
def restore_message(id):
    """Restore a message from trash (undo soft delete)."""
    msg = db.session.get(Message, id)
    if not msg:
        return jsonify({'success': False, 'error': 'Message not found'}), 404
        
    restored = False
    if msg.recipient_id == current_user.id and msg.deleted_by_recipient:
        msg.deleted_by_recipient = False
        restored = True
    if msg.sender_id == current_user.id and msg.deleted_by_sender:
        msg.deleted_by_sender = False
        restored = True
        
    if not restored:
        return jsonify({'success': False, 'error': 'Unauthorized or not in trash'}), 403
        
    db.session.commit()
    return jsonify({'success': True})


@messages_bp.route('/messages/empty-trash', methods=['POST'])
@login_required
def empty_trash():
    """Permanently delete all trash messages for the current user."""
    # Received trash
    received_trash = Message.query.filter(
        Message.recipient_id == current_user.id,
        Message.deleted_by_recipient == True,
        Message.permanently_deleted_by_recipient == False
    ).all()
    for m in received_trash:
        m.permanently_deleted_by_recipient = True

    # Sent trash
    sent_trash = Message.query.filter(
        Message.sender_id == current_user.id,
        Message.deleted_by_sender == True,
        Message.permanently_deleted_by_sender == False
    ).all()
    for m in sent_trash:
        m.permanently_deleted_by_sender = True

    db.session.commit()
    return jsonify({'success': True, 'message': 'Trash emptied successfully'})

def populate_home_clubs(users):
    if not users:
        return
    user_ids = [u.id for u in users]
    from app.models.user_club import UserClub
    from app.models.role import Role
    from sqlalchemy import or_
    from sqlalchemy.orm import joinedload
    
    ucs = UserClub.query.filter(
        UserClub.user_id.in_(user_ids),
        UserClub.is_home == True
    ).outerjoin(Role, UserClub.auth_role_id == Role.id)\
     .filter(or_(UserClub.auth_role_id.is_(None), Role.name != 'Guest'))\
     .options(joinedload(UserClub.club))\
     .all()
     
    uc_map = {uc.user_id: uc.club for uc in ucs}
    for u in users:
        u._home_club = uc_map.get(u.id)


@messages_bp.route('/api/messages/recipients')
@login_required
def get_recipients():
    """Get list of potential recipients with autocomplete."""
    try:
        import traceback
        query = request.args.get('q', '').strip()
        
        from app.club_context import get_current_club_id, get_or_set_default_club
        club_id = get_current_club_id() or get_or_set_default_club()
        
        users = []
        if club_id:
            from app.models.user_club import UserClub
            from app.models.contact import Contact
            from sqlalchemy import or_

            # Build query for users in the current club (excluding current user)
            members_query = User.query.filter(User.id != current_user.id)\
                .join(UserClub, (User.id == UserClub.user_id) & (UserClub.club_id == club_id))\
                .outerjoin(Contact, UserClub.contact_id == Contact.id)
            
            if query:
                query_like = f"%{query}%"
                members_query = members_query.filter(
                    or_(
                        User.username.ilike(query_like),
                        User._first_name.ilike(query_like),
                        User._last_name.ilike(query_like),
                        Contact.Name.ilike(query_like)
                    )
                )
            
            # Limit the query to at most 5 results to keep things extremely fast
            users = members_query.limit(5).all()
        
        # Check if query is not empty and matches a user outside/inside the club exactly by username
        if query:
            exact_user = User.query.filter(
                User.id != current_user.id,
                User.username.ilike(query)
            ).first()
            
            if exact_user and not any(u.id == exact_user.id for u in users):
                users.append(exact_user)
        
        # Batch populate contacts and home clubs to avoid N+1 queries
        if users:
            User.populate_contacts(users, club_id)
            populate_home_clubs(users)
        
        results = []
        for u in users:
            try:
                display_name = u.display_name
                
                # Fetch Home Club for context
                home_club_name = "No Club"
                home_club = u.home_club
                if home_club:
                    home_club_name = home_club.club_name

                results.append({
                    'id': u.id, 
                    'name': display_name, 
                    'email': u.email, 
                    'home_club': home_club_name
                })
            except Exception as inner_e:
                print(f"Skipping user {u.id} due to error: {inner_e}")
                continue
                
        return jsonify(results[:5])
    except Exception as e:
        print(f"FATAL ERROR in get_recipients: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500

@messages_bp.route('/api/messages/unread-count')
@login_required
def unread_count():
    """Get count of unread messages."""
    count = current_user.messages_received.filter(
        Message.read == False,
        Message.deleted_by_recipient == False
    ).count()
    return jsonify({'count': count})

@messages_bp.route('/api/messages/events')
@login_required
def message_events():
    """Server-Sent Events endpoint for message updates."""
    def event_generator():
        user_id = current_user.id
        q = announcer.listen(user_id)
        try:
            # Yield initial connect event
            yield "data: connected\n\n"
            while True:
                try:
                    # Wait for message update event
                    event_data = q.get(timeout=25)
                    yield f"data: {event_data}\n\n"
                except queue.Empty:
                    # Send keep-alive ping to prevent connection timeout
                    yield "data: ping\n\n"
        finally:
            announcer.remove_listener(user_id, q)

    response = Response(stream_with_context(event_generator()), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache, no-transform'
    response.headers['Connection'] = 'keep-alive'
    response.headers['X-Accel-Buffering'] = 'no'
    return response
