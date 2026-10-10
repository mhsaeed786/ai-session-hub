"""Dump schemas of every AI store so lifetime script can be exact."""
import os, glob, sqlite3, json

HOME = os.path.expanduser("~")
Q = os.path.join(HOME, "harness-migration")

DBS = [
    os.path.join(Q, "quarantine-20260927-070220", "goose_live", "sessions.db"),
    os.path.join(Q, "quarantine-20260927-070220", "codex_state", "state_5.sqlite"),
    os.path.join(Q, "quarantine-20260927-070220", "opencode_db", "opencode.db"),
    os.path.join(Q, "quarantine-20260927-070220", "mimocode", "mimocode.db"),
    os.path.join(Q, "quarantine-20260927-070220", "zcode_db", "db.sqlite"),
    os.path.join(HOME, "allmydata-work", "vibe-code-and-sessions", "ai-sessions", "misc", "kilo", "kilo.db"),
    os.path.join(HOME, ".gemini", "antigravity", "conversations", "04fbc3c0-e08e-47e0-992d-f6eeb7d31fa9.db"),
    os.path.join(HOME, ".gemini", "antigravity", "conversation_summaries.db"),
    os.path.join(HOME, "allmydata-work", "vibe-code-and-sessions", "ai-sessions", "antigravity", "cli",
                 "conversations", "0717c544-25bc-4e04-9f32-ffee9d915838.db"),
]

for db in DBS:
    print("=" * 78)
    print(db)
    print("  size:", os.path.getsize(db) if os.path.exists(db) else "MISSING")
    if not os.path.exists(db):
        continue
    try:
        c = sqlite3.connect("file:%s?mode=ro" % db.replace("\\", "/"), uri=True)
        tabs = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    except Exception as e:
        print("  ERR", e)
        continue
    for t in tabs:
        try:
            cols = [r[1] for r in c.execute("PRAGMA table_info(%s)" % t)]
            n = c.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
        except Exception:
            continue
        print(f"   {t}  rows={n}")
        print(f"      cols: {cols}")
    c.close()

# openclaw sessions.json
p = os.path.join(Q, "quarantine-20260927-070220", "openclaw", "sessions.json")
print("=" * 78)
print(p)
if os.path.exists(p):
    d = json.load(open(p, encoding="utf-8", errors="replace"))
    print("  type:", type(d).__name__, "len:", len(d) if hasattr(d, "__len__") else "?")
    sample = d[0] if isinstance(d, list) and d else (list(d.values())[0] if isinstance(d, dict) and d else d)
    print("  sample keys:", list(sample.keys()) if isinstance(sample, dict) else str(sample)[:200])
    s = json.dumps(sample)[:800]
    print("  sample:", s)
