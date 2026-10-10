"""Probe remaining sources: antigravity usage, hermes messages, vscode copilot,
codeium, and every content-bearing archive dir for tiktoken estimation."""
import os, glob, json, sqlite3, re

HOME = os.path.expanduser("~")
AIS = os.path.join(HOME, "allmydata-work", "vibe-code-and-sessions", "ai-sessions")
Q27 = os.path.join(HOME, "harness-migration", "quarantine-20260927-070220")

def ro(p): return sqlite3.connect("file:%s?mode=ro" % p.replace("\\", "/"), uri=True)
def tables(c): return [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]

print("=" * 80)
print("1) ANTIGRAVITY gen_metadata - does it carry token usage?")
seen = set()
for d in [os.path.join(HOME, ".gemini", "antigravity", "conversations"),
          os.path.join(AIS, "antigravity", "cli", "conversations")]:
    for fp in glob.glob(os.path.join(d, "*.db")):
        seen.add(fp)
print("  db count:", len(seen))
for fp in list(seen)[:4]:
    try:
        c = ro(fp)
        n = c.execute("SELECT COUNT(*) FROM gen_metadata").fetchone()[0]
        blob = c.execute("SELECT data FROM gen_metadata LIMIT 1").fetchone()
        c.close()
    except sqlite3.Error as e:
        print("   ERR", os.path.basename(fp), e); continue
    txt = ""
    if blob and blob[0]:
        b = blob[0]
        txt = b.decode("utf-8", "replace") if isinstance(b, (bytes, bytearray)) else str(b)
    hits = re.findall(r'"?(?:total_)?(?:prompt|input|output|candidate|thought)_?tokens"?\s*[:=]\s*\d+', txt)
    print(f"   {os.path.basename(fp)[:20]} gen_metadata rows={n} tokenkeys={hits[:4]}")
    if hits:
        print("      raw sample:", txt[:300].replace("\n", " "))

print()
print("=" * 80)
print("2) HERMES messages table token cols")
hp = os.path.join(HOME, r"AppData\Local\hermes\state.db")
c = ro(hp)
mc = [x for x in (r[1] for r in c.execute("PRAGMA table_info(messages)"))
      if "token" in x.lower() or "cost" in x.lower()]
print("   token-ish cols in messages:", mc)
for col in mc:
    try:
        print(f"     SUM({col}) =", c.execute(f"SELECT SUM({col}) FROM messages").fetchone()[0])
    except sqlite3.Error:
        pass
c.close()

print()
print("=" * 80)
print("3) VSCODE / COPILOT / CURSOR state.vscdb")
for fp in glob.glob(os.path.join(HOME, "AppData", "Roaming", "Code", "User", "**", "state.vscdb"),
                   recursive=True)[:10]:
    try:
        c = ro(fp)
        t = tables(c)
        hits = []
        for tb in t:
            cc = [r[1] for r in c.execute(f"PRAGMA table_info({tb})")]
            for col in cc:
                try:
                    v = c.execute(f"SELECT COUNT(*) FROM {tb} WHERE CAST([{col}] AS TEXT) LIKE '%token%'").fetchone()[0]
                except sqlite3.Error:
                    continue
                if v:
                    hits.append((tb, col, v))
        c.close()
        print(f"   {fp.replace(HOME,'~')}: tables={t} token-row-hits={hits[:5]}")
    except sqlite3.Error as e:
        print("   ERR", e)

# also cursor / windsurf / trae
for base in ["AppData/Roaming/Cursor/User/globalStorage/state.vscdb",
             "AppData/Roaming/Windsurf/User/globalStorage/state.vscdb",
             "AppData/Roaming/Trae/User/globalStorage/state.vscdb",
             "AppData/Local/Trae/User/globalStorage/state.vscdb"]:
    p = os.path.join(HOME, base)
    print("   exists" if os.path.exists(p) else "   -", base)

print()
print("=" * 80)
print("4) CONTENT-BEARING ARCHIVES (for tiktoken estimate)")
for cand in [os.path.join(HOME, "ai-session-extractor", "data"),
             os.path.join(HOME, "AI-Agent-Sessions-Master"),
             os.path.join(AIS, "misc"),
             os.path.join(AIS, "openclaw"),
             os.path.join(HOME, "session-migration-backup-20260822", "quarantine")]:
    if not os.path.exists(cand):
        print("   - missing", cand); continue
    files = [f for f in glob.glob(os.path.join(cand, "**", "*"), recursive=True)
             if os.path.isfile(f)]
    tot = sum(os.path.getsize(f) for f in files)
    print(f"   {cand.replace(HOME,'~')}: {len(files)} files, {tot/1e6:.1f} MB")
    for f in files[:6]:
        print(f"      {os.path.basename(f)}  {os.path.getsize(f)/1e3:.0f} KB")
