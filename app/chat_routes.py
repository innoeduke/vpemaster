from flask import Blueprint, request, jsonify, session, current_app
from flask_login import login_required, current_user
from app import db
from app.models import ChatMessage, Club
from app.auth.permissions import Permissions
from app.auth.utils import is_authorized
from app.club_context import get_current_club_id, authorized_club_required
from app.services.chat_service import ChatService
from app.services.command_parser import CommandParser
import json

chat_bp = Blueprint('chat_bp', __name__)

@chat_bp.route('/chat/send', methods=['POST'])
@login_required
@authorized_club_required
def chat_send():
    """
    Receives a message from the client, determines the mode (AI or Command),
    executes it, and returns the response message.
    """
    # 1. Determine Permission and Mode
    has_ai = is_authorized(Permissions.CHAT_AI)
    has_cmd = is_authorized(Permissions.CHAT_COMMANDS)
    
    if not (has_ai or has_cmd):
        return jsonify({'success': False, 'message': 'Permission denied.'}), 403
        
    mode = 'ai' if has_ai else 'command'
    
    # 2. Extract input message
    data = request.get_json() or {}
    message_text = data.get('message', '').strip()
    
    if not message_text:
        return jsonify({'success': False, 'message': 'Message cannot be empty.'}), 400

    club_id = get_current_club_id()
    locale = session.get('locale', 'en')

    try:
        # Save user message to database
        user_msg = ChatMessage(
            user_id=current_user.id,
            club_id=club_id,
            role='user',
            content=message_text,
            mode=mode
        )
        db.session.add(user_msg)
        db.session.commit()

        if mode == 'command':
            # Execute locally via regex command parser
            success, reply_text = CommandParser.parse_and_execute(message_text, current_user, club_id)
            
            # Save assistant response
            assistant_msg = ChatMessage(
                user_id=current_user.id,
                club_id=club_id,
                role='assistant',
                content=reply_text,
                mode=mode
            )
            db.session.add(assistant_msg)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'role': 'assistant',
                'content': reply_text,
                'mode': 'command',
                'executed_tools': []
            })
            
        else:
            # Full AI mode with MiniMax M3
            # Pre-parse matching patterns for factual queries to ensure 100% accurate results and zero hallucination
            import re
            from app.services.chat_tool_executor import ChatToolExecutor
            vote_match = re.search(r"(?:voting|vote|votign|tally|tallies)\s+results?(?:\s+of|\s+for)?\s+(?:meeting\s+)?#?(\d+|[0-9\-]+)", message_text, re.IGNORECASE)
            if vote_match:
                meeting_ident = vote_match.group(1)
                res = ChatToolExecutor.execute('get_voting_results', {'meeting_identifier': meeting_ident}, current_user, club_id)
                if res['success']:
                    reply_text = res['message']
                    assistant_msg = ChatMessage(
                        user_id=current_user.id,
                        club_id=club_id,
                        role='assistant',
                        content=reply_text,
                        mode='ai'
                    )
                    db.session.add(assistant_msg)
                    db.session.commit()
                    return jsonify({
                        'success': True,
                        'role': 'assistant',
                        'content': reply_text,
                        'mode': 'ai',
                        'executed_tools': [{'id': 'hybrid_route_vote', 'name': 'get_voting_results', 'arguments': {'meeting_identifier': meeting_ident}}]
                    })

            # Load preceding context
            history = ChatMessage.query.filter_by(
                user_id=current_user.id,
                club_id=club_id
            ).order_by(ChatMessage.timestamp.asc()).all()
            
            # Process AI completion (includes tool loop execution)
            reply_text, executed_tools = ChatService.process_chat_completion(
                chat_history_list=history,
                user=current_user,
                club_id=club_id,
                locale=locale
            )
            
            # Convert executed tools to JSON string
            tool_calls_json = json.dumps(executed_tools) if executed_tools else None

            # Save assistant response
            assistant_msg = ChatMessage(
                user_id=current_user.id,
                club_id=club_id,
                role='assistant',
                content=reply_text,
                tool_calls=tool_calls_json,
                mode=mode
            )
            db.session.add(assistant_msg)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'role': 'assistant',
                'content': reply_text,
                'mode': 'ai',
                'executed_tools': executed_tools
            })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in chat send route: {str(e)}")
        return jsonify({'success': False, 'message': f"Error: {str(e)}"}), 500

@chat_bp.route('/chat/history', methods=['GET'])
@login_required
@authorized_club_required
def chat_history():
    """
    Returns the recent chat history for the logged in user/club.
    """
    has_ai = is_authorized(Permissions.CHAT_AI)
    has_cmd = is_authorized(Permissions.CHAT_COMMANDS)
    
    if not (has_ai or has_cmd):
        return jsonify({'success': False, 'message': 'Permission denied.'}), 403
        
    club_id = get_current_club_id()
    
    # Query latest 30 messages
    messages = ChatMessage.query.filter_by(
        user_id=current_user.id,
        club_id=club_id
    ).order_by(ChatMessage.timestamp.desc()).limit(30).all()
    
    # Reverse to restore chronological order
    messages.reverse()
    
    res = []
    for msg in messages:
        res.append({
            'role': msg.role,
            'content': msg.content,
            'mode': msg.mode,
            'timestamp': msg.timestamp.isoformat()
        })
        
    return jsonify({
        'success': True,
        'messages': res,
        'mode': 'ai' if has_ai else 'command'
    })

@chat_bp.route('/chat/clear', methods=['POST'])
@login_required
@authorized_club_required
def chat_clear():
    """
    Clears all chat history for this user/club.
    """
    club_id = get_current_club_id()
    try:
        ChatMessage.query.filter_by(
            user_id=current_user.id,
            club_id=club_id
        ).delete()
        db.session.commit()
        return jsonify({'success': True, 'message': 'Chat history cleared successfully.'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error clearing chat history: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500
