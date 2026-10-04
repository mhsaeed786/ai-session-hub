"""Re-quarantine Antigravity round 3 - use os.walk (glob skips .dot dirs,
which is why .system_generated transcripts were never moved)."""
import os
import shutil
import time

HOME = r"C:\Users\LOQ"
TS = time.strftime("%Y%m%d-%H%M%S")
SRC = os.path.join(HOME, ".gemini", "antigravity")
BUP = os.path.join(HOME, "harness-migration", f"backup-{TS}")
Q = os.path.join(HOME, "harness-migration", f"quarantine-{TS}", "antigravity")

files = []
for root, _, names in os.walk(SRC):
    for n in names:
        files.append(os.path.join(root, n))
print(f"files (os.walk): {len(files)}")
if not files:
    raise SystemExit("nothing to do")

os.makedirs(BUP, exist_ok=True)
arch = shutil.make_archive(os.path.join(BUP, "antigravity"), "gztar", SRC)
print(f"backup: {arch} ({os.path.getsize(arch)/1_048_576:.1f} MB)")

os.makedirs(Q, exist_ok=True)
moved = skipped = 0
for f in files:
    try:
        d = os.path.join(Q, os.path.relpath(f, SRC))
        os.makedirs(os.path.dirname(d), exist_ok=True)
        shutil.move(f, d)
        moved += 1
    except OSError:
        skipped += 1
print(f"moved: {moved}   skipped: {skipped}")

for d, _, _ in os.walk(SRC, topdown=False):
    try:
        os.rmdir(d)
    except OSError:
        pass
left = sum(len(fs) for _, _, fs in os.walk(SRC))
print(f"files left in store: {left}")
