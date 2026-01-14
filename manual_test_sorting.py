from app.utils import group_roles_by_category

def test_group_roles_by_category_sorting():
    # Sample roles data with various categories
    roles = [
        {'role': 'Role 1', 'award_category': 'table-topic'},
        {'role': 'Role 2', 'award_category': 'speaker'},
        {'role': 'Role 3', 'award_category': 'role-taker'},
        {'role': 'Role 4', 'award_category': 'evaluator'},
        {'role': 'Role 5', 'award_category': 'none'},
        {'role': 'Role 6', 'award_category': None},
    ]

    # Run the function
    grouped = group_roles_by_category(roles)
    
    # Extract the category keys from the result
    categories = [key for key, group in grouped]
    
    # Filter out None/none for the core check
    core_categories = [c for c in categories if c and c != 'none']
    
    expected_order = ['speaker', 'evaluator', 'role-taker', 'table-topic']
    
    print(f"Got categories: {core_categories}")
    
    if core_categories == expected_order:
        print("SUCCESS: Sorting is correct.")
    else:
        print(f"FAILURE: Expected {expected_order}, but got {core_categories}")

if __name__ == '__main__':
    try:
        test_group_roles_by_category_sorting()
    except Exception as e:
        print(f"ERROR: {e}")
