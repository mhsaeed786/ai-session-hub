"""Exact coverage check: for each quarantined store, how many sessions exist
there vs how many are actually in Hermes?
"""
import glob
import os
import sqlite3

HOME = r"C:\Users\LOQ"
BASE = os.path.join(HOME, "harness-migration")
HERMES = os.path.join(HOME, r"AppData\Local\hermes\state.db")

c = sqlite3.connect(f"file:{HERMES}?mode=ro", uri=True)
HERMES_IDS = [str(r[0]) for r in c.execute("SELECT id FROM sessions")]
c.close()
ids_blob = " ".join(HERMES_IDS)


def find_db(store):
    out = []
    for qd in sorted(glob.glob(os.path.join(BASE, "quarantine-*"))):
        p = os.path.join(qd, store)
        if not os.path.isdir(p):
            continue
        for root, _, names in os.walk(p):
            for n in names:
                if n.endswith((".db", ".sqlite")) and not n.endswith(("-wal", "-shm")):
                    out.append(os.path.join(root, n))
    return out


def goose_report():
    print("\n=== GOOSE (quarantined sessions.db) ===")
    for db in find_db("goose_live"):
        try:
            c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            rows = c.execute("SELECT id, name FROM sessions").fetchall()
            if not rows:
                c.close()
                continue
            present = missing = 0
            missing_ids = []
            for sid, nm in rows:
                # Hermes names imported goose sessions with the source id inside
                if str(sid) in ids_blob:
                    present += 1
                else:
                    missing += 1
                    missing_ids.append((sid, nm))
            print(f"  db: {os.path.basename(db)}  sessions={len(rows)}")
            print(f"  in Hermes: {present}   MISSING: {missing}")
            for sid, nm in missing_ids[:12]:
                print(f"     missing: {str(nm)[:44]:46s} ({sid})")
            c.close()
        except sqlite3.Error as e:
            print("  err:", e)


def mimocode_report():
    print("\n=== MIMOCODE (quarantined mimocode.db) ===")
    for db in find_db("mimocode"):
        try:
            c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            tabs = [r[0] for r in c.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")]
            if "session" not in tabs:
                c.close()
                continue
            n = c.execute("SELECT COUNT(*) FROM session").fetchone()[0]
            miss = 0
            for sid, in c.execute("SELECT id FROM session"):
                if str(sid) not in ids_blob:
                    miss += 1
            print(f"  sessions={n}  in Hermes={n-miss}  MISSING: {miss}")
            c.close()
        except sqlite3.Error as e:
            print("  err:", e)


def simple_jsonl_report():
    print("\n=== JSONL STORES ===")
    for store in ("claude_history", "claude_projects", "codex_sessions", "openclaw"):
        for qd in sorted(glob.glob(os.path.join(BASE, "quarantine-*"))):
            p = os.path.join(qd, store)
            if not os.path.isdir(p):
                continue
            for root, _, names in os.walk(p):
                for n in names:
                    if not n.endswith(".jsonl"):
                        continue
                    fp = os.path.join(root, n)
                    stem = os.path.splitext(n)[0]
                    hit = stem[:30] in ids_blob
                    print(f"  {store:16s} {n[:38]:40s} "
                          f"{'in Hermes' if hit else 'MISSING?'}")


goose_report()
mimocode_report()
simple_jsonl_report()

print("\n=== CODEIUM / ZAI / AI_EXTRACTOR ===")
for store, note in (("codeium_state", "protobuf chat_state (12 .pb)"),
                    ("zai_logs", "19 .log files"),
                    ("ai_extractor", "819 files incl. 7 dbs")):
    n = 0
    for qd in sorted(glob.glob(os.path.join(BASE, "quarantine-*"))):
        p = os.path.join(qd, store)
        if os.path.isdir(p):
            for _, _, names in os.walk(p):
                n += len(names)
    print(f"  {store:16s} {n:5d} files  {note}  -> NEVER CONVERTED")
