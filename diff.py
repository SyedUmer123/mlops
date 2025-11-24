import subprocess
from pathlib import Path


def get_diff():
    changed_files = subprocess.check_output(
        "git diff --name-only HEAD~1 HEAD", shell=True, text=True
    ).splitlines()

    app_files = [f for f in changed_files if f.endswith(".py") and f.startswith("app")]

    diff_text = ""
    for f in app_files:
        diff_text += subprocess.check_output(
            f"git diff --unified=3 HEAD~1 HEAD -- {f}", shell=True, text=True
        )
    return diff_text.strip()


print("Diffs:\n", get_diff())