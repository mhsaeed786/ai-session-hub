"""Rename imported Hermes sessions that have junk titles.

Uses first substantive user message as the title.
Read-only on state.db; renames go through the hermes CLI.
"""
import re
import sqlite3
import subprocess

DB = r"C:\Users\LOQ\AppData\Local\hermes\state.db"

c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
rows = c.execute("""
    SELECT s.id,
           COALESCE((SELECT substr(m.content,1,60) FROM messages m
             WHERE m.session_id=s.id AND m.role='user'
               AND LENGTH(m.content)>25
             ORDER BY m.rowid LIMIT 1), '')
    FROM sessions s
    WHERE s.title IS NULL OR s.title='' OR s.title LIKE 'Imported from%'
       OR s.title LIKE 'New Chat%' OR LENGTH(s.title) < 6
    LIMIT 300""").fetchall()
c.close()
print(f"sessions needing rename: {len(rows)}")

renamed = failed = 0
for sid, first in rows:
    t = re.sub(r"\s+", " ", (first or "")).strip()
    if len(t) < 8:
        continue
    if len(t) > 55:
        t = t[:55].rsplit(" ", 1)[0]
    r = subprocess.run(["hermes", "sessions", "rename", sid, t],
                       capture_output=True, text=True, timeout=60)
    if r.returncode == 0:
        renamed += 1
    else:
        failed += 1
        if failed <= 3:
            print("  err:", (r.stderr or r.stdout)[:120].replace("\n", " "))

print(f"renamed: {renamed}  failed: {failed}")
