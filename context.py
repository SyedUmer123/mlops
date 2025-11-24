import ast
import tiktoken

def extract_skeleton(code_content):
    """
    Parses Python code and returns a 'Skeleton' (Imports, Globals, Signatures).
    It removes the actual logic inside functions to save tokens.
    """
    tree = ast.parse(code_content)
    skeleton_lines = []
    
    # 1. Extract Imports (Vital for context)
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            skeleton_lines.append(ast.get_source_segment(code_content, node))

    skeleton_lines.append("\n# --- GLOBALS & MODELS ---\n")

    # 2. Extract Global Variables & Pydantic Models (Vital for data structure)
    for node in tree.body:
        # If it's a class (Pydantic Model), keep the WHOLE thing
        if isinstance(node, ast.ClassDef):
            skeleton_lines.append(ast.get_source_segment(code_content, node))
        
        # If it's a global variable assignment (e.g. todos = {})
        elif isinstance(node, ast.Assign):
            skeleton_lines.append(ast.get_source_segment(code_content, node))

    skeleton_lines.append("\n# --- FUNCTION SIGNATURES (Logic Removed) ---\n")

    # 3. Extract Function Definitions (But replace body with '...')
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            # Get the decorators (e.g. @app.get)
            decorators = []
            for dec in node.decorator_list:
                dec_source = ast.get_source_segment(code_content, dec)
                decorators.append(f"@{dec_source}")
            
            # Reconstruct the signature
            args = ast.get_source_segment(code_content, node.args)
            
            # Construct the skeleton function
            func_skel = f"{'\n'.join(decorators)}\ndef {node.name}({args}):\n    ..."
            skeleton_lines.append(func_skel)

    return "\n\n".join(skeleton_lines)

# Test it immediately
if __name__ == "__main__":
    with open("app.py", "r") as f:
        code = f.read()
    print(extract_skeleton(code))
    
