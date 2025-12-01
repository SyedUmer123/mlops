import subprocess
import sys

test_file = "generated_test.py"

result = subprocess.run(
    ["pytest", test_file, "-q", "--maxfail=1", "--tb=short"],
    capture_output=True,
    text=True
)

print(result.stdout)
print(result.stderr)

if result.returncode == 0:
    print("Tests passed")
else:
    print("Tests failed")

sys.exit(result.returncode)
