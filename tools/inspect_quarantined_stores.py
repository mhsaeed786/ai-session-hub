"""Inspect the quarantined stores that were never converted, to see if they
actually contain recoverable conversations.
"""
import glob
import os
import sqlite3

HOME = r"C:\Users\LOQ"
BASE = os.path.join(HOME, "harness-migration")
QDS = sorted(glob.glob(os.path.join(BASE, "quarantine-*")))


def find(store, pattern="**/*"):
    hits = []
    for qd in QDS:
        p = os.path.join(qd, store)
        if os.path.isdir(p):
            for root, _, names in os.walk(p):
                for n in names:
                    fp = os.path.join(root, n)
                    if pattern == "**/*" or fp.endswith(pattern):
                        hits.append(fp)
    return hits


def probe_db(path, label):
    print(f"\n--- {label}: {os.path.basename(path)} "
          f"({os.path.getsize(path)/1024:.0f} KB) ---")
    try:
        c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        tabs = [r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")]
        for t in tabs:
            try:
                n = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                cols = [r[1] for r in c.execute(f"PRAGMA table_info({t})")]
                flag = ""
                if any(k in t.lower() for k in
                       ("session", "message", "conversation", "thread", "chat")):
                    flag = "  <-- SESSION DATA"
                print(f"    {t:28s} {n:7d} rows  {cols[:6]}{flag}")
            except sqlite3.Error:
                pass
        c.close()
    except sqlite3.Error as e:
        print("    open failed:", e)


# databases
for store, label in [("goose_live", "GOOSE"), ("codex_state", "CODEX"),
                     ("opencode_db", "OPENCODE"), ("zcode_db", "ZCODE"),
                     ("mimocode", "MIMOCODE"), ("ai_extractor", "AI_EXTRACTOR")]:
    for fp in find(store):
        if fp.endswith((".db", ".sqlite")) and not fp.endswith(("-wal", "-shm")):
            probe_db(fp, label)

# jsonl
print("\n--- CLAUDE HISTORY / CODEX SESSIONS / OPENCLAW (jsonl) ---")
for store in ("claude_history", "claude_projects", "codex_sessions", "openclaw"):
    for fp in find(store):
        if fp.endswith(".jsonl"):
            n = sum(1 for _ in open(fp, encoding="utf-8", errors="replace"))
            print(f"  {store:16s} {os.path.basename(fp)[:40]:42s} {n} lines")

# logs and pb
print("\n--- ZAI LOGS (sample) ---")
for fp in find("zai_logs")[:3]:
    with open(fp, encoding="utf-8", errors="replace") as f:
        head = f.read(220).replace("\n", " ")
    print(f"  {os.path.basename(fp)[:44]:46s} {head[:110]}")

print("\n--- CODEIUM .pb (bytes, first printable) ---")
for fp in find("codeium_state")[:3]:
    with open(fp, "rb") as f:
        raw = f.read(200)
    txt = "".join(chr(b) if 32 <= b < 127 else "." for b in raw)
    print(f"  {os.path.basename(fp)[:44]:46s} {txt[:90]}")

print("\n--- AI_EXTRACTOR non-png files ---")
for fp in find("ai_extractor"):
    e = os.path.splitext(fp)[1].lower()
    if e in (".json", ".db", ".md", ".txt"):
        print(f"  {e:6s} {os.path.relpath(fp, BASE)[:80]}")
