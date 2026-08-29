"""Push the 5 sanitized staging projects as fresh GitHub repos.

Strategy: fresh init + single clean commit (no old history -> no leaks).
"""
import os
import subprocess
import sys

STAGING = r"C:\Users\LOQ\Documents\Migrated data\_staging"
GH = r"C:\Program Files\GitHub CLI\gh.exe"
TOKEN = os.environ.get("GH_TOKEN", "")

REPOS = [
    ("FHIR-Mappings-builder",
     "FHIR Search Parameter mapping builder - scripts to build, audit and "
     "finalize FHIR-to-DB mapping masters from Excel sources"),
    ("FHIR-server-scope-based-security-testing",
     "SMART on FHIR / OAuth security testing toolkit - scope enforcement, "
     "client auth flows, Keycloak realm migration utilities"),
    ("Xellex-Campaign-Tools",
     "Outreach campaign automation - lead list building, mail merge, "
     "SearxNG/DDG search pipelines"),
    ("Python-Utilities-for-Testing",
     "Standalone testing utilities - OAuth flow testers, SMTP test server, "
     "CSV/test-plan generators"),
    ("Github-Data-Backup-Tools",
     "GitHub repository backup tools - one-shot and scheduled repo mirroring"),
]

env = dict(os.environ, GH_TOKEN=TOKEN)


def run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                          shell=True, env=env)


def main():
    for name, desc in REPOS:
        path = os.path.join(STAGING, name)
        print(f"\n=== {name} ===")
        if not os.path.isdir(path):
            print("  missing, skipped")
            continue

        # fresh git state (drop old history entirely)
        gitdir = os.path.join(path, ".git")
        if os.path.isdir(gitdir):
            import shutil
            import stat
            def _onerror(func, p, exc):
                try:
                    os.chmod(p, stat.S_IWRITE)
                    func(p)
                except Exception:
                    pass
            shutil.rmtree(gitdir, onerror=_onerror)

        for cmd in [
            f'git init -b main',
            f'git add -A',
            f'git commit -m "Initial import: {name} (sanitized)"',
        ]:
            r = run(cmd, cwd=path)
            if r.returncode != 0 and "nothing to commit" not in r.stdout:
                print(f"  git err: {(r.stderr or r.stdout)[:150]}")
                break

        # ensure .gitignore excludes pycache/env
        gi = os.path.join(path, ".gitignore")
        needed = ["__pycache__/", "*.py[cod]", ".env", ".venv/", "venv/"]
        existing = open(gi).read() if os.path.exists(gi) else ""
        missing = [n for n in needed if n not in existing]
        if missing:
            with open(gi, "a", encoding="utf-8") as f:
                if existing and not existing.endswith("\n"):
                    f.write("\n")
                f.write("\n".join(missing) + "\n")
            run('git add -A && git commit -m "chore: complete .gitignore"', cwd=path)

        # create private repo & push
        r = run(f'"{GH}" repo create {name} --private -d "{desc}"')
        out = (r.stdout + r.stderr).strip()
        if "already exists" in out:
            print("  repo exists on GitHub, using it")
        elif r.returncode != 0:
            print(f"  create err: {out[:200]}")
            continue
        else:
            print(f"  created: {out[:80]}")

TOKEN = os.environ.get("GH_TOKEN", "")
        r = run('git push -u origin main --force', cwd=path)
        if "main" in (r.stdout + r.stderr) or r.returncode == 0:
            print("  pushed ✓")
            # scrub token from remote url
            run(f'git remote set-url origin git@github.com:mhsaeed786/{name}.git', cwd=path)
        else:
            print(f"  push err: {(r.stderr or r.stdout)[:200]}")


if __name__ == "__main__":
    main()
