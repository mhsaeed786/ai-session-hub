"""Check projects for embedded personal/company data before pushing."""
import subprocess
import os

BASE = r"C:\Users\LOQ\Documents\Migrated data\_staging"

projects = {
    "FHIR-Mappings-builder": os.path.join(BASE, "FHIR-Mappings-builder"),
    "FHIR-security-testing": os.path.join(BASE, "FHIR-server-scope-based-security-testing"),
    "Xellex": os.path.join(BASE, "Xellex-Campaign-Tools"),
    "PyUtils": os.path.join(BASE, "Python-Utilities-for-Testing"),
    "GithubBackup": os.path.join(BASE, "Github-Data-Backup-Tools"),
}

PATTERNS = ["curemd", "hassan", "saeed", "github_pat_", "ghp_"]

for name, root in projects.items():
    print(f"=== {name} ===")
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in (".git", "node_modules", "__pycache__")]
        for fn in filenames:
            if not fn.endswith((".py", ".js", ".ts", ".json", ".yml", ".yaml",
                                ".env.example", ".md", ".txt", ".cfg", ".toml")):
                continue
            fp = os.path.join(dirpath, fn)
            try:
                with open(fp, encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except OSError:
                continue
            for pat in PATTERNS:
                if pat.lower() in content.lower():
                    lines = [i+1 for i, line in enumerate(content.splitlines())
                             if pat.lower() in line.lower()]
                    print(f"  {pat}: {os.path.relpath(fp, root)} lines {lines[:5]}")
                    break
    # hardcoded secrets check (simple pattern)
    import re
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in (".git", "node_modules", "__pycache__")]
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            fp = os.path.join(dirpath, fn)
            try:
                with open(fp, encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except OSError:
                continue
            hits = re.findall(r"(?:password|token|secret|api_key)\s*=\s*[\"'][A-Za-z0-9\-_]{8,}[\"']",
                              content, re.IGNORECASE)
            for h in hits:
                print(f"  SECRET? {os.path.relpath(fp, root)}: {h[:50]}")
    print()
