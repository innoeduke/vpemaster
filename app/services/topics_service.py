from datetime import datetime, timezone
from .. import db
from ..models import Topic, TopicResponse, TopicComment, TopicCollection, CollectionItem, User, Club

class TopicService:
    @staticmethod
    def create_topic(title, body, creator_id):
        """Create a new topic in draft status."""
        topic = Topic(
            title=title,
            body=body,
            status='draft',
            created_by_id=creator_id
        )
        db.session.add(topic)
        db.session.commit()
        return topic

    @staticmethod
    def publish_topic(topic_id):
        """Publish a topic, setting status to published and published_at to now."""
        topic = db.session.get(Topic, topic_id)
        if not topic:
            raise ValueError(f"Topic with ID {topic_id} not found.")
        topic.status = 'published'
        topic.published_at = datetime.now(timezone.utc)
        db.session.commit()
        return topic

    @staticmethod
    def update_topic(topic_id, title, body):
        """Update an existing topic."""
        topic = db.session.get(Topic, topic_id)
        if not topic:
            raise ValueError(f"Topic with ID {topic_id} not found.")
        topic.title = title
        topic.body = body
        db.session.commit()
        return topic

    @staticmethod
    def delete_topic(topic_id):
        """Delete a topic. Note: associated responses will have topic_id set to NULL."""
        topic = db.session.get(Topic, topic_id)
        if not topic:
            raise ValueError(f"Topic with ID {topic_id} not found.")
        
        # Explicitly set topic_id to None on all related responses to avoid cascade errors
        # if the database constraints differ, or if loaded in session
        for response in TopicResponse.query.filter_by(topic_id=topic_id).all():
            response.topic_id = None
            
        # Also clean up any CollectionItems containing this topic
        CollectionItem.query.filter_by(topic_id=topic_id).delete()

        db.session.delete(topic)
        db.session.commit()
        return True


class ResponseService:
    @staticmethod
    def create_response(topic_id, author_id, club_id, title, body, visibility):
        """Create a new essay response/reflection on a topic."""
        # Verify visibility choice
        if visibility not in ('private', 'club', 'public'):
            raise ValueError(f"Invalid visibility option: {visibility}")
            
        if topic_id:
            topic = db.session.get(Topic, topic_id)
            if not topic:
                raise ValueError(f"Topic with ID {topic_id} not found.")

        response = TopicResponse(
            topic_id=topic_id,
            author_id=author_id,
            club_id=club_id,
            title=title,
            body=body,
            visibility=visibility
        )
        db.session.add(response)
        db.session.commit()
        return response

    @staticmethod
    def update_response(response_id, user_id, title, body, visibility):
        """Update an existing response, checking author ownership."""
        if visibility not in ('private', 'club', 'public'):
            raise ValueError(f"Invalid visibility option: {visibility}")

        response = db.session.get(TopicResponse, response_id)
        if not response:
            raise ValueError(f"Response with ID {response_id} not found.")
        
        if response.author_id != user_id:
            raise PermissionError("You do not have permission to edit this reflection.")

        response.title = title
        response.body = body
        response.visibility = visibility
        db.session.commit()
        return response

    @staticmethod
    def delete_response(response_id, user_id, is_sysadmin=False):
        """Delete a response, checking author ownership or admin rights."""
        response = db.session.get(TopicResponse, response_id)
        if not response:
            raise ValueError(f"Response with ID {response_id} not found.")
        
        if response.author_id != user_id and not is_sysadmin:
            raise PermissionError("You do not have permission to delete this reflection.")
            
        # Clean up any CollectionItems containing this response
        CollectionItem.query.filter_by(response_id=response_id).delete()

        db.session.delete(response)
        db.session.commit()
        return True


class CommentService:
    @staticmethod
    def add_comment(response_id, author_id, body, parent_id=None):
        """Add a comment (or 1-level nested reply) to an essay response."""
        response = db.session.get(TopicResponse, response_id)
        if not response:
            raise ValueError(f"Response with ID {response_id} not found.")

        if parent_id:
            parent = db.session.get(TopicComment, parent_id)
            if not parent:
                raise ValueError(f"Parent comment with ID {parent_id} not found.")
            # Enforce 1-level max nesting: parent must be a top-level comment (parent_id is Null)
            if parent.parent_id is not None:
                raise ValueError("Nesting comments beyond 1 level is not allowed.")
            # Enforce matching response context
            if parent.response_id != response_id:
                raise ValueError("Parent comment does not belong to the same response.")

        comment = TopicComment(
            response_id=response_id,
            author_id=author_id,
            body=body,
            parent_id=parent_id
        )
        db.session.add(comment)
        db.session.commit()
        return comment

    @staticmethod
    def update_comment(comment_id, author_id, body):
        """Update an existing comment body, checking author ownership."""
        comment = db.session.get(TopicComment, comment_id)
        if not comment:
            raise ValueError(f"Comment with ID {comment_id} not found.")
        
        if comment.author_id != author_id:
            raise PermissionError("You do not have permission to edit this comment.")
            
        comment.body = body
        comment.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        return comment

    @staticmethod
    def delete_comment(comment_id, user_id, is_sysadmin=False):
        """
        Delete a comment.
        Authorized for:
        - Comment author
        - Reflection author (essay owner)
        - SysAdmin
        """
        comment = db.session.get(TopicComment, comment_id)
        if not comment:
            raise ValueError(f"Comment with ID {comment_id} not found.")
            
        response = db.session.get(TopicResponse, comment.response_id)
        
        is_authorized = (
            comment.author_id == user_id or
            (response and response.author_id == user_id) or
            is_sysadmin
        )
        
        if not is_authorized:
            raise PermissionError("You do not have permission to delete this comment.")
            
        db.session.delete(comment)
        db.session.commit()
        return True


class CollectionService:
    @staticmethod
    def create_collection(user_id, name):
        """Create a new custom private collection folder."""
        collection = TopicCollection(
            user_id=user_id,
            name=name
        )
        db.session.add(collection)
        db.session.commit()
        return collection

    @staticmethod
    def delete_collection(collection_id, user_id):
        """Delete a collection and its items, verifying ownership."""
        collection = db.session.get(TopicCollection, collection_id)
        if not collection:
            raise ValueError(f"Collection with ID {collection_id} not found.")
            
        if collection.user_id != user_id:
            raise PermissionError("You do not own this collection.")
            
        db.session.delete(collection)
        db.session.commit()
        return True

    @staticmethod
    def add_item_to_collection(collection_id, user_id, topic_id=None, response_id=None):
        """Add a topic or response to a collection, checking ownership and duplicates."""
        if not topic_id and not response_id:
            raise ValueError("Must specify either a topic_id or response_id.")
            
        collection = db.session.get(TopicCollection, collection_id)
        if not collection:
            raise ValueError(f"Collection with ID {collection_id} not found.")
            
        if collection.user_id != user_id:
            raise PermissionError("You do not own this collection.")

        # Check duplicate
        existing = CollectionItem.query.filter_by(
            collection_id=collection_id,
            topic_id=topic_id,
            response_id=response_id
        ).first()
        
        if existing:
            return existing

        item = CollectionItem(
            collection_id=collection_id,
            topic_id=topic_id,
            response_id=response_id
        )
        db.session.add(item)
        db.session.commit()
        return item

    @staticmethod
    def remove_item_from_collection(collection_id, user_id, topic_id=None, response_id=None):
        """Remove a topic or response from a collection, verifying ownership."""
        collection = db.session.get(TopicCollection, collection_id)
        if not collection:
            raise ValueError(f"Collection with ID {collection_id} not found.")
            
        if collection.user_id != user_id:
            raise PermissionError("You do not own this collection.")

        item = CollectionItem.query.filter_by(
            collection_id=collection_id,
            topic_id=topic_id,
            response_id=response_id
        ).first()
        
        if item:
            db.session.delete(item)
            db.session.commit()
            return True
            
        return False

    @staticmethod
    def get_user_collections_for_item(user_id, topic_id=None, response_id=None):
        """Get list of user's collections that contain this specific item."""
        if not topic_id and not response_id:
            return []
            
        # Get all user collections
        user_col_ids = [col.id for col in TopicCollection.query.filter_by(user_id=user_id).all()]
        if not user_col_ids:
            return []
            
        items = CollectionItem.query.filter(
            CollectionItem.collection_id.in_(user_col_ids),
            CollectionItem.topic_id == topic_id,
            CollectionItem.response_id == response_id
        ).all()
        
        return [i.collection_id for i in items]

    @staticmethod
    def toggle_item_in_collections(user_id, collection_ids_to_add, collection_ids_to_remove, topic_id=None, response_id=None):
        """Bulk update collections checkboxes for a single item (AJAX support)."""
        if not topic_id and not response_id:
            raise ValueError("Must specify either a topic_id or response_id.")
            
        # Verify all targeted collections belong to user
        all_target_ids = list(set(collection_ids_to_add + collection_ids_to_remove))
        if all_target_ids:
            owned_count = TopicCollection.query.filter(
                TopicCollection.id.in_(all_target_ids),
                TopicCollection.user_id == user_id
            ).count()
            if owned_count != len(all_target_ids):
                raise PermissionError("You do not own all specified collections.")

        # Process additions
        for cid in collection_ids_to_add:
            # Check duplicate
            dup = CollectionItem.query.filter_by(
                collection_id=cid,
                topic_id=topic_id,
                response_id=response_id
            ).first()
            if not dup:
                db.session.add(CollectionItem(
                    collection_id=cid,
                    topic_id=topic_id,
                    response_id=response_id
                ))

        # Process removals
        if collection_ids_to_remove:
            CollectionItem.query.filter(
                CollectionItem.collection_id.in_(collection_ids_to_remove),
                CollectionItem.topic_id == topic_id,
                CollectionItem.response_id == response_id
            ).delete(synchronize_session=False)

        db.session.commit()
        return True
