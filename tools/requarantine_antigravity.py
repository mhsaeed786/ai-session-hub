"""Re-quarantine the REGENERATED Antigravity store (round 2).

The app rebuilt its directory after the first quarantine. Same safety rules:
tar.gz backup FIRST, then move to quarantine, then remove empty dirs.
"""
import glob
import os
import shutil
import time

HOME = r"C:\Users\LOQ"
TS = time.strftime("%Y%m%d-%H%M%S")
SRC = os.path.join(HOME, ".gemini", "antigravity")
BUP = os.path.join(HOME, "harness-migration", f"backup-{TS}")
Q = os.path.join(HOME, "harness-migration", f"quarantine-{TS}", "antigravity")

files = [f for f in glob.glob(os.path.join(SRC, "**", "*"), recursive=True)
         if os.path.isfile(f)]
print(f"files in store now: {len(files)}")
if not files:
    raise SystemExit("nothing to do")

# 1. backup whole dir
os.makedirs(BUP, exist_ok=True)
arch = shutil.make_archive(os.path.join(BUP, "antigravity"), "gztar", SRC)
print(f"backup: {arch} ({os.path.getsize(arch)/1_048_576:.1f} MB)")

# 2. move to quarantine
os.makedirs(Q, exist_ok=True)
moved = skipped = 0
for f in files:
    try:
        rel = os.path.relpath(f, SRC)
        d = os.path.join(Q, rel)
        os.makedirs(os.path.dirname(d), exist_ok=True)
        shutil.move(f, d)
        moved += 1
    except OSError:
        skipped += 1
print(f"moved: {moved}   skipped (locked): {skipped}")

# 3. prune empty dirs
for d, _, _ in os.walk(SRC, topdown=False):
    try:
        os.rmdir(d)
    except OSError:
        pass
left = sum(len(fs) for _, _, fs in os.walk(SRC))
print(f"files left in store: {left}")
