"""Find every AI harness session store still present on this PC.

Reports per-harness: path, session count, whether already imported to Hermes.
"""
import os
import glob
import json
import sqlite3

HOME = r"C:\Users\LOQ"
STORES = [
    # (label, path pattern, kind)
    ("Hermes (live)", r"AppData\Local\hermes\state.db", "sqlite"),
    ("Antigravity", r".gemini\antigravity\*.db", "any"),
    ("Antigravity conv", r".gemini\antigravity\**\*.json", "any"),
    ("Goose (Block)", r"AppData\Roaming\Block\goose\data\sessions\*.db", "sqlite"),
    ("Goose (goose dir)", r"AppData\Local\goose\data\sessions\*.db", "sqlite"),
    ("Claude Code", r".claude\projects\**\*.jsonl", "jsonl"),
    ("Claude history", r".claude\history.jsonl", "jsonl"),
    ("Codex", r".codex\sessions\**\*.jsonl", "jsonl"),
    ("Codex db", r".codex\*.sqlite", "sqlite"),
    ("opencode", r".local\share\opencode\opencode.db", "sqlite"),
    ("opencode storage", r".local\share\opencode\storage\**\*.json", "json"),
    ("openworker", r"openworker\**\*.db", "sqlite"),
    ("openworker json", r"openworker\**\*.json", "json"),
    ("Zcode", r".zcode\cli\db\*.sqlite", "sqlite"),
    ("CherryStudio", r"AppData\Roaming\CherryStudio\**\*.db", "sqlite"),
    ("Z.AI", r".zai\*.log", "log"),
    ("OpenClaw", r".openclaw\sessions\*.jsonl", "jsonl"),
    ("Codeium/Windsurf", r".codeium\chat_state\*.pb", "pb"),
    ("Trae", r"AppData\Roaming\Trae\User\workspaceStorage\**\*.json", "json"),
    ("Copilot", r"AppData\Roaming\GitHub Copilot\**\*.json", "json"),
    ("mimocode", r".local\share\mimocode\mimocode.db", "sqlite"),
    ("AI Session Extractor", r"ai-session-extractor\data\*.db", "sqlite"),
    ("Hermes WSL backup", r"hermes-sessions\hermes-wsl\state.db", "sqlite"),
]

rows = []
for label, pattern, kind in STORES:
    hits = glob.glob(os.path.join(HOME, pattern), recursive=True)
    if not hits:
        rows.append((label, 0, 0, "ABSENT"))
        continue
    total_bytes = 0
    for h in hits:
        try:
            total_bytes += os.path.getsize(h)
        except OSError:
            pass
    # session count attempt
    n = len(hits)
    for h in hits:
        if h.endswith((".db", ".sqlite", ".sqlite3")):
            try:
                c = sqlite3.connect(f"file:{h}?mode=ro", uri=True)
                tabs = [r[0] for r in c.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'")]
                for t in ("sessions", "session", "messages", "threads",
                          "conversation", "history", "usage_ledger"):
                    if t in tabs:
                        try:
                            cnt = c.execute(
                                f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                            n = max(n, cnt)
                        except sqlite3.Error:
                            pass
                c.close()
            except sqlite3.Error:
                pass
        elif h.endswith(".jsonl"):
            try:
                with open(h, encoding="utf-8", errors="replace") as f:
                    lines = sum(1 for _ in f)
                n = max(n, lines)
            except OSError:
                pass
    rows.append((label, len(hits), total_bytes, n))

print(f"{'HARNESS':26s} {'FILES':>6s} {'MB':>9s} {'~SESSIONS':>11s}  STATUS")
print("-" * 72)
present = 0
for label, files, size, n in rows:
    mb = size / 1_048_576
    status = "PRESENT" if files else "migrated/removed"
    if files:
        present += 1
    print(f"{label:26s} {files:>6d} {mb:>9.1f} {n:>11d}  {status}")
print("-" * 72)
print(f"harnesses still holding data: {present}")
