
import re

class SQLBackupParser:
    """Parses SQL backup files to extract specific table data."""
    
    TABLE_PATTERNS = {
        'contacts': r"INSERT INTO `Contacts` VALUES (.*?);",
        'users': r"INSERT INTO `Users` VALUES (.*?);", # Source table names are case sensitive in pattern matching? Source has `Users`? live has `users`?
        # The schema analysis showed source has `Contacts` and `Users` (Capitalized).
        # We need to MATCH the SOURCE SQL structure.
        'meetings': r"INSERT INTO `Meetings` VALUES (.*?);",
        'session_types': r"INSERT INTO `Session_Types` VALUES (.*?);",
        'session_logs': r"INSERT INTO `Session_Logs` VALUES (.*?);",
        'roster': r"INSERT INTO `roster` VALUES (.*?);",
        'media': r"INSERT INTO `Media` VALUES (.*?);",
        'achievements': r"INSERT INTO `achievements` VALUES (.*?);",
        'votes': r"INSERT INTO `votes` VALUES (.*?);",
        # Added support for clubs and excomm
        'clubs': r"INSERT INTO `clubs` VALUES (.*?);",
        'excomm': r"INSERT INTO `excomm` VALUES (.*?);",
    }
    
    DDL_PATTERNS = {
        'all': r"(CREATE TABLE `.*?` \(.*?\).*?;)"
    }

    
    # Define mapping of positions based on Source Schema (from backup analysis)
    # Positions are 0-indexed matches from the parsed values list
    # We need to manually map these or be robust.
    
    @staticmethod
    def parse_values(values_str):
        """Parses a MySQL VALUES string into a list of lists of values."""
        # This is a naive parser. A better one handles quoted strings containing commas.
        # Format: (1, 'val', ...), (2, 'val', ...)
        rows = []
        current_row = []
        in_string = False
        in_escape = False
        current_val = []
        quote_char = None
        
        # Split by "),("
        # Only simple split is not enough due to usage in strings
        
        # Regex to split top level tuples? 
        # Strategy: Use a dedicated SQL value parser logic
        
        # Let's write a state machine parser for the values part
        # values_str: "(...), (...)"
        
        buffer = ""
        in_tuple = False
        
        idx = 0
        length = len(values_str)
        
        while idx < length:
            char = values_str[idx]
            
            if in_string:
                if char == '\\':
                    current_val.append(char)
                    idx += 1
                    if idx < length:
                        current_val.append(values_str[idx])
                elif char == quote_char:
                    in_string = False
                    current_val.append(char)
                else:
                    current_val.append(char)
            else:
                if char == '(' and not in_tuple:
                    in_tuple = True
                    current_row = []
                    current_val = []
                elif char == ')' and in_tuple:
                    in_tuple = False
                    # End of value
                    val_str = "".join(current_val).strip()
                    # Pop last value
                    if val_str:
                         current_row.append(SQLBackupParser._clean_val(val_str))
                    rows.append(current_row)
                    current_val = [] # Reset
                elif char == ',' and in_tuple:
                     # End of a field
                     val_str = "".join(current_val).strip()
                     current_row.append(SQLBackupParser._clean_val(val_str))
                     current_val = []
                elif char in ["'", '"'] and in_tuple:
                    in_string = True
                    quote_char = char
                    current_val.append(char)
                elif in_tuple:
                    current_val.append(char)
            idx += 1
            
        return rows

    @staticmethod
    def _clean_val(val):
        if val.upper() == 'NULL':
            return None
        if val.startswith("'") and val.endswith("'"):
            return val[1:-1].replace("\\'", "'").replace('\\"', '"')
        if val.startswith('"') and val.endswith('"'):
            return val[1:-1].replace('\\"', '"').replace("\\'", "'")
        try:
            return int(val)
        except:
            return val

    def parse(self, file_path):
        """Reads SQL file and returns dict of list of rows per table."""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        parsed_data = {}

        # Parse tables using robust extraction
        for key, table_name in [
            ('contacts', 'Contacts'), 
            ('users', 'Users'), # Check casing if needed, usually Users or users
            ('meetings', 'Meetings'),
            ('session_types', 'Session_Types'),
            ('session_logs', 'Session_Logs'),
            ('roster', 'roster'),
            ('media', 'Media'),
            ('achievements', 'achievements'),
            ('votes', 'votes'),
            ('clubs', 'clubs'),
            ('excomm', 'excomm'),
            ('meeting_roles', 'meeting_roles')
        ]:
            # Regex to find START of insert
            # Case insensitive table name match might be safer?
            # Using specific known casing for now.
            # Handle potential backticks or not? definition has backticks.
            start_pattern = re.compile(rf"INSERT INTO `{table_name}` VALUES", re.IGNORECASE)
            
            # Find all start indices
            for match in start_pattern.finditer(content):
                start_idx = match.end()
                # Extract robustly until ;
                values_str = self._extract_values_str(content, start_idx)
                if values_str:
                    rows = self.parse_simple(values_str)
                    if key not in parsed_data: parsed_data[key] = []
                    parsed_data[key].extend(rows)

        # Parse DDL (Keep naive regex for DDL as it's less prone to data content issues)
        parsed_data['ddl'] = {}
        ddl_matches = re.findall(r"CREATE TABLE `(.*?)`.*?;", content, re.DOTALL)
        for table_name in ddl_matches:
             pattern = rf"(CREATE TABLE `{re.escape(table_name)}` .*?;)"
             match = re.search(pattern, content, re.DOTALL)
             if match:
                 parsed_data['ddl'][table_name] = match.group(1)

        return parsed_data

    def _extract_values_str(self, content, start_idx):
        """Walks content from start_idx to find the terminating semicolon, respecting quotes."""
        in_quote = False
        quote_char = ''
        i = start_idx
        n = len(content)
        
        while i < n:
            c = content[i]
            
            if in_quote:
                if c == '\\':
                    i += 1 # Skip the backslash
                    if i < n: # Skip the escaped char
                        i += 1
                    continue
                elif c == quote_char:
                    in_quote = False
            else:
                if c == ';':
                    return content[start_idx:i]
                elif c in ["'", '"']:
                    in_quote = True
                    quote_char = c
            i += 1
        return content[start_idx:] # EOF fallback

    def parse_simple(self, text):
        """
        Parses MySQL INSERT values. 
        text: (1, 'A'), (2, 'B')
        """
        # A simple regex approach that assumes standard mysqldump format
        # This regex matches: ( ... )
        # But we need to be careful about nested parens or quotes.
        # Given complexity, we will implement a character walker.
        
        rows = []
        row = []
        val_buffer = []
        in_quote = False
        quote_char = ''
        in_paren = False
        
        i = 0
        n = len(text)
        
        while i < n:
            c = text[i]
            
            if in_quote:
                if c == '\\':
                    val_buffer.append(c)
                    if i + 1 < n:
                        val_buffer.append(text[i+1])
                        i += 1
                elif c == quote_char:
                    in_quote = False
                    val_buffer.append(c)
                else:
                    val_buffer.append(c)
            
            else:
                if c == '(':
                    if not in_paren:
                        in_paren = True
                        row = []
                        val_buffer = []
                    else:
                        val_buffer.append(c)
                
                elif c == ')':
                    if in_paren:
                        # End of row? Check if next char is comma or EOF
                        # But wait, we separate values by commas inside parens
                        # We need to know if this ) closes the row
                         val_str = "".join(val_buffer).strip()
                         if val_str:
                             row.append(self._clean_val(val_str))
                         rows.append(row)
                         in_paren = False
                         val_buffer = []

                elif c == ',':
                    if in_paren:
                        val_str = "".join(val_buffer).strip()
                        row.append(self._clean_val(val_str))
                        val_buffer = []
                
                elif c in ["'", '"']:
                    in_quote = True
                    quote_char = c
                    val_buffer.append(c)
                
                elif c in [' ', '\n', '\t']:
                    if val_buffer: # If checking strict valid sql, spaces outside quotes matter? 
                       # Inside a value (123) spaces ok?
                       val_buffer.append(c)
                else:
                    val_buffer.append(c)

            i += 1
            
        return rows
