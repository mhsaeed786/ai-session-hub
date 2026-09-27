"""Import all converted harness sessions into Hermes via the official importer.

One at a time, reporting success/failure, then a final count check.
"""
import glob
import os
import subprocess
import sys
import sqlite3

CONV = r"C:\Users\LOQ\harness-migration\converted"
HERMES_DB = r"C:\Users\LOQ\AppData\Local\hermes\state.db"


def hermes_count():
    c = sqlite3.connect(f"file:{HERMES_DB}?mode=ro", uri=True)
    n = c.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    c.close()
    return n


before = hermes_count()
print(f"Hermes sessions before: {before}")

files = sorted(glob.glob(os.path.join(CONV, "*", "*.jsonl")))
print(f"converting {len(files)} files into Hermes...\n")

ok = fail = 0
new_ids = []
for fp in files:
    tool = os.path.basename(os.path.dirname(fp))
    win = fp.replace("\\", "/")
    r = subprocess.run(["hermes", "sessions", "import", "--from", "claude", win],
                       capture_output=True, text=True, timeout=120)
    out = (r.stdout + r.stderr).strip()
    if "Imported" in out:
        ok += 1
        sid = out.split("as ")[-1].strip() if "as " in out else ""
        if sid:
            new_ids.append(sid)
    else:
        fail += 1
        if fail <= 3:
            print(f"  FAIL {os.path.basename(fp)[:44]}: {out[:90]}")

print(f"\nimported ok={ok} failed={fail}")
after = hermes_count()
print(f"Hermes sessions after: {after} (+{after - before})")

with open(os.path.join(CONV, "_imported_ids.txt"), "w") as f:
    f.write("\n".join(new_ids))
print(f"new session ids saved: {len(new_ids)}")
