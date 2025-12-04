import os
import re
import time
import yaml
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

# === MLFLOW SETUP ===
tracking_uri = os.getenv("MLFLOW_TRACKING_URI")
if tracking_uri:
    mlflow.set_tracking_uri(tracking_uri)
    print(f"Pointing to MLflow Server: {tracking_uri}")
else:
    print("Warning: MLFLOW_TRACKING_URI not set. Logs will be saved locally.")

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

def load_prompt_registry():
    """Load the YAML registry."""
    return yaml.safe_load(read_code("prompts/prompt_registry.yaml"))

def load_prompt_template(prompt_type, version):
    """Return path + template contents."""
    registry = load_prompt_registry()
    fname = registry[prompt_type]["versions"][version]
    path = f"prompts/{fname}"
    template = read_code(path)
    return template, path

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

# ================= COST CALCULATION =================
def calculate_cost(usage, model="groq-llama3"):
    """
    Calculate LLM cost based on token usage
    Groq pricing (example, update with actual rates):
    - Input: ~$0.27 per 1M tokens
    - Output: ~$0.27 per 1M tokens
    """
    if not usage:
        return 0.0
    
    input_cost_per_token = 0.27 / 1_000_000
    output_cost_per_token = 0.27 / 1_000_000
    
    total_cost = (
        usage.prompt_tokens * input_cost_per_token +
        usage.completion_tokens * output_cost_per_token
    )
    
    return total_cost

# ================= TEST GENERATION =================
def generate_test_code(app_code, diff):
    # 1. Determine prompt type
    if diff and extract_skeleton:
        prompt_type = "smart"
        skeleton = extract_skeleton(app_code)
    else:
        prompt_type = "full"
        skeleton = ""

    # 2. Load registry → get version
    registry = load_prompt_registry()
    prompt_version = registry[prompt_type]["current"]

    # 3. Load the template file
    template, template_path = load_prompt_template(prompt_type, prompt_version)

    # 4. Render prompt (inject values)
    prompt = template.format(
        skeleton=skeleton,
        diff=diff if diff else "",
        app_code=app_code
    )

    # 5. Call LLM
    content, duration, usage = call_llm(prompt)

    # 6. Clean result
    clean_code = re.sub(r"```python|```", "", content).strip()

    return clean_code, prompt, prompt_type, prompt_version, template_path, duration, usage


# ================= MAIN =================
if __name__ == "__main__":
    workflow_start = time.perf_counter()
    
    diff = get_diff()
    app_code = read_code("app.py")

    mlflow.set_experiment("AI Test Generator")

    with mlflow.start_run():
        # Generate tests
        (test_code,
         rendered_prompt,
         prompt_type,
         prompt_version,
         template_path,
         duration,
         usage) = generate_test_code(app_code, diff)

        # Calculate cost
        llm_cost = calculate_cost(usage)
        
        # Count generated tests
        tests_generated = len(re.findall(r"def test_", test_code))

        # ============================
        # MLFLOW PARAMS
        # ============================
        mlflow.log_param("model_name", MODEL_NAME)
        mlflow.log_param("prompt_type", prompt_type)
        mlflow.log_param("prompt_version", prompt_version)
        mlflow.log_param("prompt_template_path", template_path)
        mlflow.log_param("diff_present", bool(diff))
        mlflow.log_param("commit_sha", os.getenv("GITHUB_SHA", "local-run"))

        # ============================
        # MLFLOW METRICS
        # ============================
        mlflow.log_metric("llm_duration", duration)
        mlflow.log_metric("llm_cost_usd", llm_cost)
        mlflow.log_metric("tests_generated", tests_generated)
        
        if usage:
            mlflow.log_metric("llm_prompt_tokens", usage.prompt_tokens)
            mlflow.log_metric("llm_completion_tokens", usage.completion_tokens)
            mlflow.log_metric("llm_total_tokens", usage.total_tokens)

        # ============================
        # MLFLOW ARTIFACTS
        # ============================
        write_file("generated_test.py", test_code)
        mlflow.log_artifact("generated_test.py")

        write_file("prompt_used.txt", rendered_prompt)
        mlflow.log_artifact("prompt_used.txt")

        if diff:
            write_file("diff.patch", diff)
            mlflow.log_artifact("diff.patch")

        # ============================
        # EXPORT METRICS FOR PROMETHEUS
        # ============================
        metrics_summary = {
            "tests_generated": tests_generated,
            "llm_tokens_used": usage.total_tokens if usage else 0,
            "llm_cost_usd": llm_cost,
            "llm_latency_seconds": duration,
            "prompt_tokens": usage.prompt_tokens if usage else 0,
            "completion_tokens": usage.completion_tokens if usage else 0,
        }
        
        write_file("metrics_summary.json", 
                   __import__('json').dumps(metrics_summary, indent=2))

        print("✅ Generated tests saved to generated_test.py")
        print(f"📊 Generated {tests_generated} tests")
        print(f"💰 Cost: ${llm_cost:.4f}")
        print(f"⏱️  Duration: {duration:.2f}s")