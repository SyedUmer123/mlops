import os
import re
import subprocess
import mlflow
import json
import time
import tempfile
from pathlib import Path
from openai import OpenAI

# local helpers
from diff import get_diff
try:
    from context import extract_skeleton
except ImportError:
    extract_skeleton = None

# optional dependency for system metrics
try:
    import psutil
except Exception:
    psutil = None

# ================= CONFIGURATION =================
API_KEY = os.getenv("API_KEY")
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI")

if not API_KEY:
    print("⚠️ Warning: API_KEY not found.")
else:
    client = OpenAI(api_key=API_KEY, base_url="https://api.groq.com/openai/v1")

MODEL_NAME = "llama-3.3-70b-versatile"
EXPERIMENT_NAME = "AI Test Generator"

# ================= UTILS =================

def read_code(file_path):
    if not os.path.exists(file_path):
        return None
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

def git_metadata():
    """Return basic git metadata: commit, branch, author, changed files list"""
    def run(cmd):
        return subprocess.check_output(cmd, shell=True, text=True).strip()
    try:
        commit = run("git rev-parse HEAD")
        branch = run("git rev-parse --abbrev-ref HEAD")
        author = run("git --no-pager show -s --format='%an <%ae>' HEAD")
        changed_files = run("git diff --name-only HEAD~1 HEAD").splitlines()
    except subprocess.CalledProcessError:
        commit = branch = author = None
        changed_files = []
    return {
        "commit": commit,
        "branch": branch,
        "author": author,
        "changed_files": changed_files,
    }

def call_llm(prompt):
    """Call LLM, measure duration, and return response + metadata."""
    t0 = time.perf_counter()
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1
    )
    t1 = time.perf_counter()
    # extract main text safely (defensive)
    content = ""
    try:
        content = response.choices[0].message.content
    except Exception:
        content = str(response)
    meta = {
        "duration_sec": t1 - t0,
        "raw_response": response,  # may be large; we'll save to file rather than param
    }
    return content, meta

def write_file(path, content):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def capture_system_metrics():
    if not psutil:
        return {}
    cpu_percent = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory()
    return {
        "cpu_percent": cpu_percent,
        "mem_total_gb": round(mem.total / (1024 ** 3), 3),
        "mem_used_gb": round(mem.used / (1024 ** 3), 3),
        "mem_percent": mem.percent,
    }

def run_pytest_and_capture(filename="test_app_generated.py"):
    """
    Run pytest and produce junit xml & capture stdout.
    Return subprocess.CompletedProcess and path to junit xml.
    """
    junit = "pytest_report.xml"
    cmd = ["pytest", filename, "--maxfail=1", f"--junitxml={junit}"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc, junit

def parse_junit(junit_path):
    """Parse junit xml and extract tests/failures/errors/time"""
    import xml.etree.ElementTree as ET
    if not os.path.exists(junit_path):
        return {}
    try:
        tree = ET.parse(junit_path)
        root = tree.getroot()
        # Top-level <testsuite> attributes
        attrs = root.attrib if root.tag == "testsuite" else {}
        if root.tag == "testsuites":
            # sum up if multiple suites
            total = failures = errors = skipped = 0
            time_total = 0.0
            for ts in root.findall("testsuite"):
                total += int(ts.attrib.get("tests", 0))
                failures += int(ts.attrib.get("failures", 0))
                errors += int(ts.attrib.get("errors", 0))
                skipped += int(ts.attrib.get("skipped", 0))
                time_total += float(ts.attrib.get("time", 0.0))
            return {
                "tests": total,
                "failures": failures,
                "errors": errors,
                "skipped": skipped,
                "time_sec": time_total,
            }
        else:
            return {
                "tests": int(attrs.get("tests", 0)),
                "failures": int(attrs.get("failures", 0)),
                "errors": int(attrs.get("errors", 0)),
                "skipped": int(attrs.get("skipped", 0)),
                "time_sec": float(attrs.get("time", 0.0)),
            }
    except Exception:
        return {}

# ================= GENERATION LOGIC (keeps your existing prompts) =================

def generate_test_code(app_code, diff=None):
    print("🤖 AI is generating tests...")

    if diff and extract_skeleton:
        print("🧠 Strategy: SMART CONTEXT (Skeleton + Diff)")
        skeleton = extract_skeleton(app_code)

        prompt = f"""
You are a Senior QA Automation Engineer.

I am providing you with:
1. THE CONTEXT: The skeleton of the app (Imports, Models, Signatures).
2. THE CHANGE: The specific logic that was just modified (Git Diff).

=== 1. APP SKELETON (Context) ===
```python
{skeleton}
=== 2. GIT DIFF (The Change) ===
{diff}
TASK:
Write a complete pytest file to verify the logic changed in the DIFF.
You do not need to test unchanged parts of the app, but the test file must be runnable.

CRITICAL INSTRUCTIONS:
Import Rule: MUST use: from app import app, todos
State Isolation: Use a fixture to clear todos before tests.
Logic: Infer the full logic from the context and the diff.
Output: Provide ONLY the executable python code.
"""
    else:
        print("⚠️ Strategy: FULL CONTEXT (Fallback)")
        prompt = f"""
        You are a Senior QA Automation Engineer.
        Here is a FastAPI application code (filename: app.py):
        {app_code}
Write a complete Python test file using pytest and fastapi.testclient.

CRITICAL INSTRUCTIONS:

Import Rule: from app import app, todos

Clear todos before every test.

Capture dynamic IDs.

Output ONLY python code.
"""
    
    content, meta = call_llm(prompt)

    clean_code = re.sub(r"python|", "", content).strip()
    
    return clean_code, prompt, meta


# ================= EXECUTION ENTRYPOINT =================
if __name__ == "__main__":
    if MLFLOW_TRACKING_URI:
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        mlflow.set_experiment(EXPERIMENT_NAME)

    git_meta = git_metadata()
    app_code = read_code("app.py")
    diff = get_diff()

# Top-level run
    with mlflow.start_run(run_name="generate_and_run_tests") as run:
        run_id = run.info.run_id
        # Log git & environment metadata
        mlflow.set_tag("script", "generate_tests.py")
        mlflow.log_param("model_name", MODEL_NAME)
        mlflow.log_param("strategy", "smart_diff" if diff else "full_context")
        mlflow.log_param("git_commit", git_meta.get("commit"))
        mlflow.log_param("git_branch", git_meta.get("branch"))
        mlflow.log_param("git_author", git_meta.get("author"))

        # Save and log the diff (artifact) for reproducibility
        if diff:
            write_file("artifacts/diff.patch", diff)
            mlflow.log_artifact("artifacts/diff.patch")

        # System snapshot
        sys_metrics = capture_system_metrics()
        for k, v in sys_metrics.items():
            mlflow.log_metric(k, v)

    # ---------- GENERATION (nested run) ----------
    with mlflow.start_run(run_name="test_generation", nested=True):
        start_gen = time.perf_counter()
        test_code, prompt_sent, llm_meta = generate_test_code(app_code, diff)
        gen_time = time.perf_counter() - start_gen

        # write prompt & result to files and log as artifacts
        write_file("artifacts/prompt.txt", prompt_sent)
        write_file("artifacts/generated_test_code.py", test_code)
        mlflow.log_artifact("artifacts/prompt.txt")
        mlflow.log_artifact("artifacts/generated_test_code.py")

        # log generation metrics
        mlflow.log_param("llm_model", MODEL_NAME)
        mlflow.log_metric("generation_time_sec", gen_time)
        # If llm_meta contains useful fields, save them to file
        try:
            # save raw response JSON to help debugging complex failures
            raw_path = "artifacts/llm_raw_response.json"
            write_file(raw_path, json.dumps(str(llm_meta.get("raw_response")), indent=2))
            mlflow.log_artifact(raw_path)
        except Exception:
            pass

    # ---------- EXECUTION (nested run) ----------
    with mlflow.start_run(run_name="test_execution", nested=True):
        # save test file (again under run scope)
        write_file("test_app_generated.py", test_code)

        # run pytest and capture junit xml & stdout
        proc, junit_path = run_pytest_and_capture("test_app_generated.py")

        # save pytest stdout/stderr and junit
        write_file("artifacts/pytest_stdout.txt", proc.stdout or "")
        write_file("artifacts/pytest_stderr.txt", proc.stderr or "")
        mlflow.log_artifact("artifacts/pytest_stdout.txt")
        mlflow.log_artifact("artifacts/pytest_stderr.txt")

        if os.path.exists(junit_path):
            mlflow.log_artifact(junit_path)

        # parse junit for numeric metrics and log them
        junit_metrics = parse_junit(junit_path)
        if junit_metrics:
            for k, v in junit_metrics.items():
                mlflow.log_metric(k, v)

        # basic pass/fail metric
        success = 1 if proc.returncode == 0 else 0
        mlflow.log_metric("test_success", success)
        mlflow.log_param("pytest_returncode", proc.returncode)

        # store a JSON summary artifact for quick programmatic consumption
        summary = {
            "run_id": run_id,
            "git": git_meta,
            "generation_time_sec": gen_time,
            "pytest_returncode": proc.returncode,
            "junit_metrics": junit_metrics,
        }
        write_file("artifacts/summary.json", json.dumps(summary, indent=2))
        mlflow.log_artifact("artifacts/summary.json")

    # top-level housekeeping: tag run as failed if tests failed
    if success:
        mlflow.set_tag("pipeline.status", "success")
        print("✅ Tests passed.")
    else:
        mlflow.set_tag("pipeline.status", "failed")
        print("❌ Tests failed. Artifacts & logs saved to MLflow.")
