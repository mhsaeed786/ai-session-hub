"""Diagnose the REAL live stores (not exports) that were never migrated."""
import os
import sqlite3
import glob
import json

HOME = r"C:\Users\LOQ"


def probe_sqlite(path, tables_of_interest):
    print(f"\n=== {path} ({os.path.getsize(path)/1_048_576:.1f} MB) ===")
    try:
        c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        tabs = [r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")]
        print("  tables:", ", ".join(tabs[:14]))
        for t in tables_of_interest:
            if t in tabs:
                try:
                    n = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                    cols = [r[1] for r in c.execute(f"PRAGMA table_info({t})")]
                    print(f"  {t}: {n} rows | cols: {cols[:9]}")
                except sqlite3.Error as e:
                    print(f"  {t}: err {e}")
        c.close()
    except sqlite3.Error as e:
        print("  open failed:", e)


# 1. Goose live store - the big one
g = os.path.join(HOME, r"AppData\Roaming\Block\goose\data\sessions\sessions.db")
if os.path.exists(g):
    probe_sqlite(g, ["sessions", "messages", "usage_ledger"])

# 2. Antigravity
ag = glob.glob(os.path.join(HOME, r".gemini\antigravity\*.db"))
for p in ag:
    probe_sqlite(p, ["conversations", "conversation", "messages", "sessions"])
agjson = glob.glob(os.path.join(HOME, r".gemini\antigravity\**\*.json"),
                   recursive=True)
print(f"\nAntigravity json files: {len(agjson)}")
if agjson:
    with open(agjson[0], encoding="utf-8", errors="replace") as f:
        head = f.read(400)
    print("  sample:", head[:300].replace("\n", " "))

# 3. openworker
ow = glob.glob(os.path.join(HOME, "openworker", "**", "*"), recursive=True)
print(f"\nopenworker entries: {len(ow)}")
for p in ow[:8]:
    print("  ", os.path.basename(p), os.path.getsize(p)
          if os.path.isfile(p) else "<dir>")

# 4. zcode
zc = glob.glob(os.path.join(HOME, r".zcode\cli\db\*.sqlite"))
for p in zc:
    probe_sqlite(p, ["sessions", "messages", "conversation"])

# 5. opencode storage
ocs = glob.glob(os.path.join(HOME, r".local\share\opencode\storage\**\*.json"),
                recursive=True)
print(f"\nopencode storage json: {len(ocs)}")
