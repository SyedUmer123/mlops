import ast

def extract_skeleton(code: str) -> str:
    """
    Parses Python code and returns a skeleton with:
    - Imports
    - Global variables
    - Classes and models (with fields)
    - Functions (preserving arguments, return types, AND DECORATORS)
    - Replaces function bodies with '...'
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return "Error parsing code skeleton."

    skeleton_lines = []

    for node in tree.body:
        # Preserve Imports
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            skeleton_lines.append(ast.get_source_segment(code, node))
        
        # Preserve Global Variables (assignments)
        elif isinstance(node, ast.Assign):
            skeleton_lines.append(ast.get_source_segment(code, node))

        # Preserve Classes (Pydantic Models etc)
        elif isinstance(node, ast.ClassDef):
            # We want the full class definition including fields
            class_src = ast.get_source_segment(code, node)
            # Simple heuristic: keep the class signature and fields, assume methods might need pruning
            # For simplicity in this specific bug fix, we'll keep Pydantic models fully visible 
            # if they are small, or just signature if large. 
            # But let's stick to the core requirement: preserving decorators on functions.
            skeleton_lines.append(class_src)

        # Preserve Functions (The Critical Part)
        elif isinstance(node, ast.FunctionDef):
            # 1. Get the decorators
            decorators = []
            for decorator in node.decorator_list:
                dec_src = ast.get_source_segment(code, decorator)
                decorators.append(f"@{dec_src}")
            
            # 2. Get function signature (def name(args):)
            # Constructing this manually is safer to ensure we don't drop types
            args_src = ast.get_source_segment(code, node.args)
            signature = f"def {node.name}({args_src}):"
            if node.returns:
                ret_src = ast.get_source_segment(code, node.returns)
                signature = f"def {node.name}({args_src}) -> {ret_src}:"

            # 3. Combine
            if decorators:
                skeleton_lines.append("\n".join(decorators))
            skeleton_lines.append(f"{signature}\n    ...")
            
        # Preserve async functions too
        elif isinstance(node, ast.AsyncFunctionDef):
            decorators = []
            for decorator in node.decorator_list:
                dec_src = ast.get_source_segment(code, decorator)
                decorators.append(f"@{dec_src}")
            
            args_src = ast.get_source_segment(code, node.args)
            signature = f"async def {node.name}({args_src}):"
            
            if decorators:
                skeleton_lines.append("\n".join(decorators))
            skeleton_lines.append(f"{signature}\n    ...")

    return "\n\n".join(skeleton_lines)