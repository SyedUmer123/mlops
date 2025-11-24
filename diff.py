import subprocess
from pathlib import Path

# get changed files
changed_files = subprocess.check_output(
    "git diff --name-only HEAD~1 HEAD", shell=True, text=True
).splitlines()

# filter only app-related files
app_files = [f for f in changed_files if f.endswith(".py") and f.startswith("app")]
print("App files changed:", app_files)

# get diff only for these files
diff_text = ""
for f in app_files:
    diff_text += subprocess.check_output(
        f"git diff --unified=3 HEAD~1 HEAD -- {f}", shell=True, text=True
    )
