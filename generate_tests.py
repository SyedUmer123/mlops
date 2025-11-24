import os
import re
import subprocess
import mlflow
import json
from openai import OpenAI
from diff import get_diff

# Import your helper script
# Ensure context.py is in the same folder!
try:
    from context import extract_skeleton
except ImportError:
    print("⚠️ Error: context.py not found. Make sure it is in the repository.")
    extract_skeleton = None

# ================= CONFIGURATION =================
API_KEY = os.getenv("API_KEY")
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI")

if not API_KEY:
    print("⚠️ Warning: API_KEY not found.")
else:
    client = OpenAI(api_key=API_KEY, base_url="https://api.groq.com/openai/v1")

MODEL_NAME = "llama-3.3-70b-versatile"

# ================= LOGIC =================

def read_code(file_path):
    if not os.path.exists(file_path): return None
    with open(file_path, "r") as f: return f.read()

def generate_test_code(app_code, diff=None):
    print("🤖 AI is generating tests...")
    
    # 1. Decide Strategy: Smart (Diff + Skeleton) vs Full (Legacy)
    if diff and extract_skeleton:
        print("🧠 Strategy: SMART CONTEXT (Skeleton + Diff)")
        skeleton = extract_skeleton(app_code)
        
        prompt = f"""
        You are a Senior QA Automation Engineer.
        
        I am providing you with:
        1. **THE CONTEXT**: The skeleton of the app (Imports, Models, Signatures).
        2. **THE CHANGE**: The specific logic that was just modified (Git Diff).
        
        === 1. APP SKELETON (Context) ===
        ```python
        {skeleton}
        ```
        
        === 2. GIT DIFF (The Change) ===
        ```diff
        {diff}
        ```
        
        TASK:
        Write a complete `pytest` file to verify the logic changed in the DIFF.
        You do not need to test unchanged parts of the app, but the test file must be runnable.
        
        CRITICAL INSTRUCTIONS:
        1. **Import Rule:** MUST use: `from app import app, todos`
        2. **State Isolation:** Use a fixture to clear `todos` before tests.
        3. **Logic:** Infer the full logic from the context and the diff.
        4. **Output:** Provide ONLY the executable python code.
        """
    else:
        print("⚠️ Strategy: FULL CONTEXT (Fallback)")
        # Fallback to sending the whole file if no diff exists or context.py is missing
        prompt = f"""
        You are a Senior QA Automation Engineer.
        Here is a FastAPI application code (filename: app.py):
        ```python
        {app_code}
        ```
        Write a complete Python test file using `pytest` and `fastapi.testclient`.
        
        CRITICAL INSTRUCTIONS:
        1. Import Rule: `from app import app, todos`
        2. Clear `todos` before every test.
        3. Capture dynamic IDs.
        4. Output ONLY python code.
        """

    # 2. Call LLM
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1 
    )
    
    content = response.choices[0].message.content
    clean_code = re.sub(r"```python|```", "", content).strip()
    return clean_code

def save_and_run_tests(test_code):
    with open("test_app_generated.py", "w") as f:
        f.write(test_code)
    
    print("🚀 Running Tests...")
    result = subprocess.run(["pytest", "test_app_generated.py"], capture_output=True, text=True)
    return result

# ================= EXECUTION =================
if __name__ == "__main__":
    if MLFLOW_TRACKING_URI:
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        mlflow.set_experiment("AI Test Generator")
    
    with mlflow.start_run():
        app_code = read_code("app.py")
        diff = get_diff()
        
        if app_code:
            mlflow.log_param("model_name", MODEL_NAME)
            mlflow.log_param("strategy", "smart_diff" if diff else "full_context")
            
            # Pass both Code and Diff to the generator
            test_code = generate_test_code(app_code, diff)
            result = save_and_run_tests(test_code)
            
            print(result.stdout)
            
            success = 1 if result.returncode == 0 else 0
            mlflow.log_metric("test_success_rate", success)
            
            mlflow.log_text(test_code, "generated_test_code.py")
            mlflow.log_text(result.stdout, "pytest_logs.txt")
            
            if success:
                print("✅ Success! Metrics logged to Dagshub.")
            else:
                print("❌ Failure! Metrics logged to Dagshub.")