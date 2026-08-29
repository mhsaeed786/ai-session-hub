"""Round 5: final two fixes - teams-scraper PYTHONPATH + NovelForge missing module."""
import subprocess
import os


def run(cmd, cwd=None, timeout=300):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                          timeout=timeout, shell=True)


def vpy(path):
    return os.path.join(path, "venv", "Scripts", "python.exe")


# --- 1. teams-scraper via PYTHONPATH
print("=== teams-scraper (PYTHONPATH=src) ===")
p = r"C:\Users\LOQ\teams-task-scraper"
r = run(f'set "PYTHONPATH={p}\\src" && "{vpy(p)}" -m teams_task_scraper.cli --help', cwd=p)
ok_t = r.returncode == 0
print("teams-scraper:", "PASS" if ok_t else ((r.stderr or "") or (r.stdout or ""))[-250:])

# --- 2. NovelForge: research_engine module missing - check what exists
print("=== NovelForge missing modules ===")
nf = r"C:\Users\LOQ\Documents\Migrated data\Initiatives\NovelForge\novel_forge"
core_dir = os.path.join(nf, "core")
existing = sorted(os.listdir(core_dir))
print("  core/ has:", existing)

engine_path = os.path.join(core_dir, "engine.py")
with open(engine_path, encoding="utf-8") as f:
    eng = f.read()

# Find all local imports that don't resolve
import glob
all_files = {os.path.splitext(f)[0] for f in
             glob.glob(os.path.join(nf, "**", "*.py"), recursive=True)}
missing = []
for ln in eng.splitlines():
    ln_s = ln.strip()
    if ln_s.startswith("from .") and " import " in ln_s:
        mod = ln_s.split("from .")[1].split(" import")[0].strip()
        if mod not in all_files and mod != "config":
            missing.append((mod, ln_s))
print("  unresolved imports in engine.py:", [m[0] for m in missing])

# Create stub modules for missing ones so the package loads
for mod, orig_line in missing:
    stub_path = os.path.join(core_dir, mod.replace("/", os.sep))
    if not mod.endswith(".py"):
        stub_path += ".py"
    if not os.path.exists(stub_path):
        class_name = "".join(w.capitalize() for w in mod.split("_"))
        with open(stub_path, "w", encoding="utf-8", newline="") as f:
            f.write(
                f'"""Auto-generated stub - original module was lost in migration.\n'
                f'TODO: restore full implementation from session archives.\n"""\n\n'
                f'class {class_name}:\n'
                f'    """Placeholder - raises on use so callers fail loudly."""\n'
                f'    def __init__(self, *args, **kwargs):\n'
                f'        raise NotImplementedError(\n'
                f'            "{mod} module lost in migration; restore from archives")\n')
        print(f"  created stub: {stub_path}")

# also check other packages' engine imports
r2 = run(f'"{vpy(nf[:nf.find(chr(92)+"novel_forge")])}" '
         f'-c "import sys; sys.path.insert(0,\'.\'); '
         f'from novel_forge.output import exporter; print(\'OK\')"',
         cwd=nf[:nf.find(chr(92) + "novel_forge")])
print("NovelForge:", "PASS" if r2.returncode == 0 else
      (r2.stderr or "")[-300:].replace(chr(10), " | "))
