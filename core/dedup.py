"""Deduplication engine — finds duplicate sessions across tools and within.

Two sessions are duplicates if they share:
- Same source file path, OR
- Same title + same first user message (fuzzy), OR
- Same session_id imported from overlapping paths (e.g. live DB + backup)
"""

import json
import os
import sqlite3
from collections import defaultdict

from core.sync import get_conn


def _normalize(text: str) -> str:
    """Normalize text for fuzzy comparison."""
    if not text:
        return ""
    t = text.lower().strip()
    # Collapse whitespace, strip common prefixes
    import re
    t = re.sub(r"\s+", " ", t)
    for prefix in ("please ", "hey ", "hi ", "hello ", "can you "):
        if t.startswith(prefix):
            t = t[len(prefix):]
    return t[:200]


def find_duplicates() -> dict:
    """Find all duplicate groups. Returns {duplicates: [...], total_dup_groups: int}."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, tool, session_id, title, project_path, file_path, message_count "
        "FROM sessions ORDER BY started_at DESC"
    ).fetchall()
    conn.close()

    # Index by normalized title + first user message
    by_content = defaultdict(list)
    by_file = defaultdict(list)
    by_native_id = defaultdict(list)

    for row in rows:
        # First user message fingerprint
        c = get_conn()
        first = c.execute(
            "SELECT content_text FROM messages WHERE session_fk=? AND role='user' "
            "AND content_text IS NOT NULL AND content_text != '' "
            "ORDER BY seq, id LIMIT 1", (row["id"],)).fetchone()
        c.close()
        first_text = _normalize(first["content_text"] if first else row["title"] or "")

        key = f"{first_text}"
        by_content[key].append(row)
        if row["file_path"]:
            by_file[row["file_path"]].append(row)
        by_native_id[f"{row['tool']}:{row['session_id']}"].append(row)

    duplicates = []
    seen_groups = set()

    for index in (by_content, by_file, by_native_id):
        for key, group in index.items():
            if len(group) < 2 or not key.strip():
                continue
            ids = sorted(set(r["id"] for r in group))
            if tuple(ids) in seen_groups:
                continue
            seen_groups.add(tuple(ids))
            duplicates.append({
                "ids": ids,
                "keys": list(set(r["id"] for r in group)),
                "count": len(group),
                "title": group[0]["title"],
                "tools": list(set(r["tool"] for r in group)),
                "total_messages": sum(r["message_count"] or 0 for r in group),
            })

    return {"duplicates": duplicates, "total_dup_groups": len(duplicates)}


def merge_duplicates(keep: str, remove_ids: list) -> dict:
    """Merge duplicate sessions: keep one, fold messages from the rest into it,
    then delete the rest. Returns {kept_id, merged_messages, deleted_count}."""
    conn = get_conn()

    # Gather all messages from duplicates
    all_messages = []
    for rid in remove_ids:
        msgs = conn.execute(
            "SELECT role, content_text, content_type, model, timestamp, seq "
            "FROM messages WHERE session_fk=? ORDER BY seq, id", (rid,)).fetchall()
        all_messages.extend(msgs)

    # Append messages to the kept session with new seq numbers
    existing_count = conn.execute(
        "SELECT COUNT(*) FROM messages WHERE session_fk=?", (keep,)).fetchone()[0]
    for i, m in enumerate(all_messages):
        conn.execute(
            "INSERT INTO messages (session_fk, role, content_text, content_type, "
            "model, timestamp, seq) VALUES (?,?,?,?,?,?,?)",
            (keep, m["role"], m["content_text"], m["content_type"], m["model"],
             m["timestamp"], existing_count + i + 1))

    # Update message count
    new_count = existing_count + len(all_messages)
    conn.execute("UPDATE sessions SET message_count=? WHERE id=?", (new_count, keep))

    # Delete duplicates
    for rid in remove_ids:
        conn.execute("DELETE FROM messages WHERE session_fk=?", (rid,))
        conn.execute("DELETE FROM sessions WHERE id=?", (rid,))

    conn.commit()
    conn.close()
    return {"kept_id": keep, "merged_messages": len(all_messages), "deleted_count": len(remove_ids)}
