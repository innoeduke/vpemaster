from datetime import datetime, timezone
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import login_required, current_user
from sqlalchemy import or_

from . import db
from .auth.permissions import Permissions
from .auth.utils import is_authorized
from .translations.translations import translate as _
from .models import Topic, TopicResponse, TopicComment, TopicCollection, CollectionItem, User, Club
from .services.topics_service import TopicService, ResponseService, CommentService, CollectionService

topics_bp = Blueprint('topics_bp', __name__)

@topics_bp.before_request
def check_topics_enabled():
    from app.club_context import is_module_enabled
    from flask import abort
    if not is_module_enabled('Topics'):
        abort(404)


def check_response_visible(response, user):
    """
    Check if a response is visible to a user.
    - Private: only the author
    - Club: members of any club that the author and viewer both belong to
    - Public: everyone
    """
    if not response:
        return False
    if response.visibility == 'public':
        return True
    if user.is_authenticated and user.id == response.author_id:
        return True
    if response.visibility == 'club' and user.is_authenticated:
        # Check intersecting club membership
        from .models.user_club import UserClub
        author_club_ids = [uc.club_id for uc in UserClub.query.filter_by(user_id=response.author_id).all()]
        if not author_club_ids:
            return False
        return UserClub.query.filter(
            UserClub.user_id == user.id,
            UserClub.club_id.in_(author_club_ids)
        ).first() is not None
    return False


@topics_bp.route('/topics')
@login_required
def dashboard():
    """Table Topics Landing Dashboard."""
    if not is_authorized(Permissions.TOPICS_VIEW):
        abort(403)

    # Get featured topic (most recently published)
    featured_topic = Topic.get_current()
    
    # Get user's own response for the featured topic (if any)
    featured_response = None
    if featured_topic:
        featured_response = TopicResponse.query.filter_by(
            topic_id=featured_topic.id,
            author_id=current_user.id
        ).first()

    # Get past published topics (excluding featured one if it exists)
    past_topics_query = Topic.query.filter_by(status='published')
    if featured_topic:
        past_topics_query = past_topics_query.filter(Topic.id != featured_topic.id)
    past_topics = past_topics_query.order_by(Topic.published_at.desc()).limit(5).all()

    # Get recent visible essays from others on the explore board
    # Fetch public responses
    visible_responses_query = TopicResponse.query.filter(
        or_(
            TopicResponse.visibility == 'public',
            TopicResponse.author_id == current_user.id
        )
    )
    
    # Fetch shared club essays
    # (Select all responses with visibility='club', check intersection in memory or python is safe for small lists,
    # or query using SQL join)
    # Let's run a query for shared club responses
    from .models.user_club import UserClub
    my_club_ids = [uc.club_id for uc in UserClub.query.filter_by(user_id=current_user.id).all()]
    if my_club_ids:
        club_authors = db.session.query(UserClub.user_id).filter(UserClub.club_id.in_(my_club_ids))
        visible_responses_query = TopicResponse.query.filter(
            or_(
                TopicResponse.visibility == 'public',
                TopicResponse.author_id == current_user.id,
                db.and_(TopicResponse.visibility == 'club', TopicResponse.author_id.in_(club_authors))
            )
        )

    recent_feed = visible_responses_query.order_by(TopicResponse.created_at.desc()).limit(5).all()
    TopicResponse.populate_authors(recent_feed)

    # Get user's collections
    collections = TopicCollection.query.filter_by(user_id=current_user.id).order_by(TopicCollection.name.asc()).all()

    return render_template(
        'topics/dashboard.html',
        featured_topic=featured_topic,
        featured_response=featured_response,
        past_topics=past_topics,
        recent_feed=recent_feed,
        collections=collections,
        active_tab='dashboard'
    )


@topics_bp.route('/topics/explore')
@login_required
def explore():
    """Global Table Topics explore feed."""
    if not is_authorized(Permissions.TOPICS_VIEW):
        abort(403)

    page = request.args.get('page', 1, type=int)
    per_page = 10

    # Build visible responses filter
    from .models.user_club import UserClub
    my_club_ids = [uc.club_id for uc in UserClub.query.filter_by(user_id=current_user.id).all()]
    if my_club_ids:
        club_authors = db.session.query(UserClub.user_id).filter(UserClub.club_id.in_(my_club_ids))
        query = TopicResponse.query.filter(
            or_(
                TopicResponse.visibility == 'public',
                TopicResponse.author_id == current_user.id,
                db.and_(TopicResponse.visibility == 'club', TopicResponse.author_id.in_(club_authors))
            )
        )
    else:
        query = TopicResponse.query.filter(
            or_(
                TopicResponse.visibility == 'public',
                TopicResponse.author_id == current_user.id
            )
        )

    pagination = query.order_by(TopicResponse.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    responses = pagination.items
    TopicResponse.populate_authors(responses)

    # Get user's collections
    collections = TopicCollection.query.filter_by(user_id=current_user.id).order_by(TopicCollection.name.asc()).all()

    return render_template(
        'topics/explore.html',
        responses=responses,
        pagination=pagination,
        collections=collections,
        active_tab='explore'
    )


@topics_bp.route('/topics/mine')
@login_required
def mine():
    """User's personal journal timeline."""
    if not is_authorized(Permissions.TOPICS_VIEW):
        abort(403)

    page = request.args.get('page', 1, type=int)
    per_page = 10

    pagination = TopicResponse.query.filter_by(author_id=current_user.id).order_by(TopicResponse.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    responses = pagination.items
    TopicResponse.populate_authors(responses)

    # Get user's collections
    collections = TopicCollection.query.filter_by(user_id=current_user.id).order_by(TopicCollection.name.asc()).all()

    return render_template(
        'topics/mine.html',
        responses=responses,
        pagination=pagination,
        collections=collections,
        active_tab='mine'
    )


@topics_bp.route('/topics/collection/<int:collection_id>')
@login_required
def collection_detail(collection_id):
    """View details of a private collection."""
    if not is_authorized(Permissions.TOPICS_VIEW):
        abort(403)

    collection = db.session.get(TopicCollection, collection_id)
    if not collection:
        abort(404)
        
    if collection.user_id != current_user.id:
        abort(403)

    # Fetch items inside collection
    items = CollectionItem.query.filter_by(collection_id=collection_id).order_by(CollectionItem.created_at.desc()).all()
    
    # Map topics and responses
    saved_topics = []
    saved_responses = []
    
    for item in items:
        if item.topic_id:
            topic = db.session.get(Topic, item.topic_id)
            if topic:
                saved_topics.append(topic)
        elif item.response_id:
            response = db.session.get(TopicResponse, item.response_id)
            if response and check_response_visible(response, current_user):
                saved_responses.append(response)

    TopicResponse.populate_authors(saved_responses)

    # Get user's collections
    collections = TopicCollection.query.filter_by(user_id=current_user.id).order_by(TopicCollection.name.asc()).all()

    return render_template(
        'topics/collection_detail.html',
        collection=collection,
        saved_topics=saved_topics,
        saved_responses=saved_responses,
        collections=collections,
        active_tab=f'collection_{collection_id}'
    )


@topics_bp.route('/topic/<int:topic_id>')
@login_required
def topic_detail(topic_id):
    """Topic detailed question page + list of visible responses on it."""
    if not is_authorized(Permissions.TOPICS_VIEW):
        abort(403)

    topic = db.session.get(Topic, topic_id)
    if not topic:
        # Check if it was deleted
        return render_template('topics/topic_deleted.html')

    # Deny access if it's draft and user is not admin
    if topic.status == 'draft' and not is_authorized(Permissions.TOPICS_MANAGE):
        abort(403)

    # Fetch user's own response
    my_response = TopicResponse.query.filter_by(topic_id=topic_id, author_id=current_user.id).first()

    # Fetch other responses
    from .models.user_club import UserClub
    my_club_ids = [uc.club_id for uc in UserClub.query.filter_by(user_id=current_user.id).all()]
    if my_club_ids:
        club_authors = db.session.query(UserClub.user_id).filter(UserClub.club_id.in_(my_club_ids))
        other_responses_query = TopicResponse.query.filter(
            TopicResponse.topic_id == topic_id,
            TopicResponse.author_id != current_user.id,
            or_(
                TopicResponse.visibility == 'public',
                db.and_(TopicResponse.visibility == 'club', TopicResponse.author_id.in_(club_authors))
            )
        )
    else:
        other_responses_query = TopicResponse.query.filter(
            TopicResponse.topic_id == topic_id,
            TopicResponse.author_id != current_user.id,
            TopicResponse.visibility == 'public'
        )

    other_responses = other_responses_query.order_by(TopicResponse.created_at.desc()).all()
    TopicResponse.populate_authors(other_responses)

    # User collections
    collections = TopicCollection.query.filter_by(user_id=current_user.id).order_by(TopicCollection.name.asc()).all()
    
    # Get current saved collection IDs for this topic
    saved_collection_ids = CollectionService.get_user_collections_for_item(
        user_id=current_user.id,
        topic_id=topic_id
    )

    return render_template(
        'topics/topic_detail.html',
        topic=topic,
        my_response=my_response,
        other_responses=other_responses,
        collections=collections,
        saved_collection_ids=saved_collection_ids,
        active_tab=''
    )


@topics_bp.route('/topic/<int:topic_id>/respond', methods=['GET', 'POST'])
@login_required
def respond(topic_id):
    """Respond (write essay) page."""
    if not is_authorized(Permissions.TOPICS_WRITE):
        abort(403)

    topic = db.session.get(Topic, topic_id)
    if not topic:
        abort(404)

    # Deny access if draft and not admin
    if topic.status == 'draft' and not is_authorized(Permissions.TOPICS_MANAGE):
        abort(403)

    # Check if they already responded
    existing = TopicResponse.query.filter_by(topic_id=topic_id, author_id=current_user.id).first()
    if existing:
        return redirect(url_for('topics_bp.edit_response', response_id=existing.id))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        body = request.form.get('body', '').strip()
        visibility = request.form.get('visibility', 'private')

        if not body:
            flash(_('Response content cannot be empty.'), 'error')
            return redirect(url_for('topics_bp.respond', topic_id=topic_id))

        # Get author's club_id context
        from .club_context import get_current_club_id
        club_id = get_current_club_id()

        try:
            response = ResponseService.create_response(
                topic_id=topic_id,
                author_id=current_user.id,
                club_id=club_id,
                title=title if title else None,
                body=body,
                visibility=visibility
            )
            flash(_('Your response has been saved.'), 'success')
            return redirect(url_for('topics_bp.response_detail', response_id=response.id))
        except Exception as e:
            flash(str(e), 'error')

    return render_template('topics/respond.html', topic=topic)


@topics_bp.route('/response/<int:response_id>')
@login_required
def response_detail(response_id):
    """Full essay view + threaded comments."""
    if not is_authorized(Permissions.TOPICS_VIEW):
        abort(403)

    response = db.session.get(TopicResponse, response_id)
    if not response or not check_response_visible(response, current_user):
        abort(403)

    topic = None
    if response.topic_id:
        topic = db.session.get(Topic, response.topic_id)

    # Load comments and replies
    all_comments = TopicComment.query.filter_by(response_id=response_id).order_by(TopicComment.created_at.asc()).all()
    TopicComment.populate_authors(all_comments)

    # Separate top-level comments and replies
    top_comments = [c for c in all_comments if c.parent_id is None]
    
    # Store replies map for top comments
    replies_map = {}
    for c in top_comments:
        replies_map[c.id] = [r for r in all_comments if r.parent_id == c.id]

    # Get user collections
    collections = TopicCollection.query.filter_by(user_id=current_user.id).order_by(TopicCollection.name.asc()).all()
    
    # Get current saved collection IDs for this response
    saved_collection_ids = CollectionService.get_user_collections_for_item(
        user_id=current_user.id,
        response_id=response_id
    )

    return render_template(
        'topics/response_detail.html',
        response=response,
        topic=topic,
        top_comments=top_comments,
        replies_map=replies_map,
        collections=collections,
        saved_collection_ids=saved_collection_ids
    )


@topics_bp.route('/response/<int:response_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_response(response_id):
    """Edit own response."""
    if not is_authorized(Permissions.TOPICS_WRITE):
        abort(403)

    response = db.session.get(TopicResponse, response_id)
    if not response:
        abort(404)

    if response.author_id != current_user.id:
        abort(403)

    topic = None
    if response.topic_id:
        topic = db.session.get(Topic, response.topic_id)

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        body = request.form.get('body', '').strip()
        visibility = request.form.get('visibility', 'private')

        if not body:
            flash(_('Response content cannot be empty.'), 'error')
            return redirect(url_for('topics_bp.edit_response', response_id=response_id))

        try:
            ResponseService.update_response(
                response_id=response_id,
                user_id=current_user.id,
                title=title if title else None,
                body=body,
                visibility=visibility
            )
            flash(_('Your response has been updated.'), 'success')
            return redirect(url_for('topics_bp.response_detail', response_id=response_id))
        except Exception as e:
            flash(str(e), 'error')

    return render_template('topics/respond.html', response=response, topic=topic)


@topics_bp.route('/response/<int:response_id>/delete', methods=['POST'])
@login_required
def delete_response(response_id):
    """Delete own response."""
    response = db.session.get(TopicResponse, response_id)
    if not response:
        abort(404)

    # Check permission
    is_sysadmin = current_user.is_authenticated and current_user.is_sysadmin
    try:
        ResponseService.delete_response(
            response_id=response_id,
            user_id=current_user.id,
            is_sysadmin=is_sysadmin
        )
        flash(_('Your response has been deleted.'), 'success')
        return redirect(url_for('topics_bp.dashboard'))
    except Exception as e:
        flash(str(e), 'error')
        return redirect(url_for('topics_bp.response_detail', response_id=response_id))


@topics_bp.route('/response/<int:response_id>/comment', methods=['POST'])
@login_required
def add_comment(response_id):
    """Add a comment or edit an existing one (AJAX)."""
    if not is_authorized(Permissions.TOPICS_COMMENT):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    response = db.session.get(TopicResponse, response_id)
    if not response or not check_response_visible(response, current_user):
        return jsonify({'success': False, 'error': 'Response not found or hidden.'}), 404

    data = request.get_json() or {}
    body = data.get('body', '').strip()
    comment_id = data.get('comment_id')  # If editing
    parent_id = data.get('parent_id')    # If replying

    if not body:
        return jsonify({'success': False, 'error': 'Comment content cannot be empty.'}), 400

    try:
        if comment_id:
            # Edit existing comment
            comment = CommentService.update_comment(
                comment_id=comment_id,
                author_id=current_user.id,
                body=body
            )
            return jsonify({
                'success': True,
                'comment_id': comment.id,
                'body': comment.body,
                'updated_at': comment.updated_at.strftime('%Y-%m-%d %H:%M:%S')
            })
        else:
            # Create new comment/reply
            comment = CommentService.add_comment(
                response_id=response_id,
                author_id=current_user.id,
                body=body,
                parent_id=parent_id
            )
            
            # Retrieve author info for display
            from .models import Contact
            avatar_url = current_user.full_avatar_url
            author_name = current_user.first_name or current_user.display_name or current_user.username
            
            # Try to get display club
            club_name = "—"
            contact = current_user.get_contact()
            if contact and contact.display_club_name:
                club_name = contact.display_club_name

            return jsonify({
                'success': True,
                'comment_id': comment.id,
                'body': comment.body,
                'author': author_name,
                'author_id': current_user.id,
                'club_name': club_name,
                'avatar_url': avatar_url,
                'created_at': comment.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'parent_id': comment.parent_id
            })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@topics_bp.route('/comment/<int:comment_id>/delete', methods=['POST'])
@login_required
def delete_comment(comment_id):
    """Delete a comment (AJAX)."""
    is_sysadmin = current_user.is_authenticated and current_user.is_sysadmin
    try:
        CommentService.delete_comment(
            comment_id=comment_id,
            user_id=current_user.id,
            is_sysadmin=is_sysadmin
        )
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 403


# ==========================================
# Collections AJAX Endpoints
# ==========================================

@topics_bp.route('/topics/collections/create', methods=['POST'])
@login_required
def create_collection():
    """Create a new collection folder (AJAX)."""
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    
    if not name:
        return jsonify({'success': False, 'error': 'Collection name cannot be empty.'}), 400

    try:
        collection = CollectionService.create_collection(
            user_id=current_user.id,
            name=name
        )
        return jsonify({
            'success': True,
            'collection_id': collection.id,
            'name': collection.name
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@topics_bp.route('/topics/collections/<int:collection_id>/delete', methods=['POST'])
@login_required
def delete_collection(collection_id):
    """Delete a custom collection folder."""
    try:
        CollectionService.delete_collection(collection_id, current_user.id)
        flash(_('Collection has been deleted.'), 'success')
    except Exception as e:
        flash(str(e), 'error')
    return redirect(url_for('topics_bp.dashboard'))


@topics_bp.route('/topics/collections/add-item', methods=['POST'])
@login_required
def toggle_collection_item():
    """Toggle a topic/response inside collections (AJAX checkboxes)."""
    data = request.get_json() or {}
    add_ids = data.get('add_collection_ids', [])
    remove_ids = data.get('remove_collection_ids', [])
    topic_id = data.get('topic_id')
    response_id = data.get('response_id')

    try:
        CollectionService.toggle_item_in_collections(
            user_id=current_user.id,
            collection_ids_to_add=add_ids,
            collection_ids_to_remove=remove_ids,
            topic_id=topic_id,
            response_id=response_id
        )
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@topics_bp.route('/topics/collections/status')
@login_required
def collection_status():
    """Get all user collections and check if the given item is saved in each."""
    topic_id = request.args.get('topic_id', type=int)
    response_id = request.args.get('response_id', type=int)

    # Get user collections
    collections = TopicCollection.query.filter_by(user_id=current_user.id).order_by(TopicCollection.name.asc()).all()
    
    # Get user collections that contain this item
    saved_ids = []
    if topic_id or response_id:
        saved_ids = CollectionService.get_user_collections_for_item(
            user_id=current_user.id,
            topic_id=topic_id,
            response_id=response_id
        )
        
    result = []
    for col in collections:
        result.append({
            'id': col.id,
            'name': col.name,
            'saved': col.id in saved_ids
        })
        
    return jsonify({'success': True, 'collections': result})


# ==========================================
# Admin Management Routes
# ==========================================

@topics_bp.route('/topics/admin')
@login_required
def admin():
    """Topic administration pipeline."""
    if not is_authorized(Permissions.TOPICS_MANAGE):
        abort(403)

    # Fetch all draft and published topics
    drafts = Topic.query.filter_by(status='draft').order_by(Topic.created_at.desc()).all()
    published = Topic.query.filter_by(status='published').order_by(Topic.published_at.desc()).all()

    return render_template(
        'topics/admin.html',
        drafts=drafts,
        published=published,
        active_tab='admin'
    )


@topics_bp.route('/topics/admin/create', methods=['POST'])
@login_required
def admin_create():
    """Create a new topic draft."""
    if not is_authorized(Permissions.TOPICS_MANAGE):
        abort(403)

    title = request.form.get('title', '').strip()
    body = request.form.get('body', '').strip()

    if not title or not body:
        flash(_('Title and topic context are both required.'), 'error')
        return redirect(url_for('topics_bp.admin'))

    TopicService.create_topic(title=title, body=body, creator_id=current_user.id)
    flash(_('Topic draft has been created.'), 'success')
    return redirect(url_for('topics_bp.admin'))


@topics_bp.route('/topics/admin/<int:topic_id>/publish', methods=['POST'])
@login_required
def admin_publish(topic_id):
    """Publish a topic draft."""
    if not is_authorized(Permissions.TOPICS_MANAGE):
        abort(403)

    try:
        TopicService.publish_topic(topic_id)
        flash(_('Topic has been published successfully.'), 'success')
    except Exception as e:
        flash(str(e), 'error')
        
    return redirect(url_for('topics_bp.admin'))


@topics_bp.route('/topics/admin/<int:topic_id>/delete', methods=['POST'])
@login_required
def admin_delete(topic_id):
    """Admin hard deletes a topic."""
    if not is_authorized(Permissions.TOPICS_MANAGE):
        abort(403)

    try:
        TopicService.delete_topic(topic_id)
        flash(_('Topic has been deleted.'), 'success')
    except Exception as e:
        flash(str(e), 'error')
        
    return redirect(url_for('topics_bp.admin'))
