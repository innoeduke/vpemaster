import re
import shutil
import os
import sys

# Configuration
BASELINE_SCHEMA = 'instance/vpemaster_schema.sql'
BACKUP_FILE = 'instance/backup_20260112.sql'
BACKUP_COPY = 'instance/backup_20260112.sql.bak'

def read_file(path):
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        return f.read()

def extract_create_table(content):
    """
    Returns a dictionary: {table_name: create_table_block_string}
    """
    # Regex to capture CREATE TABLE statements.
    # We assume standard mysqldump format: CREATE TABLE `Name` ( ... ) ENGINE=...;
    # We capture up to 'ENGINE=...;' (inclusive)
    # The 're.DOTALL' allows matching across newlines.
    
    # Pattern explanation:
    # CREATE TABLE `(\w+)`  -> Matches start and captures table name
    # \s*\(                 -> Matches opening parenthesis
    # .*?                   -> Matches content (non-greedy)
    # \) ENGINE=.*?;        -> Matches closing parenthesis, ENGINE part, and semicolon
    
    pattern = re.compile(r'(CREATE TABLE `(\w+)` \s*\(.*?\)\s*ENGINE=.*?;)', re.DOTALL | re.IGNORECASE)
    matches = pattern.findall(content)
    
    definitions = {}
    for full_match, table_name in matches:
        definitions[table_name] = full_match
    return definitions

def normalize_schema(schema_str):
    """
    Normalizes schema string for comparison.
    - Removes AUTO_INCREMENT=...
    - Normalizes whitespace
    """
    # Remove AUTO_INCREMENT=123
    s = re.sub(r'AUTO_INCREMENT=\d+', '', schema_str)
    # Remove comments if any (though usually mysqldump creates clean create statements)
    # Normalize whitespace
    s = " ".join(s.split())
    return s

def count_columns_in_def(create_stmt):
    """Basic column counting: counts commas + 1 inside the main parens, discounting keys."""
    # This is a heuristic. A robust SQL parser is better but for this task we use regex.
    # Extract content between first ( and last )
    match = re.search(r'\((.*)\) ENGINE', create_stmt, re.DOTALL)
    if not match:
        return 0
    body = match.group(1)
    
    count = 0
    lines = body.split('\n')
    for line in lines:
        line = line.strip()
        if not line: continue
        if line.upper().startswith(('PRIMARY KEY', 'KEY', 'UNIQUE KEY', 'CONSTRAINT')):
            continue
        if line.startswith('`'):
            count += 1
    return count

def patch_insert_statements(content, table_name, old_col_count, new_col_count):
    """
    Patches INSERT INTO `table_name` VALUES ... statements.
    If new_col_count > old_col_count, appends NULLs.
    """
    diff = new_col_count - old_col_count
    if diff <= 0:
        return content # No patching needed if columns removed or same (removed cols is harder to patch safely automatically)

    print(f"  -> Patching INSERTs for table `{table_name}`: adding {diff} NULL(s) per row.")
    
    def replacer(match):
        # match.group(0) is the whole line
        line = match.group(0)
        # We need to process the VALUES part.
        # INSERT INTO `table` VALUES (1, 'a'), (2, 'b');
        val_start = line.find("VALUES ")
        if val_start == -1: return line
        
        prefix = line[:val_start + 7] # INSERT INTO ... VALUES 
        values_str = line[val_start + 7:].strip()
        if values_str.endswith(';'):
            values_str = values_str[:-1]
            suffix = ";"
        else:
            suffix = ""
            
        # Basic parsing of (val1, val2), (val3, val4)
        # We assume values don't contain '),' that would break simple split. 
        # For huge dumps this might be fragile if data contains ");" strings.
        # But for this specific task context it should be sufficient.
        
        # Split by `),(` then restore.
        # A clearer way: regex replace `)` at the end of a tuple with `, NULL)`
        # But tuples are separated by `,`.
        
        # HEURISTIC: Replace `)` with `, NULL... )` but we must be careful not to match inside strings.
        # Given the task complexity constraint, we will try a robust split.
        
        # Actually, simpler approach:
        # Each row is enclosed in (...).
        # We can just replace all `)` with `, NULL)` ? No, that breaks strings/nested parens.
        # But SQL dump values usually strictly formatted: `(v1,v2),(v3,v4)`
        
        new_values = []
        # Remove outer wrapper if single line? No, it's a list.
        # Let's iterate manually or use regex carefully.
        
        # Regex to match a tuple: \((.*?)\)  -- non-greedy match inside parens.
        # But we want to match THE closing paren of the tuple.
        # Since it's a dump, usually `(1,2,3),(4,5,6)`
        
        # Let's just assume standard mysqldump structure.
        # We want to insert `diff` amount of `,NULL` before every `)` that closes a row.
        # Rows are separated by `),(`.
        
        # So we can replace `),(` with `,NULL` * diff + `),(`
        # And the last `)` with `,NULL` * diff + `)`
        
        padding = ",NULL" * diff
        
        # Does the value string start with `(`?
        if not values_str.startswith('('): return line
        
        # Replace the separator
        patched_values = values_str.replace("),(", f"{padding}),(")
        
        # Replace the final closing paren
        if patched_values.endswith(')'):
             patched_values = patched_values[:-1] + f"{padding})"
             
        return prefix + patched_values + suffix
        
    # Regex for the specific table insert.
    # INSERT INTO `table_name` VALUES ...
    pattern = re.compile(rf'INSERT INTO `{table_name}` VALUES .*?;', re.DOTALL)
    
    return pattern.sub(replacer, content)

def main():
    # Redirect stdout to a log file
    log_file = 'fix_log.txt'
    with open(log_file, 'w') as f:
        sys.stdout = f
        
        if not os.path.exists(BASELINE_SCHEMA):
            print(f"Error: Baseline schema not found at {BASELINE_SCHEMA}")
            return
        if not os.path.exists(BACKUP_FILE):
            print(f"Error: Backup file not found at {BACKUP_FILE}")
            return

        print(f"Reading schemas...")
        baseline_content = read_file(BASELINE_SCHEMA)
        backup_content = read_file(BACKUP_FILE)
        
        baseline_tables = extract_create_table(baseline_content)
        backup_tables = extract_create_table(backup_content)
        
        print(f"Baseline tables found: {len(baseline_tables)}")
        print(f"Backup tables found: {len(backup_tables)}")
        
        mismatches = []
        
        for table, base_def in baseline_tables.items():
            if table not in backup_tables:
                print(f"[WARN] Table `{table}` missing in backup. (Current script does not auto-add missing tables)")
                continue
                
            target_def = backup_tables[table]
            
            norm_base = normalize_schema(base_def)
            norm_target = normalize_schema(target_def)
            
            if norm_base != norm_target:
                print(f"[MISMATCH] Table `{table}` definitions differ.")
                mismatches.append(table)
        
        if not mismatches:
            print("No schema mismatches found! Backup is consistent.")
            return

        print(f"Found {len(mismatches)} mismatches. Creating backup copy...")
        shutil.copy2(BACKUP_FILE, BACKUP_COPY)
        print(f"Backup created at {BACKUP_COPY}")
        
        new_backup_content = backup_content
        
        for table in mismatches:
            print(f"Patching table `{table}`...")
            old_def = backup_tables[table]
            new_def = baseline_tables[table]
            
            # 1. Replace definition
            new_backup_content = new_backup_content.replace(old_def, new_def)
            
            # 2. Check column counts for INSERT patching
            old_cols = count_columns_in_def(old_def)
            new_cols = count_columns_in_def(new_def)
            
            if new_cols > old_cols:
                print(f"  -> Column count changed: {old_cols} -> {new_cols}. Patching data...")
                new_backup_content = patch_insert_statements(new_backup_content, table, old_cols, new_cols)
            elif new_cols < old_cols:
                 print(f"  -> [WARNING] Column count decreased: {old_cols} -> {new_cols}. Data not patched (complex truncation). Manual review needed.")

        # Write back
        with open(BACKUP_FILE, 'w', encoding='utf-8') as f:
            f.write(new_backup_content)
            
        print("Done. Backup file updated.")

if __name__ == "__main__":
    main()
