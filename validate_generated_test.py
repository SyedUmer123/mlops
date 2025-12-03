import ast
import mlflow
import re

TEST_FILE = "generated_test.py"

# Forbidden imports and dangerous patterns
FORBIDDEN_IMPORTS = {
    "os", "subprocess", "shutil", "socket", "sys", "requests", "pathlib",
}

FORBIDDEN_PATTERNS = [
    r"os\.system",
    r"subprocess\.",
    r"shutil\.",
    r"eval\(",
    r"exec\(",
    r"open\(.+\/etc\/passwd",
    r"while\s+True",
]


def validate_syntax(code: str):
    """Check if the test file contains valid Python syntax."""
    try:
        ast.parse(code)
        return True, None
    except SyntaxError as e:
        return False, f"Syntax error: {str(e)}"


def validate_imports(code: str):
    """Ensure only safe imports are used."""
    tree = ast.parse(code)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in FORBIDDEN_IMPORTS:
                    return False, f"Forbidden import: {alias.name}"

        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in FORBIDDEN_IMPORTS:
                return False, f"Forbidden import: {node.module}"

    return True, None


def validate_patterns(code: str):
    """Check for dangerous patterns."""
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, code):
            return False, f"Forbidden pattern used: {pattern}"
    return True, None


def validate_test_format(code: str):
    """Ensure test has at least one valid test function."""
    if "def test_" not in code:
        return False, "No test functions found (missing `def test_...`)."
    return True, None


if __name__ == "__main__":
    mlflow.set_experiment("AI Test Generator")

    with mlflow.start_run(nested=True):

        # Load test code
        with open(TEST_FILE, "r") as f:
            code = f.read()

        # Run validators
        checks = [
            validate_syntax,
            validate_imports,
            validate_patterns,
            validate_test_format,
        ]

        for check in checks:
            ok, error = check(code)
            if not ok:
                print(f"Validation Failed: {error}")
                mlflow.log_metric("validation_passed", 0)
                mlflow.log_param("validation_error", error)

                # Save invalid test file
                with open("invalid_test.py", "w") as bad:
                    bad.write(code)
                mlflow.log_artifact("invalid_test.py")

                exit(1)

        print("Validation Passed")
        mlflow.log_metric("validation_passed", 1)
        exit(0)
