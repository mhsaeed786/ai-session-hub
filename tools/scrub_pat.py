"""Scrub embedded PAT from migration scripts so GitHub push protection passes."""
import re

for fp in [r"tools\push_staging_repos.py", r"tools\push_novel_repos.py"]:
    with open(fp, encoding="utf-8") as f:
        c = f.read()
    before = c.count("github" + "_pat_")
    c = re.sub(r'TOKEN = "github_pat_[A-Za-z0-9]*"',
               'TOKEN = os.environ.get("GH_TOKEN", "")', c)
    c = re.sub(r'x-access-token:github_pat_[A-Za-z0-9]*@github\.com',
               'x-access-token:$GH_TOKEN@github.com', c)
    with open(fp, "w", encoding="utf-8", newline="") as f:
        f.write(c)
    after = c.count("github" + "_pat_")
    print(f"{fp}: {before} -> {after} occurrences")
