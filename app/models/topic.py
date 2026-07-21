from datetime import datetime, timezone
from .base import db

class Topic(db.Model):
    __tablename__ = 'topics'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='draft', nullable=False)  # 'draft', 'published'
    published_at = db.Column(db.DateTime, nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    responses = db.relationship('TopicResponse', backref='topic', cascade='all, delete-orphan', order_by='TopicResponse.created_at.desc()', lazy='dynamic')

    @classmethod
    def get_current(cls):
        """Get the latest published topic by published_at."""
        return cls.query.filter_by(status='published').order_by(cls.published_at.desc()).first()

    @classmethod
    def list_published(cls):
        """Get all published topics ordered by published_at desc."""
        return cls.query.filter_by(status='published').order_by(cls.published_at.desc()).all()

    def __repr__(self):
        return f'<Topic {self.id} status={self.status}>'


class TopicResponse(db.Model):
    __tablename__ = 'topic_responses'

    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id', ondelete='SET NULL'), nullable=True, index=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    club_id = db.Column(db.Integer, db.ForeignKey('clubs.id', ondelete='SET NULL'), nullable=True, index=True)
    title = db.Column(db.String(255), nullable=True)
    body = db.Column(db.Text, nullable=False)
    visibility = db.Column(db.String(20), default='private', nullable=False)  # 'private', 'club', 'public'
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    author_relationship = db.relationship('User', foreign_keys=[author_id], backref='topic_responses')
    comments = db.relationship('TopicComment', backref='response', cascade='all, delete-orphan', order_by='TopicComment.created_at')
    collection_items = db.relationship('CollectionItem', back_populates='response', cascade='all, delete-orphan')

    # Composite index for global public/club explorer queries
    __table_args__ = (
        db.Index('ix_topic_responses_visibility_created', 'visibility', 'created_at'),
    )

    @property
    def author(self):
        if hasattr(self, '_author'):
            return self._author
        return self.author_relationship

    @staticmethod
    def populate_authors(responses):
        """Batch-load authors to avoid N+1 queries when rendering lists."""
        if not responses:
            return
        from .user import User
        author_ids = list({r.author_id for r in responses})
        users = User.query.filter(User.id.in_(author_ids)).all()
        user_map = {u.id: u for u in users}
        for r in responses:
            r._author = user_map.get(r.author_id)

    @staticmethod
    def populate_likes(responses, user_id):
        """Batch-load like counts and a `liked by me` flag for a list of
        responses, mirroring the populate_authors N+1 avoidance pattern.

        Sets two private attributes consumed by templates:
          * `_like_count`    — total likes on the response (int)
          * `_liked_by_me`  — True if `user_id` has liked the response
        Both default to 0 / False when the response has no likes, so the
        template can read them unconditionally.
        """
        if not responses:
            return
        ids = [r.id for r in responses]
        counts = dict(
            db.session.query(TopicResponseLike.response_id, db.func.count())
            .filter(TopicResponseLike.response_id.in_(ids))
            .group_by(TopicResponseLike.response_id)
            .all()
        )
        mine = set()
        if user_id is not None:
            mine = {
                row[0] for row in
                db.session.query(TopicResponseLike.response_id)
                .filter(TopicResponseLike.response_id.in_(ids),
                        TopicResponseLike.user_id == user_id)
                .all()
            }
        for r in responses:
            r._like_count = counts.get(r.id, 0)
            r._liked_by_me = r.id in mine

    def __repr__(self):
        return f'<TopicResponse {self.id} author={self.author_id} visibility={self.visibility}>'


class TopicResponseLike(db.Model):
    """Association table recording one user's like on a single reflection.

    Invariants:
      * A user can like a reflection at most once — enforced by a
        unique constraint on (user_id, response_id).
      * Likes cascade on response deletion; on user deletion the row is
        removed as well so stale likes never accumulate.
      * Any authenticated member can like any reflection they can view
        (including their own); there is no `TOPICS_LIKE` permission —
        visibility is the only gating rule.
    """
    __tablename__ = 'topic_response_likes'

    id = db.Column(db.Integer, primary_key=True)
    response_id = db.Column(db.Integer, db.ForeignKey('topic_responses.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        db.UniqueConstraint('response_id', 'user_id', name='uq_topic_response_likes_response_user'),
    )

    def __repr__(self):
        return f'<TopicResponseLike response={self.response_id} user={self.user_id}>'


class TopicComment(db.Model):
    __tablename__ = 'topic_comments'

    id = db.Column(db.Integer, primary_key=True)
    response_id = db.Column(db.Integer, db.ForeignKey('topic_responses.id', ondelete='CASCADE'), nullable=False, index=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('topic_comments.id', ondelete='CASCADE'), nullable=True, index=True)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    author_relationship = db.relationship('User', foreign_keys=[author_id], backref='topic_comments')
    parent = db.relationship('TopicComment', remote_side=[id], backref=db.backref('children', cascade='all, delete-orphan'))

    @property
    def author(self):
        if hasattr(self, '_author'):
            return self._author
        return self.author_relationship

    @staticmethod
    def populate_authors(comments):
        """Batch-load authors to avoid N+1 queries when rendering comment threads."""
        if not comments:
            return
        from .user import User
        author_ids = list({c.author_id for c in comments})
        users = User.query.filter(User.id.in_(author_ids)).all()
        user_map = {u.id: u for u in users}
        for c in comments:
            c._author = user_map.get(c.author_id)

    def __repr__(self):
        return f'<TopicComment {self.id} author={self.author_id} response={self.response_id}>'


class TopicCollection(db.Model):
    __tablename__ = 'topic_collections'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    user = db.relationship('User', backref='topic_collections')
    items = db.relationship('CollectionItem', back_populates='collection', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<TopicCollection {self.id} name={self.name} user={self.user_id}>'


class CollectionItem(db.Model):
    __tablename__ = 'collection_items'

    id = db.Column(db.Integer, primary_key=True)
    collection_id = db.Column(db.Integer, db.ForeignKey('topic_collections.id', ondelete='CASCADE'), nullable=False, index=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id', ondelete='CASCADE'), nullable=True, index=True)
    response_id = db.Column(db.Integer, db.ForeignKey('topic_responses.id', ondelete='CASCADE'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    collection = db.relationship('TopicCollection', back_populates='items')
    topic = db.relationship('Topic', backref='collection_items')
    response = db.relationship('TopicResponse', back_populates='collection_items')

    # Add unique constraints to prevent duplicate saves in a single collection
    __table_args__ = (
        db.UniqueConstraint('collection_id', 'topic_id', name='uq_collection_topic'),
        db.UniqueConstraint('collection_id', 'response_id', name='uq_collection_response'),
    )

    def __repr__(self):
        return f'<CollectionItem {self.id} collection={self.collection_id} topic={self.topic_id} response={self.response_id}>'
