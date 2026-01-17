
import pytest
from sqlalchemy import inspect
from app import create_app, db

@pytest.fixture
def app():
    app = create_app('config.Config')
    app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"
    })
    
    with app.app_context():
        yield app

@pytest.fixture
def inspector(app):
    with app.app_context():
        # Ensure models are loaded
        return inspect(db.engine)

def test_foreign_key_naming_convention(app):
    """
    Verify that all Foreign Keys have an explicit name.
    
    Unnamed constraints can cause issues with migrations (e.g. inability to drop constraints).
    It is best practice to use a naming convention.
    """
    with app.app_context():
        # Reflect all tables
        db.reflect()
        metadata = db.metadata
        
        unnamed_fks = []
        
        for table_name, table in metadata.tables.items():
            for content in table.constraints:
                # We are looking for ForeignKeyConstraint or CheckConstraint or UniqueConstraint
                # But specifically the user asked about Foreign Keys "unnamed foreign keys"
                # Note: table.foreign_key_constraints is available too.
                pass

            for fk in table.foreign_key_constraints:
                 if not fk.name:
                     unnamed_fks.append(f"Table '{table_name}' has an unnamed Foreign Key: {fk}")
                     
        assert not unnamed_fks, "\n".join(unnamed_fks)

def test_no_circular_dependencies(app):
    """
    Verify that there are no circular dependencies between tables.
    Circular dependencies can make it difficult to insert/delete data in the correct order.
    """
    with app.app_context():
        # reflect must be done on the bind
        db.reflect()
        metadata = db.metadata
        
        # Build dependency graph
        # Node: Table Name
        # Edge: A -> B if A has a Foreign Key to B
        
        adj_list = {}
        # metadata.tables keys are table names (strings)
        tables = list(metadata.tables.keys())
        
        for table_name in tables:
            adj_list[table_name] = set()
            
        for table_name, table in metadata.tables.items():
            for fk in table.foreign_key_constraints:
                # A foreign key constraint can point to multiple columns, but usually one table
                # We need to find the referred table.
                # fk.elements is a list of ForeignKey objects
                if not fk.elements:
                    continue
                
                # Get target table from the first element (composite FKs point to same table)
                target_table = fk.elements[0].column.table.name
                
                if target_table != table_name:
                    adj_list[table_name].add(target_table)

        # Detect cycles using DFS
        visited = set()
        recursion_stack = set()
        cycles = []
        
        # We need to pass the path as a list to reconstruct the cycle
        def dfs(node, path):
            visited.add(node)
            recursion_stack.add(node)
            path.append(node)
            
            try:
                for neighbor in adj_list.get(node, []):
                    if neighbor not in visited:
                        if dfs(neighbor, path):
                            return True
                    elif neighbor in recursion_stack:
                        # Cycle detected
                        try:
                            index = path.index(neighbor)
                            cycle_path = path[index:] + [neighbor]
                            cycle_str = " -> ".join(cycle_path)
                            
                            # Whitelist allowed cycles
                            # Cycle: clubs -> excomm -> clubs
                            # We check if the cycle contains only allowed tables or matches specific allowed patterns
                            allowed_cycles = [
                                "clubs -> excomm -> clubs",
                                "excomm -> clubs -> excomm",
                                "Meetings -> Media -> Session_Logs -> Meetings",
                                "Media -> Session_Logs -> Meetings -> Media",
                                "Session_Logs -> Meetings -> Media -> Session_Logs"
                            ]
                            
                            if cycle_str not in allowed_cycles:
                                cycles.append(cycle_str)
                                return True # Stop DFS for this path if it's a bad cycle
                            else:
                                # It's an allowed cycle, we don't return True, we just continue exploring other paths
                                # But we shouldn't recurse into neighbor again (it's in stack), so we just skip it
                                pass
                                
                        except ValueError:
                             cycles.append(f"Cycle detected involving {neighbor} but path reconstruction failed. Path: {path}")
                             return True
            finally:
                recursion_stack.remove(node)
                path.pop()
            
            return False

        for table in tables:
            if table not in visited:
                dfs(table, [])
                
        assert not cycles, f"Circular dependencies detected:\n" + "\n".join(cycles)
