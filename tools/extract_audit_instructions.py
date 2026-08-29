"""Extract all substantive user instructions per session into audit files."""
import sqlite3
import os

DB = r"C:\Users\LOQ\ai-session-hub\db\session_hub.db"
OUT = r"C:\Users\LOQ\session-audit-20260822"

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

rows = conn.execute(
    "SELECT id, tool, title, category, message_count FROM sessions "
    "WHERE message_count > 10 ORDER BY message_count DESC"
).fetchall()

count = 0
for r in rows:
    msgs = conn.execute(
        "SELECT seq, content_text FROM messages "
        "WHERE session_fk=? AND role='user' AND content_text IS NOT NULL "
        "AND length(content_text)>30 ORDER BY seq",
        (r["id"],),
    ).fetchall()
    safe = (r["title"] or "untitled")[:50]
    for ch in ' /\\:*?"<>|\n\r\t':
        safe = safe.replace(ch, "_")
    fn = os.path.join(OUT, f"{r['id'].replace(':','_')[:40]}_{safe}.md")
    with open(fn, "w", encoding="utf-8") as f:
        f.write(f"# {r['title']}\n\n")
        f.write(f"Tool: {r['tool']} | Category: {r['category']} | Msgs: {r['message_count']}\n\n")
        f.write(f"## User Instructions ({len(msgs)})\n\n")
        for m in msgs:
            txt = (m["content_text"] or "")[:800].replace("\n", " ")
            f.write(f"**[{m['seq']}]** {txt}\n\n")
    count += 1

print(f"Wrote {count} instruction files to {OUT}")
