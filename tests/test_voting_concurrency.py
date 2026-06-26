import os
import time
import unittest
import tempfile
import requests
from concurrent.futures import ThreadPoolExecutor
from datetime import date

# Add parent directory to path
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import User, Contact, AuthRole, Meeting, Permission, UserClub, Vote
from app.auth.permissions import Permissions
from config import Config

class ConcurrencyTestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SERVER_NAME = 'localhost.localdomain'

class VotingConcurrencyTestCase(unittest.TestCase):
    def setUp(self):
        self.target_url = os.environ.get('TARGET_URL')
        self.meeting_id = os.environ.get('MEETING_ID')
        self.concurrent_users = int(os.environ.get('CONCURRENT_USERS', '30'))
        
        if not self.target_url:
            # For local tests, we must use a file-based temporary SQLite DB
            # instead of in-memory (sqlite:///:memory:) so that concurrent threads
            # share the same database instance.
            self.db_fd, self.db_path = tempfile.mkstemp()
            
            class ThreadSafeConfig(ConcurrencyTestConfig):
                SQLALCHEMY_DATABASE_URI = f'sqlite:///{self.db_path}'
                SQLALCHEMY_ENGINE_OPTIONS = {}
            
            self.app = create_app(ThreadSafeConfig)
            self.app_context = self.app.app_context()
            self.app_context.push()
            
            # Configure db session and create tables
            db.session.configure(expire_on_commit=False)
            db.create_all()
            
            self.populate_data()
        else:
            if not self.meeting_id:
                # Default remote meeting ID to 1 if not specified
                self.meeting_id = '1'

    def tearDown(self):
        if not self.target_url:
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
            self.app_context.pop()
            
            # Clean up the temporary database file
            try:
                os.close(self.db_fd)
            except Exception:
                pass
            try:
                if os.path.exists(self.db_path):
                    os.unlink(self.db_path)
            except Exception:
                pass

    def populate_data(self):
        # Create Roles
        self.roles = {}
        for name, level in [('SysAdmin', 10), ('ClubAdmin', 5), ('Staff', 2), ('Member', 1), ('Guest', 0)]:
            role = AuthRole(name=name, description=f"{name} Role", level=level if level is not None else 0)
            db.session.add(role)
            self.roles[name] = role
        
        # Create Club
        from app.models import Club
        self.club = Club(
            club_no='000000',
            club_name='Test Club',
            district='Test District'
        )
        db.session.add(self.club)
        db.session.flush()

        # Define Permissions
        perm_objs = {}
        unique_perms = [
            Permissions.MEETING_VIEW_PUBLISHED,
            Permissions.VOTING_VIEW_RESULTS,
            Permissions.VOTING_TRACK_PROGRESS
        ]
        for p_name in unique_perms:
            p = Permission(name=p_name, description=p_name)
            db.session.add(p)
            perm_objs[p_name] = p
        db.session.flush()

        # Assign MEETING_VIEW_PUBLISHED globally to Guest
        self.roles['Guest'].permissions.append(perm_objs[Permissions.MEETING_VIEW_PUBLISHED])
        db.session.commit()

        # Create Meeting
        self.meeting = Meeting(
            Meeting_Number=100, 
            Meeting_Date=date.today(), 
            status='running',
            club_id=self.club.id
        )
        db.session.add(self.meeting)
        db.session.flush()
        db.session.commit()
        self.meeting_id = str(self.meeting.id)

    def test_concurrent_voting_page_loads(self):
        """Simulate 30+ concurrent users loading the voting page."""
        url_path = f"/voting/{self.meeting_id}"
        results = []
        
        def make_request(index):
            start_time = time.time()
            try:
                if self.target_url:
                    full_url = f"{self.target_url.rstrip('/')}{url_path}"
                    session = requests.Session()
                    resp = session.get(full_url, timeout=15)
                    status_code = resp.status_code
                    success = (status_code == 200)
                    error_msg = None if success else f"Status code: {status_code}"
                else:
                    client = self.app.test_client()
                    resp = client.get(url_path)
                    status_code = resp.status_code
                    success = (status_code == 200)
                    error_msg = None if success else f"Status code: {status_code}"
            except Exception as e:
                success = False
                status_code = 0
                error_msg = str(e)
            
            elapsed = time.time() - start_time
            return {
                'index': index,
                'success': success,
                'status_code': status_code,
                'elapsed': elapsed,
                'error': error_msg
            }

        print(f"\nStarting concurrency test with {self.concurrent_users} users...")
        if self.target_url:
            print(f"Targeting remote server: {self.target_url.rstrip('/')}{url_path}")
        else:
            print(f"Targeting local Flask test client: {url_path}")

        start_all = time.time()
        with ThreadPoolExecutor(max_workers=self.concurrent_users) as executor:
            futures = [executor.submit(make_request, i) for i in range(self.concurrent_users)]
            for fut in futures:
                results.append(fut.result())
        total_time = time.time() - start_all

        # Process results
        successes = [r for r in results if r['success']]
        failures = [r for r in results if not r['success']]
        
        elapsed_times = [r['elapsed'] for r in results]
        elapsed_times.sort()

        print("\n--- Concurrency Test Results Summary ---")
        print(f"Total concurrent users: {self.concurrent_users}")
        print(f"Successful requests: {len(successes)}")
        print(f"Failed requests: {len(failures)}")
        print(f"Total test execution time: {total_time:.4f} seconds")
        
        if elapsed_times:
            mean_time = sum(elapsed_times) / len(elapsed_times)
            median_time = elapsed_times[len(elapsed_times) // 2]
            p95_time = elapsed_times[int(len(elapsed_times) * 0.95)] if len(elapsed_times) >= 20 else elapsed_times[-1]
            min_time = elapsed_times[0]
            max_time = elapsed_times[-1]
            
            print(f"Min response time: {min_time:.4f}s")
            print(f"Mean response time: {mean_time:.4f}s")
            print(f"Median response time: {median_time:.4f}s")
            print(f"95th percentile response time: {p95_time:.4f}s")
            print(f"Max response time: {max_time:.4f}s")

        if failures:
            print("\nFailures:")
            for f in failures:
                print(f"  User {f['index']}: Status {f['status_code']}, Error: {f['error']}")

        # Assertions
        self.assertEqual(len(failures), 0, f"Expected 0 failures, but got {len(failures)} failures.")
        self.assertEqual(len(successes), self.concurrent_users, f"Expected {self.concurrent_users} successes, but got {len(successes)}.")

if __name__ == '__main__':
    unittest.main()
