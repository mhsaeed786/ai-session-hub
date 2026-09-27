"""Inspect the real schema of the two big live stores we never truly migrated."""
import sqlite3
import os
import json

HOME = r"C:\Users\LOQ"


def show(path, label, tables):
    print(f"\n{'='*70}\n{label}\n{'='*70}")
    try:
        c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        all_tabs = [r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")]
        print("tables:", all_tabs)
        for t in tables:
            if t not in all_tabs:
                continue
            n = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            cols = [r[1] for r in c.execute(f"PRAGMA table_info({t})")]
            print(f"\n-- {t}: {n} rows")
            print("   cols:", cols)
            try:
                row = c.execute(f"SELECT * FROM {t} LIMIT 1").fetchone()
                if row:
                    for cn, v in zip(cols, row):
                        s = str(v)[:90].replace("\n", " ")
                        print(f"     {cn}: {s}")
            except sqlite3.Error as e:
                print("   sample err:", e)
        c.close()
    except sqlite3.Error as e:
        print("open failed:", e)


# 1. Goose live store
g = os.path.join(HOME, r"AppData\Roaming\Block\goose\data\sessions\sessions.db")
if os.path.exists(g):
    show(g, "GOOSE LIVE sessions.db", ["sessions", "messages", "usage_ledger"])

# 2. Antigravity db
import glob
for p in glob.glob(os.path.join(HOME, r".gemini\antigravity\*.db")):
    show(p, f"ANTIGRAVITY {os.path.basename(p)}",
         ["conversations", "conversation", "messages", "sessions", "state"])

# 3. What does a hermes-imported goose row look like (reference schema)?
h = os.path.join(HOME, r"AppData\Local\hermes\state.db")
if os.path.exists(h):
    c = sqlite3.connect(f"file:{h}?mode=ro", uri=True)
    try:
        row = c.execute(
            "SELECT * FROM sessions WHERE title LIKE 'Goose%' LIMIT 1").fetchone()
        cols = [r[1] for r in c.execute("PRAGMA table_info(sessions)")]
        if row:
            print(f"\n{'='*70}\nHERMES reference (a migrated Goose session)\n{'='*70}")
            for cn, v in zip(cols, row):
                print(f"  {cn}: {str(v)[:70]}")
    except sqlite3.Error as e:
        print("hermes probe err:", e)
    c.close()
