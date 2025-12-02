import os
import re
import time
import mlflow
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

from diff import get_diff
try:
    from context import extract_skeleton
except ImportError:
    extract_skeleton = None

load_dotenv()

API_KEY = os.getenv("API_KEY")
MODEL_NAME = "llama-3.3-70b-versatile"

# === UPDATED MLFLOW SETUP ===
# We now rely on standard env vars: MLFLOW_TRACKING_URI and AWS credentials
tracking_uri = os.getenv("MLFLOW_TRACKING_URI")
if tracking_uri:
    mlflow.set_tracking_uri(tracking_uri)
    print(f"Pointing to MLflow Server: {tracking_uri}")
else:
    print("Warning: MLFLOW_TRACKING_URI not set. Logs will be saved locally.")
# ============================

if not API_KEY:
    raise ValueError("API_KEY not set")

client = OpenAI(api_key=API_KEY, base_url="https://api.groq.com/openai/v1")

# ================= UTILS =================
def read_code(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

def write_file(path, content):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

# ================= LLM CALL =================
def call_llm(prompt):
    t0 = time.perf_counter()

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1
    )

    duration = time.perf_counter() - t0

    content = response.choices[0].message.content
    usage = response.usage

    return content, duration, usage

# ================= TEST GENERATION =================
def generate_test_code(app_code, diff=None):
    if diff and extract_skeleton:
        skeleton = extract_skeleton(app_code)
        prompt = f"""
You are a Senior QA Automation Engineer.

=== SKELETON ===
{skeleton}

=== DIFF ===
{diff}

Write runnable pytest tests.
Import: from app import app, todos
Output only python code.
"""
    else:
        prompt = f"""
You are a Senior QA Automation Engineer.
Here is the full FastAPI app code:

{app_code}

Write complete pytest tests.
Import: from app import app, todos
Output ONLY python code.
"""

    content, duration, usage = call_llm(prompt)

    clean_code = re.sub(r"```python|```", "", content).strip()

    return clean_code, prompt, duration, usage

# ================= MAIN =================
if __name__ == "__main__":
    diff = get_diff()
    app_code = read_code("app.py")

    mlflow.set_experiment("AI Test Generator")

    with mlflow.start_run():

        # PARAMETERS
        mlflow.log_param("model_name", MODEL_NAME)
        mlflow.log_param("diff_present", bool(diff))
        mlflow.log_param("commit_sha", os.getenv("GITHUB_SHA", "local-run"))

        # Generate tests
        test_code, prompt, duration, usage = generate_test_code(app_code, diff)

        # METRICS
        mlflow.log_metric("llm_duration", duration)
        if usage:
            mlflow.log_metric("llm_prompt_tokens", usage.prompt_tokens)
            mlflow.log_metric("llm_completion_tokens", usage.completion_tokens)
            mlflow.log_metric("llm_total_tokens", usage.total_tokens)

        # Save artifacts
        write_file("generated_test.py", test_code)
        mlflow.log_artifact("generated_test.py")

        write_file("prompt.txt", prompt)
        mlflow.log_artifact("prompt.txt")

        if diff:
            write_file("diff.patch", diff)
            mlflow.log_artifact("diff.patch")

        print("Generated tests saved to generated_test.py")