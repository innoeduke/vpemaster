import os
import pytest

def test_no_important_in_css():
    """
    Ensures that no CSS files in app/static/css/components and app/static/css/core
    contain the '!important' tag.
    """
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    target_dirs = [
        os.path.join(base_dir, 'app/static/css/components'),
        os.path.join(base_dir, 'app/static/css/core')
    ]
    
    issues = []
    
    for target_dir in target_dirs:
        if not os.path.exists(target_dir):
            continue
            
        for root, _, files in os.walk(target_dir):
            for file in files:
                if file.endswith('.css'):
                    file_path = os.path.join(root, file)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                        # Remove comments (simple multi-line comment removal)
                        import re
                        clean_content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
                        
                        if '!important' in clean_content.lower():
                            # If found, find the line number in the original content for better reporting
                            lines = content.splitlines()
                            for line_no, line in enumerate(lines, 1):
                                # Check if the line has !important and if that part is not commented
                                # This is still a bit simplified but better
                                if '!important' in line.lower():
                                    # Very basic check: is it in a single line comment?
                                    stripped = line.strip()
                                    if stripped.startswith('/*') or stripped.endswith('*/') or (stripped.count('/*') > 0 and stripped.find('!important') > stripped.find('/*')):
                                         # Likely in a comment or partially commented
                                         # For simplicity, if it's in the clean_content it's an issue
                                         pass
                                    
                                    rel_path = os.path.relpath(file_path, base_dir)
                                    # Only add if it's still in the clean content somehow
                                    # This is tricky because we removed comments. 
                                    # Let's just use the clean content check for the whole file first.
                            
                            # Re-scanning to find exactly which lines are NOT comments
                            # A better way:
                            curr_line = 1
                            in_comment = False
                            i = 0
                            while i < len(content):
                                if not in_comment and content[i:i+2] == '/*':
                                    in_comment = True
                                    i += 2
                                elif in_comment and content[i:i+2] == '*/':
                                    in_comment = False
                                    i += 2
                                elif not in_comment:
                                    if content[i:i+10].lower() == '!important':
                                        # Find line number
                                        line_no = content[:i].count('\n') + 1
                                        line_text = content.splitlines()[line_no-1]
                                        rel_path = os.path.relpath(file_path, base_dir)
                                        issues.append(f"{rel_path}:{line_no}: {line_text.strip()}")
                                        i += 10
                                    else:
                                        i += 1
                                else:
                                    i += 1
    
    if issues:
        pytest.fail(f"Found '!important' in restricted CSS files:\n" + "\n".join(issues))
