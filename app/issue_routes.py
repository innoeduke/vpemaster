from datetime import datetime, timezone

from flask import (
    Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for,
)
from flask_login import current_user, login_required
from sqlalchemy.orm import joinedload

from . import db
from .auth.permissions import Permissions
from .auth.utils import club_permission_required
from .club_context import (
    authorized_club_required, filter_by_club, get_current_club_id,
)
from .models import Club, Issue, IssueComment, User, UserClub
from .system_messaging import send_system_message


issue_bp = Blueprint('issue_bp', __name__)


TERMINAL_STATUSES = Issue.TERMINAL_STATUSES
DESCRIPTION_MAX = 10000


def _get_issue_or_404(issue_id):
    club_id = get_current_club_id()
    query = Issue.query.filter_by(id=issue_id)
    if club_id:
        query = query.filter_by(club_id=club_id)
    return query.first_or_404()


@issue_bp.route('/issues/')
@login_required
@authorized_club_required
def list_issues():
    query = Issue.query.options(
        joinedload(Issue.submitter),
        joinedload(Issue.assignee),
    )

    filters = {
        'status': request.args.get('status') or None,
        'type': request.args.get('type') or None,
        'priority': request.args.get('priority') or None,
    }
    assignee_id = request.args.get('assignee_id', type=int)

    is_sysadmin = current_user.is_authenticated and current_user.is_sysadmin
    selected_club_id = request.args.get('club_id', type=int)
    if is_sysadmin and selected_club_id:
        query = query.filter(Issue.club_id == selected_club_id)
    else:
        query = filter_by_club(query, Issue)

    for field, value in filters.items():
        if value:
            query = query.filter(getattr(Issue, field) == value)
    if assignee_id:
        query = query.filter(Issue.assignee_id == assignee_id)

    issues = query.order_by(Issue.created_at.desc()).all()

    assignable_users = _list_club_users(
        get_current_club_id() if not is_sysadmin or not selected_club_id else selected_club_id,
        permission=Permissions.ISSUE_MANAGE,
    )

    return render_template(
        'issues/list.html',
        issues=issues,
        filters={k: v for k, v in filters.items() if v},
        assignee_id=assignee_id,
        assignable_users=assignable_users,
        is_sysadmin=is_sysadmin,
        clubs=Club.query.order_by(Club.club_name).all() if is_sysadmin else None,
        selected_club_id=selected_club_id,
        Issue=Issue,
    )


@issue_bp.route('/issues/new', methods=['POST'])
@login_required
@authorized_club_required
def new_issue():
    data = request.get_json(silent=True) or request.form
    title = (data.get('title') or '').strip()
    description = (data.get('description') or '').strip()
    issue_type = data.get('type') or Issue.TYPE_BUG
    priority = data.get('priority') or Issue.PRIORITY_MEDIUM

    errors = []
    if not title:
        errors.append('Title is required.')
    if not description:
        errors.append('Description is required.')
    if len(description) > DESCRIPTION_MAX:
        errors.append(f'Description must be {DESCRIPTION_MAX} characters or fewer.')
    if issue_type not in Issue.TYPES:
        errors.append('Invalid type.')
    if priority not in Issue.PRIORITIES:
        errors.append('Invalid priority.')

    if errors:
        return jsonify({'success': False, 'error': ' '.join(errors)}), 400

    issue = Issue(
        club_id=get_current_club_id(),
        type=issue_type,
        status=Issue.STATUS_OPEN,
        priority=priority,
        title=title,
        description=description,
        submitter_id=current_user.id,
    )
    db.session.add(issue)
    db.session.commit()
    return jsonify({'success': True, 'id': issue.id})


@issue_bp.route('/issues/<int:issue_id>')
@login_required
@authorized_club_required
def detail_issue(issue_id):
    issue = _get_issue_or_404(issue_id)
    can_manage = current_user.is_authenticated and _can_manage_issues()
    assignable_users = _list_club_users(issue.club_id, permission=Permissions.ISSUE_MANAGE)
    return render_template(
        'issues/detail.html',
        issue=issue,
        can_manage=can_manage,
        assignable_users=assignable_users,
    )


@issue_bp.route('/issues/<int:issue_id>/update', methods=['POST'])
@login_required
@authorized_club_required
@club_permission_required(Permissions.ISSUE_MANAGE)
def update_issue(issue_id):
    issue = _get_issue_or_404(issue_id)
    previous_assignee_id = issue.assignee_id

    new_status = request.form.get('status') or issue.status
    new_priority = request.form.get('priority') or issue.priority
    new_assignee_id = request.form.get('assignee_id', type=int)
    new_title = (request.form.get('title') or issue.title).strip()
    new_description = (request.form.get('description') or issue.description).strip()

    errors = []
    if new_status not in Issue.STATUSES:
        errors.append('Invalid status.')
    if new_priority not in Issue.PRIORITIES:
        errors.append('Invalid priority.')
    if not new_title:
        errors.append('Title cannot be empty.')
    if not new_description:
        errors.append('Description cannot be empty.')
    if len(new_description) > DESCRIPTION_MAX:
        errors.append(f'Description must be {DESCRIPTION_MAX} characters or fewer.')
    if new_assignee_id:
        assignee = db.session.get(User, new_assignee_id)
        if not assignee:
            errors.append('Assignee not found.')
        elif not assignee.has_club_permission(Permissions.ISSUE_MANAGE, issue.club_id):
            errors.append('Assignee does not have permission to manage issues.')

    if errors:
        for e in errors:
            flash(e, 'error')
        return redirect(url_for('issue_bp.detail_issue', issue_id=issue.id))

    status_changed_to_terminal = (
        new_status in TERMINAL_STATUSES and issue.status not in TERMINAL_STATUSES
    )

    issue.status = new_status
    issue.priority = new_priority
    issue.assignee_id = new_assignee_id
    issue.title = new_title
    issue.description = new_description

    if status_changed_to_terminal:
        issue.closed_at = datetime.now(timezone.utc)
    elif new_status not in TERMINAL_STATUSES:
        issue.closed_at = None

    db.session.commit()

    if new_assignee_id and new_assignee_id != previous_assignee_id:
        send_system_message(
            new_assignee_id,
            f'You were assigned issue #{issue.id}: {issue.title}',
            (
                f'You have been assigned to issue #{issue.id} ({issue.type}, {issue.priority} priority).\n\n'
                f'{issue.description}\n\n'
                f'View: {url_for("issue_bp.detail_issue", issue_id=issue.id, _external=True)}'
            ),
        )

    flash('Issue updated.', 'success')
    return redirect(url_for('issue_bp.detail_issue', issue_id=issue.id))


@issue_bp.route('/issues/<int:issue_id>/comment', methods=['POST'])
@login_required
@authorized_club_required
def add_comment(issue_id):
    issue = _get_issue_or_404(issue_id)
    if issue.is_terminal():
        abort(403)

    body = (request.form.get('body') or '').strip()
    if not body:
        flash('Comment cannot be empty.', 'error')
        return redirect(url_for('issue_bp.detail_issue', issue_id=issue.id))

    comment = IssueComment(issue_id=issue.id, author_id=current_user.id, body=body)
    db.session.add(comment)
    db.session.commit()
    flash('Comment added.', 'success')
    return redirect(url_for('issue_bp.detail_issue', issue_id=issue.id))


@issue_bp.route('/issues/api/assignable-users')
@login_required
@authorized_club_required
def assignable_users():
    club_id = request.args.get('club_id', type=int) or get_current_club_id()
    users = _list_club_users(club_id, permission=Permissions.ISSUE_MANAGE)
    return jsonify([{'id': u.id, 'name': u.display_name, 'username': u.username} for u in users])


def _list_club_users(club_id, permission=None):
    if not club_id:
        return []
    user_ids = {
        uc.user_id
        for uc in UserClub.query.filter_by(club_id=club_id).all()
    }
    if not user_ids:
        return []
    users = User.query.filter(User.id.in_(user_ids)).order_by(User.username).all()
    if permission is None:
        return users
    return [u for u in users if u.has_club_permission(permission, club_id)]


def _can_manage_issues():
    if not current_user.is_authenticated:
        return False
    if current_user.is_sysadmin:
        return True
    from .auth.utils import is_authorized
    return is_authorized(Permissions.ISSUE_MANAGE)
