"""Create super-app repo on GitHub (private - contains company-derived code)
and push. Uses GH_TOKEN env var - no embedded credentials.
"""
import os
import subprocess

GH = r"C:\Program Files\GitHub CLI\gh.exe"
TOKEN = os.environ.get("GH_TOKEN")
if not TOKEN:
    # fall back to the session PAT provided by user earlier in central secrets
    env_path = r"C:\Users\LOQ\secrets\.env.central"
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("GH_TOKEN="):
                TOKEN = line.split("=", 1)[1].strip()
                break
if not TOKEN:
    # last resort: push_staging used the user-provided PAT via env; prompt env
    raise SystemExit("GH_TOKEN not set and not found in central secrets")

env = dict(os.environ, GH_TOKEN=TOKEN)


def run(cmd, cwd=None, timeout=300):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                          shell=True, env=env)


# safety: confirm no embedded PATs in tracked files
r = subprocess.run(["git", "grep", "-l", ("github" + "_pat_")],
                   capture_output=True, text=True, cwd=r"C:\Users\LOQ\super-app")
if r.stdout.strip():
    print("EMBEDDED TOKENS FOUND in:", r.stdout)
    raise SystemExit(1)
print("secret check: clean")

r = run(f'"{GH}" repo create super-app --private -d "Unified AI Super App: '
        f'BA/QA suite (7 modules) + OneAgent autonomous loop + AI Studio UI"')
out = (r.stdout + r.stderr).strip()
print("create:", out[:120] if out else "(exists?)")

run(f"git remote add origin https://x-access-token:{TOKEN}"
    f"@github.com/mhsaeed786/super-app.git")
r = run("git push -u origin main", timeout=600)
ok = "main" in (r.stdout + r.stderr)
print("push:", "OK" if ok else (r.stderr or r.stdout)[-200:])
if ok:
    run("git remote set-url origin git@github.com:mhsaeed786/super-app.git")
    print("remote scrubbed of token")
