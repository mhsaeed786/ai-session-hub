"""Audit every local repo: does its origin remote point at a repo that actually
belongs to it? Catches the cwd bug that made super-app's push land in ai-session-hub.
"""
import os
import subprocess

HOME = r"C:\Users\LOQ"
CANDIDATES = [
    "ai-session-hub", "super-app", "python-scripts-collection",
    "omnimedia-agency", "ai-session-extractor", "repo-audit/One-Agent",
    "Documents/Migrated data/_staging/FHIR-Mappings-builder",
    "Documents/Migrated data/_staging/FHIR-server-scope-security-testing",
    "Documents/Migrated data/_staging/Xellex-Campaign-Tools",
    "Documents/Migrated data/_staging/Python-Utilities-for-Testing",
    "Documents/Migrated data/_staging/Github-Data-Backup-Tools",
]


def run(args, cwd):
    try:
        r = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                           timeout=60)
        return (r.stdout + r.stderr).strip()
    except (subprocess.TimeoutExpired, OSError) as e:
        return f"ERR {e}"


print(f"{'REPO':46s} {'DIRNAME':16s} REMOTE MATCH")
print("-" * 88)
bad = []
for rel in CANDIDATES:
    p = os.path.join(HOME, rel.replace("/", os.sep))
    if not os.path.isdir(os.path.join(p, ".git")):
        continue
    url = run(["git", "remote", "get-url", "origin"], p)
    if not url or url.startswith("ERR"):
        print(f"{rel:46s} {'(none)':16s} NO REMOTE")
        continue
    dirname = os.path.basename(p).lower().replace("-", "").replace("_", "")
    repo = url.rstrip("/").split("/")[-1].replace(".git", "").lower()
    repo_n = repo.replace("-", "").replace("_", "")
    match = "OK" if (dirname in repo_n or repo_n in dirname) else "*** MISMATCH ***"
    if match != "OK":
        bad.append((rel, url))
    print(f"{rel:46s} {dirname:16s} {match}  -> {url}")

print()
if bad:
    print("MISMATCHED REPOS (remote does not match the local project):")
    for rel, url in bad:
        print(f"  {rel}  ->  {url}")
else:
    print("no mismatches found")
