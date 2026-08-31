"""Hunt for EVERY token record on the whole PC.

The 140M figure only covered live Hermes + quarantined files. But:
- Hermes sessions may span MULTIPLE dbs (old imports, profiles, backups)
- The WSL/old-PC archives may have their own state dbs
- ZAI/Antigravity/CherryStudio/etc may have dbs or jsonl with usage
- The Goose 'accumulated_total_tokens' was NOT summed (only in/out)
- Old Hermes session store: AppData might hold multiple state files

Search strategy: find every *.db/*.sqlite*/state* + every jsonl/log with
'tokens' strings, then extract.
"""
import os
import glob
import sqlite3
import json

import os
HOME = os.environ.get("ASH_HOME") or str(__import__("pathlib").Path.home())
SKIP = ("node_modules", "site-packages", "dist-packages", "venv", ".venv",
        "__pycache__", "repo-audit", "Documents/Migrated data/Initiatives")

print("Phase 1: find candidate databases")
db_candidates = []
for root, dirs, files in os.walk(HOME):
    rel = os.path.relpath(root, HOME)
    if any(s in rel for s in SKIP):
        dirs[:] = []
        continue
    for f in files:
        low = f.lower()
        if low.endswith((".db", ".sqlite", ".sqlite3", ".db-wal")):
            p = os.path.join(root, f)
            try:
                size = os.path.getsize(p)
            except OSError:
                continue
            if size > 10_000:  # skip tiny
                db_candidates.append((p, size))

print(f"Found {len(db_candidates)} dbs; probing for token columns...")
token_dbs = []
for p, size in db_candidates:
    try:
        c = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
        tables = [r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")]
        hits = []
        for t in tables:
            try:
                cols = [r[1] for r in c.execute(f"PRAGMA table_info({t})")]
                tok = [x for x in cols if "token" in x.lower()]
                if tok:
                    hits.append((t, tok))
            except sqlite3.OperationalError:
                continue
        if hits:
            token_dbs.append((p, size, hits))
        c.close()
    except (sqlite3.OperationalError, sqlite3.DatabaseError):
        continue

print(f"\n{len(token_dbs)} dbs have token columns:\n")
grand_in = grand_out = 0
for p, size, hits in token_dbs:
    print(f"== {p} ({size//1024}KB)")
    try:
        c = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
        for t, tok_cols in hits:
            sums = []
            for col in tok_cols:
                try:
                    v = c.execute(
                        f"SELECT SUM({col}) FROM {t}").fetchone()[0]
                    if v:
                        sums.append(f"{col}={v:,}")
                        if "input" in col.lower():
                            grand_in += v
                        if "output" in col.lower():
                            grand_out += v
                except sqlite3.OperationalError:
                    continue
            if sums:
                print(f"   {t}: {'; '.join(sums)}")
        c.close()
    except sqlite3.Error as e:
        print(f"   err: {e}")

print()
print("=" * 70)
print(f"DB-hunt grand totals: input={grand_in:,} output={grand_out:,}")
print("=" * 70)
