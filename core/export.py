"""Exporter — writes any neutral session into another tool's native cache format.

Supports exporting directly into Hermes state.db (SQLite) so sessions are immediately
usable in Hermes Desktop.
"""

import os
import shutil
import sqlite3
from typing import Optional

from config import DB_PATH, get_adapter, all_tool_names
from core.sync import get_conn


def export_session(session_id: str, target_tool: str,
                   destination_dir: str | None = None) -> dict:
    """Export a neutral session into target_tool's native format.

    Returns {"status", "path", "error"}.
    """
    conn = get_conn()
    s = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
    if not s:
        conn.close()
        return {"status": "error", "error": f"Session not found: {session_id}"}
    messages = conn.execute(
        "SELECT role, content_text, content_type, model, timestamp, message_id "
        "FROM messages WHERE session_fk=? ORDER BY seq, id", (session_id,)).fetchall()
    conn.close()

    adapter = get_adapter(target_tool)
    if adapter is None:
        return {"status": "error", "error": f"No adapter for target tool: {target_tool}"}

    # Build ParsedMessage objects
    from adapters.base import ParsedMessage
    msgs = []
    for i, m in enumerate(messages):
        msgs.append(ParsedMessage(
            message_id=m["message_id"] or str(i), role=m["role"],
            content_text=m["content_text"], content_type=m["content_type"] or "text",
            model=m["model"], timestamp=m["timestamp"], seq=i,
        ))

    # Resolve destination dir
    if not destination_dir and target_tool != "hermes":
        destination_dir = _default_export_dir(target_tool, adapter)
        os.makedirs(destination_dir, exist_ok=True)

    try:
        if target_tool == "hermes":
            out_path = adapter.export_session(
                session_id=s["session_id"],
                title=s["title"] or s["session_id"],
                messages=msgs,
                destination_dir=destination_dir or "",
                cwd=s["project_path"],
                model=s["model"],
                started_at=s["started_at"],
            )
        else:
            out_path = adapter.export_session(
                session_id=s["session_id"],
                title=s["title"] or s["session_id"],
                messages=msgs,
                destination_dir=destination_dir,
            )
        _log_export(session_id, target_tool, out_path)
        return {"status": "ok", "path": out_path}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _default_export_dir(target_tool, adapter) -> str:
    base = adapter.data_path or os.path.expanduser("~")
    return os.path.join(base, "hub_exports")


def _log_export(session_id, target_tool, path):
    conn = get_conn()
    conn.execute(
        "INSERT INTO export_log (session_fk, target_tool, status, destination) "
        "VALUES (?,?,?,?)", (session_id, target_tool, "ok", path))
    conn.commit()
    conn.close()


def export_all_to_target(target_tool: str, destination_dir: str | None = None,
                         limit: int = 0) -> dict:
    """Bulk-export sessions to a target tool. Returns summary."""
    conn = get_conn()
    query = "SELECT id, tool FROM sessions WHERE tool != ? ORDER BY started_at DESC" if target_tool == "hermes" else "SELECT id, tool FROM sessions ORDER BY started_at DESC"
    args = (target_tool,) if target_tool == "hermes" else ()
    if limit:
        query += f" LIMIT {limit}"
    rows = conn.execute(query, args).fetchall()
    conn.close()

    ok = errors = 0
    paths = []
    for row in rows:
        res = export_session(row["id"], target_tool, destination_dir)
        if res["status"] == "ok":
            ok += 1
            paths.append(res["path"])
        else:
            errors += 1
            print(f"  [!] Error exporting {row['id']}: {res.get('error')}")
    return {"ok": ok, "errors": errors, "paths": paths}
