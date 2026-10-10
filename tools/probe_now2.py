"""Probe AI token stores - targeted paths only (no recursive glob over HOME)."""
import os, glob, sqlite3

HOME = os.path.expanduser("~")

CANDS = {
    "hermes_live":  [r"AppData\Local\hermes\state.db"],
    "hermes_prof":  glob.glob(os.path.join(HOME, "AppData", "Local", "hermes", "profiles", "*", "state.db")),
    "hermes_other": [r"hermes-sessions\hermes-wsl\state.db",
                     os.path.join("session-migration-backup-20260822", "c", "Users",
                                  os.path.basename(HOME), "Goose Chats (Old)",
                                  "_wsl_cache", "hermes_state.db"),
                     r"ai-session-hub\db\session_hub.db"],
    "goose":        [r"AppData\Roaming\Block\goose\data\sessions\sessions.db",
                     r"AppData\Roaming\Block\goose\sessions.db",
                     r"allmydata-work\vibe-code-and-sessions\ai-sessions\goose\sessions.db"],
    "codex":        glob.glob(os.path.join(HOME, ".codex", "*.sqlite")),
    "opencode":     [r".local\share\opencode\opencode.db"],
    "mimocode":     [r".local\share\mimocode\mimocode.db"],
    "zcode":        [r".zcode\cli\db\db.sqlite"],
    "antigrav":     glob.glob(os.path.join(HOME, ".gemini", "antigravity", "conversations", "*.db")),
}

def probe(path):
    if not os.path.exists(path):
        print(f"  MISSING  {path}")
        return
    sz = os.path.getsize(path)
    try:
        c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        tabs = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    except sqlite3.Error as e:
        print(f"  NOTDB    {path} ({sz//1024}KB): {e}")
        try: c.close()
        except Exception: pass
        return
    print(f"  OK       {path} ({sz//1024}KB, {len(tabs)} tables)")
    for t in tabs:
        try:
            cols = [r[1] for r in c.execute(f"PRAGMA table_info({t})")]
        except sqlite3.OperationalError:
            continue
        tok = [x for x in cols if any(k in x.lower() for k in ("token", "usage", "cost"))]
        if not tok:
            continue
        sums = []
        for col in tok:
            try:
                v = c.execute(f"SELECT SUM({col}) FROM {t}").fetchone()[0]
            except (sqlite3.OperationalError, sqlite3.DatabaseError):
                continue
            if isinstance(v, (int, float)) and v:
                sums.append(f"{col}={int(v):,}")
        if sums:
            try:
                n = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            except sqlite3.Error:
                n = "?"
            print(f"     {t} (rows={n}): " + "; ".join(sums))
    c.close()

for label, paths in CANDS.items():
    print(f"\n### {label}")
    for p in paths:
        probe(os.path.join(HOME, p) if not os.path.isabs(p) else p)
