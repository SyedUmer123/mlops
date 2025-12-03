import os
import re
import time
import ast
import mlflow
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

# === LOCAL MODULES ===
from diff import get_diff

# Try to import Context skeleton
try:
    from context import extract_skeleton
except ImportError:
    extract_skeleton = None

# Try to import Smart Update tools
try:
    from smart_update import (
        get_changed_functions, 
        update_test_file, 
        get_existing_test_code
    )
except ImportError:
    print("CRITICAL WARNING: 'smart_update.py' not found. Incremental updates will fail.")
    get_changed_functions = None
    update_test_file = None
    get_existing_test_code = None

load_dotenv()

# === CONFIGURATION ===
API_KEY = os.getenv("API_KEY")
MODEL_NAME = "llama-3.3-70b-versatile" # Or your preferred model
TEST_FILE_PATH = "generated_test.py"

# === MLFLOW SETUP ===
tracking_uri = os.getenv("MLFLOW_TRACKING_URI")
if tracking_uri:
    mlflow.set_tracking_uri(tracking_uri)
else:
    print("Warning: MLFLOW_TRACKING_URI not set. Logs will be saved locally.")

if not API_KEY:
    raise ValueError("API_KEY not set")

client = OpenAI(api_key=API_KEY, base_url="https://api.groq.com/openai/v1")

# ================= UTILS =================
def read_code(file_path):
    if not os.path.exists(file_path):
        return ""
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

def write_file(path, content):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def get_function_source(code, func_name):
    """
    Extracts the source code of a specific function from app.py using AST.
    Used to send ONLY the relevant code to the LLM.
    """
    try:
        tree = ast.parse(code)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == func_name:
                    return ast.unparse(node)
    except Exception as e:
        print(f"Error extracting source for {func_name}: {e}")
    return ""

# ================= LLM CALL =================
def call_llm(prompt):
    t0 = time.perf_counter()
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2, # Slightly higher temp for creative edge cases
        )
        duration = time.perf_counter() - t0
        content = response.choices[0].message.content
        usage = response.usage
        return content, duration, usage
    except Exception as e:
        print(f"LLM Call Failed: {e}")
        return "", 0, None

# ================= TEST GENERATION LOGIC =================

def generate_single_test_incremental(func_name, func_source, skeleton, test_file_path):
    """
    Generates a ROBUST, PARAMETERIZED test for a single function.
    Reads existing test to preserve legacy edge cases.
    """
    
    # 1. Retrieve Existing Test (Context Merge Strategy)
    existing_test_code = get_existing_test_code(test_file_path, func_name)
    
    context_instruction = ""
    if existing_test_code:
        context_instruction = f"""
=== EXISTING TEST CODE (PRESERVE THESE SCENARIOS) ===
{existing_test_code}

INSTRUCTION: 
The function logic has changed. You must UPDATE the test to match the new logic, 
BUT you must MERGE any valid edge cases from the 'EXISTING TEST CODE' above into your new parameter list.
"""

    # 2. Construct Prompt
    prompt = f"""
You are a Senior QA Automation Engineer.
The function `{func_name}` has been modified. We need a robust, parameterized test suite.

=== APP STRUCTURE (Context) ===
{skeleton}

=== NEW FUNCTION CODE (Target) ===
{func_source}
{context_instruction}

=== REQUIREMENTS ===
1. Use `@pytest.mark.parametrize` to cover at least 5 distinct scenarios:
   - Happy path (standard valid inputs)
   - Edge cases (empty strings, None, zeros, negative numbers, max values)
   - Error cases (inputs that should raise exceptions, if applicable)
2. The output must be a SINGLE function named `test_{func_name}`.
3. Assume `app` and `todos` (or relevant modules) are imported.
4. Output ONLY valid Python code. No markdown formatting.
"""

    content, duration, usage = call_llm(prompt)
    
    # Cleanup Markdown
    clean_code = re.sub(r"```python|```", "", content).strip()
    return clean_code, prompt, duration, usage

def generate_full_suite_fallback(app_code):
    """
    Fallback: Generates the entire test file from scratch (Standard Mode).
    """
    prompt = f"""
You are a Senior QA Automation Engineer.
Here is the full FastAPI app code:

{app_code}

Write complete pytest tests.
Requirements:
1. Use `@pytest.mark.parametrize` for all test functions to maximize coverage.
2. Import: from app import app, todos
3. Output ONLY python code.
"""
    content, duration, usage = call_llm(prompt)
    clean_code = re.sub(r"```python|```", "", content).strip()
    return clean_code, prompt, duration, usage

# ================= MAIN EXECUTION =================
if __name__ == "__main__":
    # 1. Setup Environment
    diff = get_diff()
    app_code = read_code("app.py")
    
    # Determine if we can run in "Smart Incremental Mode"
    # We need: A diff, the smart_update module, and an existing test file to patch
    can_update_incrementally = (
        diff and 
        get_changed_functions is not None and 
        os.path.exists(TEST_FILE_PATH)
    )

    mlflow.set_experiment("AI Test Generator")

    with mlflow.start_run():
        mlflow.log_param("model_name", MODEL_NAME)
        mlflow.log_param("commit_sha", os.getenv("GITHUB_SHA", "local-run"))
        mlflow.log_param("mode", "incremental" if can_update_incrementally else "full_suite")

        total_duration = 0
        total_tokens = 0

        # === PATH A: INCREMENTAL UPDATE ===
        if can_update_incrementally:
            print("--- 🚀 Running Smart Incremental Update ---")
            
            # Identify which functions actually changed
            changed_funcs = get_changed_functions(app_code, diff)
            mlflow.log_param("changed_functions", str(changed_funcs))
            
            if not changed_funcs:
                print("Diff detected, but no specific function logic matched. Skipping.")
            
            else:
                skeleton = extract_skeleton(app_code) if extract_skeleton else ""
                
                for func_name in changed_funcs:
                    print(f"-> Processing: {func_name}")
                    
                    # Get the raw code for just this function
                    func_source = get_function_source(app_code, func_name)
                    
                    if not func_source:
                        print(f"   Skipping {func_name} (Source not found in AST).")
                        continue

                    # Generate Test (Reading old test -> Merging -> Writing new)
                    test_code, prompt, duration, usage = generate_single_test_incremental(
                        func_name, func_source, skeleton, TEST_FILE_PATH
                    )
                    
                    if not test_code:
                        print(f"   Failed to generate code for {func_name}")
                        continue

                    # Surgically update the file
                    update_test_file(TEST_FILE_PATH, test_code, func_name)
                    print(f"   Updated test_{func_name} in {TEST_FILE_PATH}")
                    
                    # Accumulate Metrics
                    total_duration += duration
                    if usage:
                        total_tokens += usage.total_tokens
                        
                    # Log specific prompt for debugging
                    mlflow.log_text(prompt, f"prompts/{func_name}_prompt.txt")

        # === PATH B: FULL REGENERATION (Fallback) ===
        else:
            print("--- Running Full Suite Regeneration (Fresh Start) ---")
            if not diff:
                print("(Reason: No Diff detected)")
            elif not os.path.exists(TEST_FILE_PATH):
                print("(Reason: No existing test file to patch)")
            
            test_code, prompt, duration, usage = generate_full_suite_fallback(app_code)
            
            write_file(TEST_FILE_PATH, test_code)
            print(f"Created new test suite in {TEST_FILE_PATH}")
            
            total_duration = duration
            if usage:
                total_tokens = usage.total_tokens
            
            mlflow.log_text(prompt, "prompts/full_suite_prompt.txt")

        # Final Logs
        mlflow.log_metric("total_duration", total_duration)
        mlflow.log_metric("total_tokens", total_tokens)
        mlflow.log_artifact(TEST_FILE_PATH)
        
        if diff:
            mlflow.log_text(diff, "diff.patch")

        print(f"Done. Process finished in {total_duration:.2f}s")