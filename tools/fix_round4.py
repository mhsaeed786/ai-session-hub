"""Round 4: finish the last 3 fixes."""
import subprocess
import os
import re


def run(cmd, cwd=None, timeout=300):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                          timeout=timeout, shell=True)


def vpy(path):
    return os.path.join(path, "venv", "Scripts", "python.exe")


def vpip(path):
    return os.path.join(path, "venv", "Scripts", "pip.exe")


# --- 1. One-Agent: install remaining deps (bs4 + likely more)
print("=== One-Agent full deps ===")
p = r"C:\Users\LOQ\repo-audit\One-Agent"
deps = ["requests", "rich", "pydantic", "beautifulsoup4", "lxml",
        "python-dotenv", "colorama"]
run(f'"{vpip(p)}" install -q ' + " ".join(deps), timeout=900)
r = run(f'"{vpy(p)}" -c "import main"', cwd=p)
ok1 = r.returncode == 0
print("One-Agent:", "PASS" if ok1 else (r.stderr or "")[-250:].replace(chr(10), " | "))

# --- 2. teams-scraper: check actual package layout
print("=== teams-scraper layout ===")
p = r"C:\Users\LOQ\teams-task-scraper"
src_pkg = os.path.join(p, "src", "teams_task_scraper")
print("  src pkg exists:", os.path.isdir(src_pkg))
r = run(f'"{vpip(p)}" install -q -e .', timeout=600)
err = (r.stderr or "")
if "error" in err.lower():
    print("  editable install error:", err[-200:])
else:
    # try with PYTHONPATH=src instead
    env_cmd = (f'set PYTHONPATH={p}\\src && "{vpy(p)}" '
               f'-m teams_task_scraper.cli --help')
    r2 = run(env_cmd, cwd=p)
    print("teams-scraper (PYTHONPATH):",
          "PASS" if r2.returncode == 0 else
          ((r2.stderr or "") or (r2.stdout or ""))[-200:].replace(chr(10), " | "))

# --- 3. NovelForge: fix the broken alias line properly
print("=== NovelForge alias fix ===")
nf_root = r"C:\Users\LOQ\Documents\Migrated data\Initiatives\NovelForge"
engine_path = os.path.join(nf_root, "novel_forge", "core", "engine.py")
with open(engine_path, encoding="utf-8") as f:
    eng = f.read()
# remove broken alias with colon
eng = eng.replace("from .config import PlotStructureConfig: as NovelConfig",
                  "from .config import PlotStructureConfig as NovelConfig")
with open(engine_path, "w", encoding="utf-8", newline="") as f:
    f.write(eng)

# check what engine.py actually needs from config
need = set(re.findall(r"(?:config|cfg)\.([A-Za-z_]+)", eng))
print("  attributes referenced:", sorted(need)[:10])
with open(os.path.join(nf_root, "novel_forge", "core", "config.py"),
          encoding="utf-8") as f:
    cfg_content = f.read()
defined = re.findall(r"class\s+([A-Za-z_]+)", cfg_content)
print("  classes defined:", defined)

r = run(f'"{vpy(nf_root)}" -c "import sys; sys.path.insert(0,\'.\'); '
        f'from novel_forge.output import exporter; print(\'OK\')"',
        cwd=nf_root)
print("NovelForge:", "PASS" if r.returncode == 0 else
      (r.stderr or "")[-300:].replace(chr(10), " | "))
