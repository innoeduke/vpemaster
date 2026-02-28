import os
import argparse
from jinja2 import Environment, FileSystemLoader

def check_template(env, template_dir, name):
    """Parses a single Jinja template to check for syntax errors."""
    try:
        with open(os.path.join(template_dir, name), 'r') as f:
            source = f.read()
        env.parse(source)
        print(f"✅ {name}: Parsed successfully.")
        return True
    except Exception as e:
        print(f"❌ {name}: Error - {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Check Jinja2 templates for syntax errors.")
    parser.add_argument('files', nargs='*', help="Specific template files to check (relative to app/templates). If empty, checks all .html files.")
    parser.add_argument('--template-dir', default='app/templates', help="Directory containing templates (default: app/templates)")
    
    args = parser.parse_args()
    
    # Ensure template_dir is absolute
    base_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    template_dir = os.path.join(base_dir, args.template_dir)
    
    if not os.path.exists(template_dir):
        print(f"Error: Template directory not found at {template_dir}")
        return

    env = Environment(loader=FileSystemLoader(template_dir))
    
    files_to_check = args.files
    if not files_to_check:
        # Scan for all .html files
        files_to_check = []
        for root, _, files in os.walk(template_dir):
            for file in files:
                if file.endswith('.html'):
                    rel_path = os.path.relpath(os.path.join(root, file), template_dir)
                    files_to_check.append(rel_path)
    
    print(f"Checking {len(files_to_check)} templates in {template_dir}...")
    
    success_count = 0
    for file in sorted(files_to_check):
        if check_template(env, template_dir, file):
            success_count += 1
            
    print(f"\nSummary: {success_count}/{len(files_to_check)} templates passed.")
    if success_count < len(files_to_check):
        exit(1)

if __name__ == "__main__":
    main()
