import subprocess
import sys
import time
import mlflow
import re
import ast  
import os
from dotenv import load_dotenv

load_dotenv()

# === UPDATED MLFLOW SETUP ===
tracking_uri = os.getenv("MLFLOW_TRACKING_URI")
if tracking_uri:
    mlflow.set_tracking_uri(tracking_uri)
# ============================

test_file = "generated_test.py"

mlflow.set_experiment("AI Test Generator")

with mlflow.start_run(nested=True):

    t0 = time.perf_counter()

    # Run pytest
    result = subprocess.run(
        ["pytest", test_file, "-q", "--maxfail=1", "--tb=short"],
        capture_output=True,
        text=True
    )

    duration = time.perf_counter() - t0

    with open("test_stdout.txt", "w") as f:
        f.write(result.stdout)
    with open("test_stderr.txt", "w") as f:
        f.write(result.stderr)

    mlflow.log_artifact("test_stdout.txt")
    mlflow.log_artifact("test_stderr.txt")

    output = result.stdout
    passed_match = re.search(r"(\d+) passed", output)
    passed_count = int(passed_match.group(1)) if passed_match else 0
    
    failed_match = re.search(r"(\d+) failed", output)
    failed_count = int(failed_match.group(1)) if failed_match else 0

    mlflow.log_metric("test_duration", duration)
    mlflow.log_metric("tests_passed_count", passed_count)
    mlflow.log_metric("tests_failed_count", failed_count)
    mlflow.log_metric("suite_success", 1 if result.returncode == 0 else 0)

    if failed_count > 0:
        failed_names = re.findall(r"FAILED.*?::(\w+)", output)
        
        with open(test_file, "r") as f:
            source_code = f.read()
        
        tree = ast.parse(source_code)
        failed_tests_code = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name in failed_names:
                segment = ast.get_source_segment(source_code, node)
                if segment:
                    failed_tests_code.append(segment)
        
        failed_content = "\n\n".join(failed_tests_code)
        with open("failed_tests.py", "w") as f:
            f.write("# Failed Test Cases extracted from run\n")
            f.write("from app import app, todos\n\n") 
            f.write(failed_content)
        
        mlflow.log_artifact("failed_tests.py")
        print(f"Captured {len(failed_tests_code)} failed tests to failed_tests.py")


    print(result.stdout)
    print(result.stderr)

    if result.returncode == 0:
        print("Tests passed")
    else:
        print("Tests failed")

    sys.exit(result.returncode)