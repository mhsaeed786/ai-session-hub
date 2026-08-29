"""Find USER-AUTHORED loose Python scripts (exclude installed libs/tools)."""
import os

HOME = r"C:\Users\LOQ"
# Exclude tool/library installs entirely
EXCLUDE_TOP = {
    "AppData", "Local Settings", ".unsloth", ".ollama", ".cache", ".npm",
    "node", ".codex", ".claude", ".gemini", ".codeium", ".trae", ".zcode",
    ".openclaw", ".openclaw-autoclaw", ".hermes", ".hermes-wsl", ".antigravity",
    ".cherrystudio", ".copilot", ".tabnine", ".zai", ".oneagent", ".agents",
    "ai-session-hub",  # already pushed
}
SKIP_DIRS = {"node_modules", "__pycache__", "venv", ".venv", ".git",
             "site-packages", "dist-packages"}
MARKERS = ("requirements.txt", "package.json", "setup.py", "pyproject.toml", ".git")
# Library/interpreter/tool dirs - never user code
EXCLUDE_SUBSTR = ("Application Data", "cpython-", "uv\\python", "Lib\\",
                  "Local Settings", ".unsloth")

results = []
for dirpath, dirnames, filenames in os.walk(HOME):
    rel = os.path.relpath(dirpath, HOME)
    if any(x in rel for x in EXCLUDE_SUBSTR):
        dirnames[:] = []
        continue
    top = rel.split(os.sep)[0]
    if top in EXCLUDE_TOP:
        dirnames[:] = []
        continue
    dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
    depth = rel.count(os.sep)
    if depth > 4:
        dirnames[:] = []
        continue
    # skip dirs that are real projects
    if any(os.path.exists(os.path.join(dirpath, m)) for m in MARKERS):
        continue
    for fn in filenames:
        if fn.endswith(".py") and not fn.startswith("_"):
            fp = os.path.join(dirpath, fn)
            try:
                size = os.path.getsize(fp)
                with open(fp, encoding="utf-8", errors="replace") as f:
                    head = f.read(400)
            except OSError:
                continue
            results.append((fp, size, head))

results.sort(key=lambda x: -x[1])
print(f"User loose scripts: {len(results)}\n")
home_prefix = HOME + os.sep
for fp, size, head in results[:80]:
    first = head.splitlines()[0][:70] if head else ""
    rel = fp.replace(home_prefix, "")
    print(f"  {size:>7}  {rel}  | {first}")
