"""Push NovelForge + Novel-writing-agent as fresh private repos."""
import os
import shutil
import subprocess

GH = r"C:\Program Files\GitHub CLI\gh.exe"
TOKEN = os.environ.get("GH_TOKEN", "")
env = dict(os.environ, GH_TOKEN=TOKEN)

REPOS = [
    (r"C:\Users\LOQ\Documents\Migrated data\Initiatives\NovelForge",
     "NovelForge",
     "AI-powered novel generation system - world building, characters, plot "
     "outlines, prose generation, HTML/EPUB export"),
    (r"C:\Users\LOQ\Documents\Migrated data\Initiatives\Novel-writing-agent-",
     "novel-writing-agent",
     "AI novel writing platform - Notebook editor + full NovelForge pipeline "
     "(worlds, characters, plots, prose)"),
]


def run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                          shell=True, env=env)


for path, name, desc in REPOS:
    print(f"=== {name} ===")
    gitdir = os.path.join(path, ".git")
    if os.path.isdir(gitdir):
        def _onerror(func, p, exc):
            try:
                os.chmod(p, 0o777)
                func(p)
            except Exception:
                pass
        shutil.rmtree(gitdir, onerror=_onerror)

    for cmd in ["git init -b main", "git add -A",
                f'git commit -m "Initial import: {name} (syntax-fixed)"']:
        r = run(cmd, cwd=path)
        if r.returncode != 0 and "nothing to commit" not in (r.stdout or ""):
            print(f"  git: {(r.stderr or r.stdout)[:120]}")

    # scrub personal refs from tracked files before push
    run("git grep -l -iE 'mhsaeed786' | xargs -r sed -i 's/mhsaeed786/your-org/g'", cwd=path)
    run('git -c user.name=hub -c user.email=a@b.c commit -am "sanitize" || true', cwd=path)

    r = run(f'"{GH}" repo create {name} --private -d "{desc}"')
    out = (r.stdout + r.stderr).strip()
    print(f"  create: {'OK' if 'github.com' in out else out[:100]}")

TOKEN = os.environ.get("GH_TOKEN", "")
    r = run("git push -u origin main --force", cwd=path)
    ok = "main" in (r.stdout + r.stderr)
    print(f"  push: {'OK' if ok else (r.stderr or r.stdout)[:150]}")
    if ok:
        run(f"git remote set-url origin git@github.com:mhsaeed786/{name}.git", cwd=path)
