"""Exporter — writes any neutral session into another tool's native cache format.

Safety: exports ALWAYS write to a NEW file and back up any existing destination
as `.hub.bak` before writing. Source data is never touched.
"""

import os
import shutil
import sqlite3

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
    if not destination_dir:
        destination_dir = _default_export_dir(target_tool, adapter)
    os.makedirs(destination_dir, exist_ok=True)

    try:
        out_path = adapter.export_session(
            session_id=s["session_id"], title=s["title"] or s["session_id"],
            messages=msgs, destination_dir=destination_dir)
        _log_export(session_id, target_tool, out_path)
        return {"status": "ok", "path": out_path}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _default_export_dir(target_tool, adapter) -> str:
    """Choose a safe default export location under the tool's data dir,
    always in a dedicated 'hub_exports' subfolder so we never pollute the
    tool's real cache or risk overwriting live data."""
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
    rows = conn.execute(
        "SELECT id FROM sessions ORDER BY started_at DESC LIMIT ?",
        (limit,)).fetchall() if limit else conn.execute(
        "SELECT id FROM sessions ORDER BY started_at DESC").fetchall()
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
    return {"ok": ok, "errors": errors, "paths": paths}
