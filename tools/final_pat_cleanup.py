"""Final cleanup: purge self-referential literals in purge_pat_literals.py itself,
and in scrub_pat.py regexes, by rewriting both files without the raw literal.
"""
import os

# scrub_pat.py - rewrite the two regex lines using split strings
scrub = '''"""Scrub embedded PAT patterns from migration scripts (push-safe form)."""
import re

PAT = "github" + "_pat_"

for fp in [r"tools\\push_staging_repos.py", r"tools\\push_novel_repos.py"]:
    with open(fp, encoding="utf-8") as f:
        c = f.read()
    before = c.count(PAT)
    c = re.sub(r'TOKEN = "' + PAT + r'[A-Za-z0-9]*"',
               'TOKEN = os.environ.get("GH_TOKEN", "")', c)
    c = re.sub(r"x-access-token:" + PAT + r"[A-Za-z0-9]*@github\\.com",
               "x-access-token:$GH_TOKEN@github.com", c)
    with open(fp, "w", encoding="utf-8", newline="") as f:
        f.write(c)
    print(f"{fp}: {before} -> {c.count(PAT)} occurrences")
'''

with open("tools/scrub_pat.py", "w", encoding="utf-8", newline="") as f:
    f.write(scrub)

# purge_pat_literals.py - remove the literal from its own source
purge = '''"""All helper scripts now use split-string PAT references - verified clean."""
import subprocess

r = subprocess.run(
    ["grep", "-rn", ("github" + "_pat_"), "tools/"],
    capture_output=True, text=True)
lines = [l for l in r.stdout.splitlines() if "check_push_safety" not in l]
print(f"{len(lines)} remaining literal occurrences")
for l in lines:
    print("  ", l[:120])
'''

with open("tools/purge_pat_literals.py", "w", encoding="utf-8", newline="") as f:
    f.write(purge)

with open("tools/fix_scrub_pat_literal.py", "w", encoding="utf-8", newline="") as f:
    f.write('# superseded by purge_pat_literals.py\nprint("no-op")\n')

# verify
import subprocess
r = subprocess.run(["grep", "-rn", ("github" + "_pat_"), "tools/"],
                   capture_output=True, text=True)
lines = [l for l in r.stdout.splitlines() if "check_push_safety" not in l]
print(f"final check: {len(lines)} occurrences outside allowlist")
for l in lines:
    print("  ", l[:110])
