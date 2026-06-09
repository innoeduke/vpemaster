"""Token helpers for the public Self Check-In page.

Mirrors the pattern in app/models/user.py:107-126 (URLSafeTimedSerializer for
password reset / verification) but uses a distinct salt so a leaked token of
one kind can never be used as the other.
"""
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from flask import current_app


_SALT = 'checkin-token'
_DEFAULT_MAX_AGE = 24 * 60 * 60  # 24 hours


def _serializer():
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'])


def generate_checkin_token(meeting_id):
    """Sign a token that grants access to the public check-in page for a meeting."""
    return _serializer().dumps({'meeting_id': int(meeting_id)}, salt=_SALT)


def verify_checkin_token(token, max_age=_DEFAULT_MAX_AGE):
    """Decode a check-in token. Returns the meeting_id or None on failure."""
    try:
        data = _serializer().loads(token, salt=_SALT, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
    if not isinstance(data, dict):
        return None
    meeting_id = data.get('meeting_id')
    try:
        return int(meeting_id) if meeting_id is not None else None
    except (TypeError, ValueError):
        return None
