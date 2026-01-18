from app import create_app, db
from app.models.user import User
from app.models.message import Message

app = create_app()

def reproduce_bug():
    with app.app_context():
        # Get a user (User 1)
        u1 = User.query.get(1)
        if not u1:
            print("User 1 not found")
            return

        print(f"Testing with User: {u1.username} ({u1.id})")
        
        # 1. Send message to SELF
        print("\n--- Sending message to SELF ---")
        msg = Message(
            sender_id=u1.id,
            recipient_id=u1.id,
            subject="[TEST] Self Message",
            body="Reproduction test"
        )
        db.session.add(msg)
        db.session.commit()
        msg_id = msg.id
        print(f"Message created. ID: {msg_id}")
        
        # 2. Simulate Delete Request (Default Logic)
        # In the route:
        # if msg.recipient_id == current_user.id:
        #     msg.deleted_by_recipient = True
        # elif msg.sender_id == current_user.id:
        #     msg.deleted_by_sender = True
        
        print("Simulating delete request with context='sent'...")
        # Since u1 is BOTH recipient and sender, we pass 'sent' to target sender flag
        context = 'sent'
        deleted = False
        
        if context == 'inbox':
            if msg.recipient_id == u1.id:
                msg.deleted_by_recipient = True
                deleted = True
        elif context == 'sent':
            if msg.sender_id == u1.id:
                msg.deleted_by_sender = True
                deleted = True
        
        db.session.commit()
        
        # 3. Verify Flags
        db.session.refresh(msg)
        print(f"Deleted by Recipient: {msg.deleted_by_recipient}")
        print(f"Deleted by Sender: {msg.deleted_by_sender}")
        
        if msg.deleted_by_sender:
            print("\nRESULT: Success! 'deleted_by_sender' is True when context='sent'.")
        else:
            print("\nRESULT: FAILED. 'deleted_by_sender' is still False.")

        # Cleanup
        db.session.delete(msg)
        db.session.commit()

if __name__ == "__main__":
    reproduce_bug()
