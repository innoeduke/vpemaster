import shutil
import os

BACKUP_FILE = 'instance/backup_20260112.sql'
BACKUP_COPY = 'instance/backup_20260112.sql.bak'

def patch_backup():
    if not os.path.exists(BACKUP_FILE):
        print(f"Error: {BACKUP_FILE} not found.")
        return

    # Create a backup copy
    shutil.copy2(BACKUP_FILE, BACKUP_COPY)
    print(f"Created backup copy at {BACKUP_COPY}")

    with open(BACKUP_FILE, 'r') as f:
        lines = f.readlines()

    new_lines = []
    in_meetings_table = False
    meetings_insert_processed = False

    for line in lines:
        # Check for start of Meetings table definition
        if line.strip().startswith('CREATE TABLE `Meetings`'):
            in_meetings_table = True
        
        # Check for end of Meetings table (to stop flag)
        if in_meetings_table and line.strip().startswith(') ENGINE='):
            in_meetings_table = False

        # Add nps column after status
        if in_meetings_table and '`status` enum' in line:
            new_lines.append(line)
            print("Injecting nps column definition.")
            new_lines.append("  `nps` float DEFAULT NULL,\n")
            continue

        # Process INSERT INTO `Meetings`
        if line.strip().startswith('INSERT INTO `Meetings`'):
            print("Found INSERT INTO `Meetings`. Processing values.")
            val_idx = line.find("VALUES ")
            if val_idx != -1:
                prefix = line[:val_idx + 7]
                values_part = line[val_idx + 7:].strip()
                if values_part.endswith(';'):
                    values_part = values_part[:-1]
                    suffix = ";\n"
                else:
                    suffix = "\n" 
                
                if values_part.startswith('('): values_part = values_part[1:]
                if values_part.endswith(')'): values_part = values_part[:-1]
                
                tuples = values_part.split("),(")
                new_tuples = []
                for t in tuples:
                    last_comma = t.rfind(',')
                    second_last = t.rfind(',', 0, last_comma)
                    
                    if second_last != -1:
                        new_t = t[:second_last] + ",NULL" + t[second_last:]
                        new_tuples.append(new_t)
                    else:
                        new_tuples.append(t)
                
                new_line = prefix + "(" + "),(".join(new_tuples) + ")" + suffix
                new_lines.append(new_line)
                meetings_insert_processed = True
                continue
        
        new_lines.append(line)

    if not meetings_insert_processed:
        print("Warning: Did not find INSERT INTO `Meetings` line.")

    with open(BACKUP_FILE, 'w') as f:
        f.writelines(new_lines)
    print(f"Successfully patched {BACKUP_FILE}")

if __name__ == "__main__":
    patch_backup()
