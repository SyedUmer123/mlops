import os
import re
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

from diff import get_diff
try:
    from context import extract_skeleton
except ImportError:
    extract_skeleton = None

load_dotenv()

API_KEY = os.getenv("API_KEY")
MODEL_NAME = "llama-3.3-70b-versatile"

if not API_KEY:
    raise ValueError("API_KEY not set")

client = OpenAI(api_key=API_KEY, base_url="https://api.groq.com/openai/v1")

# ================== UTILS ==================
def read_code(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

def call_llm(prompt):
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1
    )
    return response.choices[0].message.content

def write_file(path, content):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

# ================== GENERATION ==================
def generate_test_code(app_code, diff=None):
    print("AI is generating tests...")
    if diff and extract_skeleton:
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

    content = call_llm(prompt)
    clean_code = re.sub(r"```python|```", "", content).strip()
    return clean_code

# ================== MAIN ==================
if __name__ == "__main__":
    app_code = read_code("app.py")
    diff = get_diff()
    test_code = generate_test_code(app_code, diff)
    write_file("generated_test.py", test_code)
    print("Generated tests saved to tests/generated_test.py")
