"""Verify Hermes token columns + probe Codex/Goose formats for hidden token data."""
import sqlite3
import os
import glob
import json

import os
HOME = os.environ.get("ASH_HOME") or str(__import__("pathlib").Path.home())

# 1. Hermes: what token columns exist and sample values
db = os.path.join(HOME, r"AppData\Local\hermes\state.db")
c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
for table in ("sessions", "messages"):
    try:
        cols = [r[1] for r in c.execute(f"PRAGMA table_info({table})")]
        tok_cols = [x for x in cols if "token" in x.lower() or "cost" in x.lower()
                    or "usage" in x.lower()]
        print(f"{table}: {len(cols)} cols; token-ish: {tok_cols}")
    except sqlite3.OperationalError:
        print(f"{table}: missing")

# sample session token values
try:
    rows = c.execute(
        "SELECT id, input_tokens FROM sessions "
        "WHERE input_tokens IS NOT NULL ORDER BY input_tokens DESC LIMIT 5"
    ).fetchall()
    for sid, t in rows:
        print(f"  session {sid}: input_tokens={t}")
    tot_in = c.execute(
        "SELECT SUM(input_tokens), SUM(output_tokens), SUM(cache_tokens) "
        "FROM sessions").fetchone()
    print(f"  SUM in/out/cache: {tot_in}")
except sqlite3.OperationalError as e:
    print(f"  sessions token query: {e}")

# messages table tokens?
try:
    mcols = [r[1] for r in c.execute("PRAGMA table_info(messages)")]
    mtok = [x for x in mcols if "token" in x.lower()]
    print(f"  messages token cols: {mtok}")
    if mtok:
        sums = []
        for mcol in mtok:
            v = c.execute(f"SELECT SUM({mcol}) FROM messages").fetchone()[0]
            sums.append(f"{mcol}={v}")
        print(f"  messages SUMs: {sums}")
except sqlite3.OperationalError:
    pass
c.close()

# 2. Codex rollouts: find the token event structure
print("\nCodex rollout token events:")
for fp in glob.glob(os.path.join(
        HOME, r"session-migration-backup-20260822\quarantine\codex-sessions\*.jsonl"))[:2]:
    with open(fp, encoding="utf-8", errors="replace") as f:
        for line in f:
            if "token" in line.lower():
                try:
                    d = json.loads(line)
                    s = json.dumps(d)
                    print(f"  {os.path.basename(fp)[:30]}: {s[:180]}")
                except json.JSONDecodeError:
                    pass
                break

# 3. Goose: any 'tokens' or 'usage' keys?
print("\nGoose JSON keys:")
for fp in glob.glob(os.path.join(
        HOME, r"session-migration-backup-20260822\quarantine\goose\*.json"))[:1]:
    with open(fp, encoding="utf-8") as f:
        d = json.load(f)
    print(f"  top-level: {list(d.keys())}")
    conv = d.get("conversation") or []
    if conv:
        print(f"  first msg keys: {list(conv[0].keys())}")
