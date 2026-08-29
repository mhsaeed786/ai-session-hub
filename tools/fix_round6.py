"""Round 6: fix NovelForge __init__ imports to match actual classes."""
import os
import re
import subprocess

NF = r"C:\Users\LOQ\Documents\Migrated data\Initiatives\NovelForge"
init_path = os.path.join(NF, "novel_forge", "__init__.py")
cfg_path = os.path.join(NF, "novel_forge", "core", "config.py")

with open(cfg_path, encoding="utf-8") as f:
    cfg = f.read()
defined = re.findall(r"class\s+([A-Za-z_][A-Za-z0-9_]*)", cfg)
print("classes actually defined:", defined)

with open(init_path, encoding="utf-8") as f:
    init = f.read()

# Replace the broken import line with what exists
init = re.sub(
    r"from \.core\.config import [^\n]+",
    "from .core.config import " + ", ".join(defined),
    init)

# Also alias for backward compat if code elsewhere expects NovelConfig
if "NovelConfig" not in defined and "NovelConfig" in init:
    init = init.replace(", ".join(defined),
                        ", ".join(defined) + f", {defined[0]} as NovelConfig")

with open(init_path, "w", encoding="utf-8", newline="") as f:
    f.write(init)
print("patched __init__.py")


def run(cmd, cwd=None, timeout=120):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                          timeout=timeout, shell=True)


def vpy(path):
    return os.path.join(path, "venv", "Scripts", "python.exe")


root = NF
r = run(f'"{vpy(root)}" -c "import sys; sys.path.insert(0,\'.\'); '
        f'from novel_forge.output import exporter; print(\'OK\')"', cwd=root)
print("exporter:", "PASS" if r.returncode == 0 else
      (r.stderr or "")[-300:].replace(chr(10), " | "))

# deeper: does full package import?
r2 = run(f'"{vpy(root)}" -c "import sys; sys.path.insert(0,\'.\'); '
         f'import novel_forge; print(\'full pkg OK\')"', cwd=root)
print("full package:", "PASS" if r2.returncode == 0 else
      (r2.stderr or "")[-300:].replace(chr(10), " | "))
