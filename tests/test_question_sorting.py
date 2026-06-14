import unittest
from app.utils import group_roles_by_category

class TestQuestionSorting(unittest.TestCase):
    def test_group_roles_by_category_sorting(self):
        # Sample roles data with various categories
        roles = [
            {'role': 'Role 1', 'award_category': 'table-topic'},
            {'role': 'Role 2', 'award_category': 'speaker'},
            {'role': 'Role 3', 'award_category': 'role-taker'},
            {'role': 'Role 4', 'award_category': 'evaluator'},
            {'role': 'Role Custom', 'award_category': 'best-dresser'},
            {'role': 'Role 5', 'award_category': 'none'},
            {'role': 'Role 6', 'award_category': None},
        ]

        # Expected order: speaker, evaluator, role-taker, table-topic, custom, none/None
        grouped = group_roles_by_category(roles)
        categories = [key for key, group in grouped]
        core_categories = [c for c in categories if c and c != 'none']
        
        expected_order = ['speaker', 'evaluator', 'role-taker', 'table-topic', 'best-dresser']
        
        self.assertEqual(core_categories, expected_order, 
                         f"Categories were not sorted correctly. Got: {core_categories}")

if __name__ == '__main__':
    unittest.main()
