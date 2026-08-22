"""Sync engine — orchestrates incremental import across all tool adapters."""

import json
import os
import sqlite3
from datetime import datetime, timezone

from config import DB_PATH, get_adapter, all_tool_names
from adapters.base import ParsedSession, ParsedMessage


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


class SyncEngine:
    """Runs incremental sync for all registered tools.

    For each tool: create its adapter, discover sessions, compare against the
    DB by composite id, and (re)parse messages for new or changed sessions.
    """

    def __init__(self, force_full: bool = False):
        self.force_full = force_full
        self.conn = get_conn()
        self.results = {}

    def run_all(self) -> dict:
        for tool_name in all_tool_names():
            try:
                self.results[tool_name] = self._sync_tool(tool_name)
            except Exception as e:  # never let one tool kill the run
                self.results[tool_name] = {
                    "status": "error", "error": str(e),
                    "found": 0, "new": 0, "updated": 0,
                }
                print(f"  [!] {tool_name}: ERROR - {e}")
        self.conn.close()
        return self.results

    def _sync_tool(self, tool_name: str) -> dict:
        started = datetime.now(timezone.utc).isoformat()
        log_id = self._start_sync_log(tool_name, started)
        adapter = get_adapter(tool_name)
        if adapter is None:
            self._finish_sync_log(log_id, "skipped", error="No adapter")
            return {"status": "skipped", "found": 0, "new": 0, "updated": 0}
        print(f"  [*] {tool_name}: discovering sessions...")

        if not adapter.is_available():
            self._finish_sync_log(log_id, "unavailable", error="Data path not accessible")
            print(f"  [-] {tool_name}: data path not available")
            return {"status": "unavailable", "found": 0, "new": 0, "updated": 0}

        found = new = updated = errors = 0
        try:
            for session in adapter.discover_sessions():
                found += 1
                action = self._should_sync(session.id if hasattr(session, 'id') else
                                           f"{tool_name}:{session.session_id}", session)
                if action == "skip":
                    continue
                try:
                    messages = list(adapter.parse_messages(session))
                    self._upsert_session(tool_name, session, len(messages))
                    self.conn.execute(
                        "DELETE FROM messages WHERE session_fk = ?",
                        (self._composite(tool_name, session),),
                    )
                    self._insert_messages(tool_name, session, messages)
                    self.conn.commit()
                    new += (1 if action == "new" else 0)
                    updated += (0 if action == "new" else 1)
                except Exception as e:
                    errors += 1
                    print(f"    [!] Error syncing {session.session_id}: {e}")
                    continue
        except Exception as e:
            self._finish_sync_log(log_id, "error", error=str(e))
            return {"status": "error", "error": str(e), "found": found,
                    "new": new, "updated": updated}

        self._update_tool_stats(tool_name)
        status = "ok" if errors == 0 else f"ok ({errors} errors)"
        self._finish_sync_log(log_id, status, sessions_found=found,
                              sessions_new=new, sessions_updated=updated)
        print(f"  [+] {tool_name}: found={found} new={new} updated={updated}")
        return {"status": status, "found": found, "new": new, "updated": updated}

    # --- Helpers -------------------------------------------------------------
    def _composite(self, tool_name, session) -> str:
        return f"{tool_name}:{session.session_id}"

    def _should_sync(self, composite_id: str, session) -> str:
        if self.force_full:
            return "update" if self._session_exists(composite_id) else "new"
        row = self.conn.execute(
            "SELECT file_size_bytes, file_mtime FROM sessions WHERE id = ?",
            (composite_id,),
        ).fetchone()
        if row is None:
            return "new"
        if (row["file_size_bytes"] != session.file_size_bytes or
                row["file_mtime"] != session.file_mtime):
            return "update"
        return "skip"

    def _session_exists(self, composite_id: str) -> bool:
        return self.conn.execute(
            "SELECT 1 FROM sessions WHERE id = ?", (composite_id,)
        ).fetchone() is not None

    def _upsert_session(self, tool_name, session, msg_count: int):
        cid = self._composite(tool_name, session)
        raw_meta = json.dumps(session.raw_metadata) if session.raw_metadata else None
        now = datetime.now(timezone.utc).isoformat()
        if self._session_exists(cid):
            self.conn.execute("""
                UPDATE sessions SET title=?, project_path=?, model=?, status=?,
                    started_at=?, ended_at=?, message_count=?, file_path=?,
                    file_size_bytes=?, file_mtime=?, raw_metadata=?,
                    input_tokens=?, output_tokens=?, cache_read_tokens=?,
                    cache_write_tokens=?, reasoning_tokens=?, api_call_count=?,
                    last_synced_at=?
                WHERE id=?
            """, (session.title, session.project_path, session.model, session.status,
                  session.started_at, session.ended_at, msg_count, session.file_path,
                  session.file_size_bytes, session.file_mtime, raw_meta,
                  session.input_tokens, session.output_tokens, session.cache_read_tokens,
                  session.cache_write_tokens, session.reasoning_tokens, session.api_call_count,
                  now, cid))
        else:
            self.conn.execute("""
                INSERT INTO sessions (id, tool, session_id, title, project_path, model,
                    status, started_at, ended_at, message_count, file_path,
                    file_size_bytes, file_mtime, raw_metadata,
                    input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
                    reasoning_tokens, api_call_count, first_synced_at, last_synced_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (cid, tool_name, session.session_id, session.title, session.project_path,
                  session.model, session.status, session.started_at, session.ended_at,
                  msg_count, session.file_path, session.file_size_bytes, session.file_mtime,
                  raw_meta, session.input_tokens, session.output_tokens,
                  session.cache_read_tokens, session.cache_write_tokens,
                  session.reasoning_tokens, session.api_call_count, now, now))

    def _insert_messages(self, tool_name, session, messages):
        cid = self._composite(tool_name, session)
        for msg in messages:
            raw_json = json.dumps(msg.raw_json) if msg.raw_json else None
            self.conn.execute("""
                INSERT INTO messages (session_fk, message_id, role, content_text,
                    content_type, model, timestamp, token_input, token_output,
                    raw_json, parent_id, seq)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, (cid, msg.message_id, msg.role, msg.content_text, msg.content_type,
                  msg.model, msg.timestamp, msg.token_input, msg.token_output,
                  raw_json, msg.parent_id, msg.seq))

    def _start_sync_log(self, tool_name, started) -> int:
        cur = self.conn.execute(
            "INSERT INTO sync_log (tool, sync_started_at, status) VALUES (?,?,'running')",
            (tool_name, started))
        self.conn.commit()
        return cur.lastrowid

    def _finish_sync_log(self, log_id, status, sessions_found=0,
                         sessions_new=0, sessions_updated=0, error=None):
        self.conn.execute("""
            UPDATE sync_log SET sync_ended_at=?, status=?, sessions_found=?,
                sessions_new=?, sessions_updated=?, error_message=?
            WHERE id=?
        """, (datetime.now(timezone.utc).isoformat(), status, sessions_found,
              sessions_new, sessions_updated, error, log_id))
        self.conn.commit()

    def _update_tool_stats(self, tool_name):
        row = self.conn.execute(
            "SELECT COUNT(*) c, COALESCE(SUM(file_size_bytes),0) s FROM sessions WHERE tool=?",
            (tool_name,)).fetchone()
        self.conn.execute(
            "UPDATE tools SET last_sync_at=?, session_count=?, total_size_mb=? WHERE name=?",
            (datetime.now(timezone.utc).isoformat(), row["c"], round(row["s"] / 1048576, 2),
             tool_name))
        self.conn.commit()
