from app import create_app, db
from app.models.user import User
from app.models.message import Message
from app.system_messaging import send_system_message

app = create_app()

def test_messaging():
    with app.app_context():
        # Clean up previous test messages
        print("Cleaning up old messages...")
        db.session.execute(db.text("DELETE FROM messages WHERE subject LIKE '[TEST]%'"))
        db.session.commit()
        
        # Get two users
        users = User.query.limit(2).all()
        if len(users) < 2:
            print("Need at least 2 users to test messaging.")
            return

        u1 = users[0]
        u2 = users[1]
        
        print(f"User 1: {u1.username} ({u1.id})")
        print(f"User 2: {u2.username} ({u2.id})")
        
        # 1. User 1 sends to User 2
        print("\n--- Test 1: User 1 sends to User 2 ---")
        msg1 = Message(
            sender_id=u1.id,
            recipient_id=u2.id,
            subject="[TEST] Hello from User 1",
            body="This is a test message body."
        )
        db.session.add(msg1)
        db.session.commit()
        print(f"Message sent. ID: {msg1.id}")
        
        # Verify receipt
        u2_inbox = u2.messages_received.all()
        received = next((m for m in u2_inbox if m.id == msg1.id), None)
        if received:
            print("User 2 received the message.")
        else:
            print("FAILED: User 2 did not receive the message.")
            
        # 2. System message to User 1
        print("\n--- Test 2: System message to User 1 ---")
        success, info = send_system_message(u1.id, "[TEST] System Notification", "This is a system message.")
        if success:
            print(f"System message sent: {info}")
            # Verify
            u1_inbox = u1.messages_received.all()
            sys_msg = next((m for m in u1_inbox if m.subject == "[TEST] System Notification"), None)
            if sys_msg:
                print(f"User 1 received system message. Sender: {sys_msg.sender_id} (Should be None)")
            else:
                print("FAILED: User 1 did not receive system message.")
        else:
            print(f"FAILED to send system message: {info}")

if __name__ == "__main__":
    test_messaging()
