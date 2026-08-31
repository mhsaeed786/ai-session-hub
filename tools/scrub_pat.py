"""Scrub embedded PAT patterns from migration scripts (push-safe form)."""
import re

PAT = "github" + "_pat_"

for fp in [r"tools\push_staging_repos.py", r"tools\push_novel_repos.py"]:
    with open(fp, encoding="utf-8") as f:
        c = f.read()
    before = c.count(PAT)
    c = re.sub(r'TOKEN = "' + PAT + r'[A-Za-z0-9]*"',
               'TOKEN = os.environ.get("GH_TOKEN", "")', c)
    c = re.sub(r"x-access-token:" + PAT + r"[A-Za-z0-9]*@github\.com",
               "x-access-token:$GH_TOKEN@github.com", c)
    with open(fp, "w", encoding="utf-8", newline="") as f:
        f.write(c)
    print(f"{fp}: {before} -> {c.count(PAT)} occurrences")
