import os
import re
import subprocess
from openai import OpenAI
from dotenv import load_dotenv
# Load environment variables from .env file
load_dotenv()
API_KEY = os.getenv("API_KEY")

if not API_KEY:
    raise ValueError("❌ API Key is missing! Please set GROQ_API_KEY in your environment.")

# Setup the Client (Defaulting to Groq for speed/free tier, change if using OpenAI)
client = OpenAI(
    api_key=API_KEY,
    base_url="https://api.groq.com/openai/v1", # Remove this line if using OpenAI
)
MODEL_NAME = "llama-3.3-70b-versatile" # Use "gpt-4o" if using OpenAI

# ================= THE LOGIC =================

def read_code(file_path):
    """Reads the content of your application file."""
    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found.")
        return None
    with open(file_path, "r") as f:
        return f.read()

def generate_test_code(app_code):
    """Sends code to LLM and gets a Test file back."""
    print("🤖 AI is analyzing your code...")
    
    prompt = f"""
    You are a Senior QA Automation Engineer.
    Here is a FastAPI application code:
    
    ```python
    {app_code}
    ```
    
    Write a complete Python test file using `pytest` and `fastapi.testclient`.
    
    CRITICAL INSTRUCTIONS:
    1. **State Isolation:** The `todos` dictionary in `app.py` is global. Create a `pytest.fixture(autouse=True)` that clears it (`todos.clear()`) before every test.
    2. **NO HARDCODED IDs:** The `next_id` counter in the app does NOT reset. 
       - When testing updates or deletions, you MUST create a new todo first.
       - **Capture the ID** from the creation response (e.g., `todo_id = response.json()["id"]`).
       - Use that captured variable `todo_id` for your DELETE/GET requests.
       - NEVER assume the ID is 1.
    3. **Edge Cases:** Handle creating a todo with an empty title (expect 200 OK).
    4. **Output:** Provide ONLY the executable python code. No markdown.
    """

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0
    )
    
    content = response.choices[0].message.content
    clean_code = re.sub(r"```python|```", "", content).strip()
    return clean_code

def save_and_run_tests(test_code):
    """Saves the test code and runs pytest."""
    
    # Save the file
    with open("test_app_generated.py", "w") as f:
        f.write(test_code)
    print("✅ Test file generated: test_app_generated.py")
    
    # Run Pytest
    print("🚀 Running Tests...")
    result = subprocess.run(["pytest", "test_app_generated.py"], capture_output=True, text=True)
    
    print(result.stdout)
    if result.returncode == 0:
        print("🎉 SUCCESS: All AI-generated tests passed!")
    else:
        print("❌ FAILURE: Some tests failed.")
        print(result.stderr)

# ================= EXECUTION =================
if __name__ == "__main__":
    # 1. Read your App
    app_code = read_code("app.py")
    
    if app_code:
        # 2. Generate Test
        test_code = generate_test_code(app_code)
        
        # 3. Save and Run
        save_and_run_tests(test_code)