import unittest
from app.services.backup_parser import SQLBackupParser

class SQLBackupParserReproductionTestCase(unittest.TestCase):
    def test_parse_simple_strings(self):
        parser = SQLBackupParser()
        
        # Case 1: Standard Quoted String
        values_str = "(1, 'testuser', 'other')"
        rows = parser.parse_simple(values_str)
        self.assertEqual(rows[0][1], 'testuser')
        self.assertEqual(len(rows[0][1]), 8)
        
        # Case 2: String with spaces
        values_str = "(2, 'test user', 'other')"
        rows = parser.parse_simple(values_str)
        self.assertEqual(rows[0][1], 'test user')
        
    def test_parse_simple_truncation_suspicion(self):
        parser = SQLBackupParser()
        
        # Case A: Double quoted
        values_str = '(3, "testuser", "other")'
        rows = parser.parse_simple(values_str)
        self.assertEqual(rows[0][1], 'testuser')
        
        # Case B: Extra spaces
        values_str = "(4, 'testuser' , 'other')"
        rows = parser.parse_simple(values_str)
        self.assertEqual(rows[0][1], 'testuser')

        # Case C: Is it possible _clean_val is too aggressive?
        # If the input ALREADY lacked quotes? 
        values_str = "(5, testuser, other)" 
        # Note: SQL usually requires quotes for strings, but if backup is loose?
        rows = parser.parse_simple(values_str)
        self.assertEqual(rows[0][1], 'testuser') 
        
        # Case D: Escaped quotes
        values_str = r"(6, 'test\'user', 'other')"
        rows = parser.parse_simple(values_str)
        self.assertEqual(rows[0][1], "test'user")

    def test_bulk_parsing(self):
        """Test with content similar to a real backup line."""
        parser = SQLBackupParser()
        # Simulated line from 'users' table
        # Schema: id, username, created_at, password_hash, contact_id, email, status
        line = "(1, 'superuser', '2023-01-01', 'hash', 100, 'admin@test.com', 'active')"
        rows = parser.parse_simple(line)
        self.assertEqual(rows[0][1], 'superuser')
        self.assertEqual(len(rows[0][1]), 9)

if __name__ == '__main__':
    unittest.main()
