import glob
import os
import py_compile
import subprocess

ROOT = r"C:\Users\LOQ\Documents\ollama-eval-system"

errs = 0
total = 0
for f in glob.glob(ROOT + r"\**\*.py", recursive=True):
    if "venv" in f or "__pycache__" in f:
        continue
    total += 1
    try:
        py_compile.compile(f, doraise=True)
    except Exception as e:
        errs += 1
        print("ERR:", os.path.basename(f))
print(f"{total} py, {errs} errors")

src = os.path.join(ROOT, "src")
print("src contents:", sorted(os.listdir(src)))
for cand in ("main.py", "app.py", "server.py", "run.py"):
    p = os.path.join(src, cand)
    if os.path.exists(p):
        print(f"--- head of {cand} ---")
        with open(p, encoding="utf-8", errors="replace") as fh:
            print(fh.read(600))
