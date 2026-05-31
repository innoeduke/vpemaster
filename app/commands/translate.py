import os
import re
import json
import click
from flask.cli import with_appcontext

# Regex to match _('...') and _("...") with negative lookbehind for escaping, supporting optional arguments
SINGLE_QUOTE_REGEX = re.compile(r'_\(\s*\'(.*?)(?<!\\)\'\s*[,)]')
DOUBLE_QUOTE_REGEX = re.compile(r'_\(\s*\"(.*?)(?<!\\)\"\s*[,)]')

@click.command('translate-scan')
@with_appcontext
def translate_scan():
    """Scan the codebase for translatable strings and update JSON translation files."""
    click.echo("Scanning codebase for translatable strings...")
    
    found_keys = set()
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # 1. Scan Python files and HTML templates
    scan_dirs = [
        os.path.join(base_dir), # app/ (includes subdirectories like auth, models, templates)
    ]
    
    for scan_dir in scan_dirs:
        for root, _, files in os.walk(scan_dir):
            # Skip python virtual environments or cache/node_modules if any
            if any(p in root for p in ['__pycache__', 'node_modules', '.venv', 'migrations']):
                continue
                
            for file in files:
                if not (file.endswith('.py') or file.endswith('.html')):
                    continue
                    
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    # Find all matches
                    matches_single = SINGLE_QUOTE_REGEX.findall(content)
                    matches_double = DOUBLE_QUOTE_REGEX.findall(content)
                    
                    for match in matches_single + matches_double:
                        # Clean up escaped quotes
                        match_clean = match.replace("\\'", "'").replace('\\"', '"')
                        if match_clean:
                            found_keys.add(match_clean)
                except Exception as e:
                    click.echo(f"Error reading file {file_path}: {e}")
                    
    click.echo(f"Found {len(found_keys)} unique translatable strings in codebase.")
    
    # 2. Update translation JSON files
    translations_dir = os.path.join(base_dir, 'translations')
    if not os.path.exists(translations_dir):
        os.makedirs(translations_dir)
        click.echo(f"Created translations directory: {translations_dir}")
        
    updated_files = 0
    for file in os.listdir(translations_dir):
        if not file.endswith('.json'):
            continue
            
        file_path = os.path.join(translations_dir, file)
        try:
            # Read existing translations
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    try:
                        data = json.load(f)
                    except json.JSONDecodeError:
                        data = {}
            else:
                data = {}
                
            # Merge new keys
            added_count = 0
            for key in sorted(found_keys):
                if key not in data:
                    data[key] = ""  # Seed new key with empty translation
                    added_count += 1
                    
            # Sort the translation keys for clean diffs
            sorted_data = {k: data[k] for k in sorted(data.keys())}
            
            # Save back
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(sorted_data, f, ensure_ascii=False, indent=2)
                
            click.echo(f"Updated {file}: added {added_count} new keys (total {len(sorted_data)} keys).")
            updated_files += 1
        except Exception as e:
            click.echo(f"Error updating translation file {file_path}: {e}")
            
    if updated_files == 0:
        click.echo("No translation JSON files found in app/translations/ directory to update.")
        click.echo("Please ensure at least one locale JSON file exists (e.g. app/translations/zh_CN.json).")
    else:
        click.echo("Scan and merge complete.")
