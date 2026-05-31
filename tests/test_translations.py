import unittest
import sys
import os

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.translations.translations import get_locale, translate, _
from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    SECRET_KEY = 'test-secret-key'

class TranslationsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()

    def tearDown(self):
        self.app_context.pop()

    def test_default_locale(self):
        """Test default locale is English when no request context or headers exist."""
        # Outside request context
        self.assertEqual(get_locale(), 'en')

        # Inside request context with no preferences
        with self.app.test_request_context():
            self.assertEqual(get_locale(), 'en')

    def test_locale_from_headers(self):
        """Test locale detection from Accept-Language HTTP headers."""
        with self.app.test_request_context(headers={'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'}):
            self.assertEqual(get_locale(), 'zh_CN')

        with self.app.test_request_context(headers={'Accept-Language': 'en-US,en;q=0.9'}):
            self.assertEqual(get_locale(), 'en')

    def test_locale_from_session(self):
        """Test locale detection from session overrides headers."""
        with self.app.test_request_context(headers={'Accept-Language': 'en-US'}):
            from flask import session
            session['locale'] = 'zh_CN'
            self.assertEqual(get_locale(), 'zh_CN')

    def test_translation_lookups(self):
        """Test translation lookup behavior for English and Simplified Chinese."""
        # When locale is English, translation should return key itself
        with self.app.test_request_context():
            # Force locale to English
            from flask import session
            session['locale'] = 'en'
            self.assertEqual(translate('Calendar'), 'Calendar')
            self.assertEqual(translate('Agenda'), 'Agenda')
            # Test missing key in English
            self.assertEqual(translate('Nonexistent Key'), 'Nonexistent Key')

        # When locale is Chinese, should look up value in JSON
        with self.app.test_request_context():
            from flask import session
            session['locale'] = 'zh_CN'
            self.assertEqual(translate('Calendar'), '日历')
            self.assertEqual(translate('Agenda'), '日程表')
            # Test missing key fallback
            self.assertEqual(translate('Nonexistent Key'), 'Nonexistent Key')

    def test_translation_formatting(self):
        """Test string formatting parameters inside translate helper."""
        with self.app.test_request_context():
            from flask import session
            session['locale'] = 'zh_CN'
            # Format using % kwargs
            result = translate('Meeting #%(num)s is %(status)s', num=20, status='进行中')
            self.assertEqual(result, '会议 #20 状态为 进行中')

            # Test fallback format if translation key has no formatting but called with args
            self.assertEqual(translate('Calendar', extra='test'), '日历')

    def test_set_language_route(self):
        """Test the language toggle endpoint updates session and redirects."""
        with self.client:
            # 1. Switch to Chinese
            resp = self.client.get('/set_language/zh_CN', headers={'Referer': 'http://localhost/agenda'})
            # Should redirect back to referrer
            self.assertEqual(resp.status_code, 302)
            self.assertIn('http://localhost/agenda', resp.headers['Location'])
            
            # Check session locale is updated
            from flask import session
            self.assertEqual(session.get('locale'), 'zh_CN')

            # 2. Switch to English
            resp = self.client.get('/set_language/en', headers={'Referer': 'http://localhost/agenda'})
            self.assertEqual(resp.status_code, 302)
            self.assertEqual(session.get('locale'), 'en')

            # 3. Switch with invalid referrer (failsafe fallback to index)
            resp = self.client.get('/set_language/zh_CN', headers={'Referer': 'http://malicious.com'})
            self.assertEqual(resp.status_code, 302)
            # Host URL matches localhost, so malicious redirect falls back to index
            self.assertEqual(resp.headers['Location'], '/')

if __name__ == '__main__':
    unittest.main()
