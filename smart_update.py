import ast
import re

def get_changed_functions(app_code, diff):
    """
    Returns a set of function names in app_code that were modified by the diff.
    """
    changed_lines = set()
    
    # 1. Parse Diff to find changed line numbers
    # Look for patterns like @@ -10,4 +15,5 @@
    hunk_headers = re.findall(r"^@@ -\d+,\d+ \+(\d+),(\d+) @@", diff, re.MULTILINE)
    for start_line, count in hunk_headers:
        start = int(start_line)
        # Add all lines in this hunk range
        for i in range(int(count)):
            changed_lines.add(start + i)

    # 2. Parse Code to find which function owns those lines
    tree = ast.parse(app_code)
    changed_functions = set()

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Check if the function's line range overlaps with changed_lines
            func_lines = set(range(node.lineno, node.end_lineno + 1))
            if not changed_lines.isdisjoint(func_lines):
                changed_functions.add(node.name)
                
    return changed_functions

def update_test_file(test_file_path, new_test_code, function_name):
    """
    Reads existing tests, removes the old test_function_name, and appends the new one.
    """
    if not os.path.exists(test_file_path):
        # If file doesn't exist, just write the new code
        with open(test_file_path, "w") as f:
            f.write(new_test_code)
        return

    with open(test_file_path, "r") as f:
        existing_code = f.read()

    # We assume the test function is named 'test_' + function_name
    test_func_name = f"test_{function_name}"
    
    # 1. Remove the old test function using AST to find its range
    try:
        tree = ast.parse(existing_code)
        lines = existing_code.splitlines()
        
        # Find the node to delete
        node_to_remove = None
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == test_func_name:
                    node_to_remove = node
                    break
        
        if node_to_remove:
            # Slicing out the old function
            # We recreate the file content skipping the lines of the old function
            start = node_to_remove.lineno - 1
            end = node_to_remove.end_lineno
            del lines[start:end]
            existing_code = "\n".join(lines)
            
    except SyntaxError:
        print("Warning: Could not parse existing test file. Appending blindly.")

    # 2. Append the new test code
    # Ensure we have imports if it's a new file, or just append the function
    final_code = existing_code.strip() + "\n\n" + new_test_code.strip()
    
    with open(test_file_path, "w") as f:
        f.write(final_code)

def get_existing_test_code(test_file_path, func_name):
    """
    Reads the existing test file and returns the source code 
    of the test function (e.g., test_login) if it exists.
    """
    if not os.path.exists(test_file_path):
        return None

    with open(test_file_path, "r") as f:
        code = f.read()

    test_func_name = f"test_{func_name}"
    try:
        tree = ast.parse(code)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == test_func_name:
                    return ast.unparse(node)
    except:
        pass # If parsing fails, just return None
    return None