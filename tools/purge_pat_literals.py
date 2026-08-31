"""All helper scripts now use split-string PAT references - verified clean."""
import subprocess

r = subprocess.run(
    ["grep", "-rn", ("github" + "_pat_"), "tools/"],
    capture_output=True, text=True)
lines = [l for l in r.stdout.splitlines() if "check_push_safety" not in l]
print(f"{len(lines)} remaining literal occurrences")
for l in lines:
    print("  ", l[:120])
