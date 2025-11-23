import os
import re
import subprocess
import mlflow
from openai import OpenAI

# ================= CONFIGURATION =================
API_KEY = os.getenv("API_KEY")
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI")

# Setup Client
if not API_KEY:
    # Fallback for local testing if env var not set
    print("⚠️ Warning: GROQ_API_KEY not found in environment.")
else:
    client = OpenAI(api_key=API_KEY, base_url="https://api.groq.com/openai/v1")

MODEL_NAME = "llama-3.3-70b-versatile"

# ================= LOGIC =================

def read_code(file_path):
    if not os.path.exists(file_path): return None
    with open(file_path, "r") as f: return f.read()

def generate_test_code(app_code):
    print("🤖 AI is generating tests...")
    prompt = f"""
    You are a Senior QA Automation Engineer.
    Here is a FastAPI application code:
    ```python
    {app_code}
    ```
    Write a complete Python test file using `pytest` and `fastapi.testclient`.
    
    CRITICAL INSTRUCTIONS:
    1. **State Isolation:** Create a `pytest.fixture(autouse=True)` that clears `todos` dictionary before every test.
    2. **Dynamic IDs:** Capture IDs from responses. Do NOT assume ID is 1.
    3. **Output:** Provide ONLY the executable python code.
    """

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1 
    )
    
    content = response.choices[0].message.content
    clean_code = re.sub(r"```python|```", "", content).strip()
    return clean_code

def save_and_run_tests(test_code):
    # Save file
    with open("test_app_generated.py", "w") as f:
        f.write(test_code)
    
    # Run Pytest
    print("🚀 Running Tests...")
    result = subprocess.run(["pytest", "test_app_generated.py"], capture_output=True, text=True)
    return result

# ================= EXECUTION =================
if __name__ == "__main__":
    # 1. Setup MLflow
    if MLFLOW_TRACKING_URI:
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        mlflow.set_experiment("AI Test Generator")
    
    # 2. Start Tracking Run
    with mlflow.start_run():
        app_code = read_code("app.py")
        
        if app_code:
            # Log Model Params
            mlflow.log_param("model_name", MODEL_NAME)
            mlflow.log_param("app_code_length", len(app_code))

            # Generate and Run
            test_code = generate_test_code(app_code)
            result = save_and_run_tests(test_code)
            
            print(result.stdout)
            
            # Log Metrics (1 = Pass, 0 = Fail)
            success = 1 if result.returncode == 0 else 0
            mlflow.log_metric("test_success_rate", success)
            
            # Log Artifacts (The actual code)
            mlflow.log_text(test_code, "generated_test_code.py")
            mlflow.log_text(result.stdout, "pytest_logs.txt")
            
            if success:
                print("✅ Success! Metrics logged to Dagshub.")
            else:
                print("❌ Failure! Metrics logged to Dagshub.")