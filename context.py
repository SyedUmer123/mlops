import ast

def extract_skeleton(code: str) -> str:
    """
    Parses code and returns a skeleton. 
    CRITICAL UPDATE: Now preserves Pydantic fields (Annotated Assignments).
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return "Error parsing code structure."

    skeleton_lines = []

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Handle Functions (Keep signatures)
            args = [arg.arg for arg in node.args.args]
            args_str = ", ".join(args)
            def_type = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
            skeleton_lines.append(f"{def_type} {node.name}({args_str}):")
            
            if ast.get_docstring(node):
                skeleton_lines.append(f'    """{ast.get_docstring(node)}"""')
            skeleton_lines.append("    ...\n")

        elif isinstance(node, ast.ClassDef):
            # Handle Classes (Keep Fields/Attributes)
            skeleton_lines.append(f"class {node.name}:")
            if ast.get_docstring(node):
                skeleton_lines.append(f'    """{ast.get_docstring(node)}"""')
            
            # --- NEW LOGIC START ---
            # Extract fields like 'title: str' or 'done: bool = False'
            has_fields = False
            for subnode in node.body:
                if isinstance(subnode, ast.AnnAssign):
                    try:
                        target = ast.unparse(subnode.target)
                        annotation = ast.unparse(subnode.annotation)
                        line = f"    {target}: {annotation}"
                        # Check for default values (e.g., = False)
                        if subnode.value:
                            line += " = ..." # Hide actual value to save tokens, or keep it
                        skeleton_lines.append(line)
                        has_fields = True
                    except Exception:
                        pass
            
            if not has_fields:
                skeleton_lines.append("    # (Methods/Fields hidden)")
            else:
                 skeleton_lines.append("    # Methods hidden...")
            # --- NEW LOGIC END ---
            skeleton_lines.append("")

        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            skeleton_lines.append(ast.unparse(node))

    return "\n".join(skeleton_lines)