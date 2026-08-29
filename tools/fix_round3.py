"""Round 3: fix the remaining 4 failures one by one."""
import subprocess
import os
import sys


def run(cmd, cwd=None, timeout=300):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                          timeout=timeout, shell=True)


def vpy(path):
    return os.path.join(path, "venv", "Scripts", "python.exe")


def vpip(path):
    return os.path.join(path, "venv", "Scripts", "pip.exe")


# --- 1. One-Agent: needs requests + more; install a broad set
print("=== One-Agent deps ===")
p = r"C:\Users\LOQ\repo-audit\One-Agent"
run(f'"{vpip(p)}" install -q requests rich pydantic', timeout=600)
r = run(f'"{vpy(p)}" -c "import main"', cwd=p)
print("One-Agent:", "PASS" if r.returncode == 0 else
      (r.stderr or "")[-200:].replace(chr(10), " | "))

# --- 2. ollama-evals: dotenv missing
print("=== ollama-evals deps ===")
p = r"C:\Users\LOQ\Documents\ollama-eval-system"
run(f'"{vpip(p)}" install -q python-dotenv', timeout=300)
r = run(f'"{vpy(p)}" -c "from src import server"', cwd=p)
print("ollama-evals:", "PASS" if r.returncode == 0 else
      (r.stderr or "")[-200:].replace(chr(10), " | "))

# --- 3. teams-scraper: needs editable install for module path
print("=== teams-scraper install ===")
p = r"C:\Users\LOQ\teams-task-scraper"
run(f'"{vpip(p)}" install -q -e .', timeout=600)
r = run(f'"{vpy(p)}" -m teams_task_scraper.cli --help', cwd=p)
print("teams-scraper:", "PASS" if r.returncode == 0 else
      (r.stderr or "")[-200:].replace(chr(10), " | "))

# --- 4. NovelForge: NovelConfig import name issue
print("=== NovelForge config class ===")
cfg = os.path.join(r"C:\Users\LOQ\Documents\Migrated data\Initiatives\NovelForge",
                   "novel_forge", "core", "config.py")
with open(cfg, encoding="utf-8") as f:
    content = f.read()
classes = [ln.split("class ")[1].split("(")[0].strip()
           for ln in content.splitlines()
           if ln.startswith("class ") and ":" in ln]
print("  classes in config.py:", classes)
target = None
for c in classes:
    if "config" in c.lower():
        target = c
        break
if target and target != "NovelConfig":
    engine_path = cfg.replace("config.py", os.path.join("engine.py"))
    with open(engine_path, encoding="utf-8") as f:
        eng = f.read()
    eng = eng.replace(
        "from .config import NovelConfig",
        f"from .config import {target} as NovelConfig")
    with open(engine_path, "w", encoding="utf-8", newline="") as f:
        f.write(eng)
    print(f"  aliased {target} -> NovelConfig in engine.py")
elif not target:
    # maybe it's a dataclass named differently or defined inline
    print("  no config class found - will alias any class")
    if classes:
        first = classes[0]
        engine_path = cfg.replace("config.py", os.path.join("engine.py"))
        with open(engine_path, encoding="utf-8") as f:
            eng = f.read()
        eng = eng.replace(
            "from .config import NovelConfig",
            f"from .config import {first} as NovelConfig")
        with open(engine_path, "w", encoding="utf-8", newline="") as f:
            f.write(eng)
        print(f"  aliased {first} -> NovelConfig")

novel_root = r"C:\Users\LOQ\Documents\Migrated data\Initiatives\NovelForge"
r = run(f'"{vpy(novel_root)}" '
        f'-c "import sys; sys.path.insert(0,\'.\'); '
        f'from novel_forge.output import exporter; print(\'OK\')"',
        cwd=novel_root)
print("NovelForge:", "PASS" if r.returncode == 0 else
      (r.stderr or "")[-250:].replace(chr(10), " | "))
