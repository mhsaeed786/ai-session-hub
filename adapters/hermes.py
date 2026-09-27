"""Hermes adapter.

Imports sessions from a Hermes state.db (SQLite) in READ-ONLY mode.
Exports sessions directly into Hermes state.db (SQLite) so they appear and function
natively in Hermes Desktop and CLI.
"""

import json
import os
import re
import sqlite3
import time
from datetime import datetime, timezone
from typing import Generator, List, Optional

from adapters.base import BaseAdapter, ParsedSession, ParsedMessage

HERMES_STATE_DB = os.path.join(os.path.expanduser("~"), "AppData", "Local", "hermes", "state.db")


def clean_title(title: Optional[str], default: str = "Migrated Session") -> str:
    """Produce a concise, human-readable title without JSON or raw prompt noise."""
    if not title:
        return default
    t = str(title).strip()
    # Strip any previous wrapper prefixes
    for prefix in ("Imported from Claude Code:", "Imported from Codex:", "Imported from:", "Antigravity note:"):
        if t.startswith(prefix):
            t = t[len(prefix):].strip()

    # Check if raw JSON
    if t.startswith("{") or t.startswith("["):
        try:
            d = json.loads(t)
            if isinstance(d, dict):
                t = d.get("text") or d.get("content") or d.get("summary") or d.get("title") or ""
        except Exception:
            pass

    # Strip XML tags like <USER_REQUEST>, <turn_context>, etc.
    t = re.sub(r"<[^>]+>", "", t).strip()

    # If first turn is a markdown header, grab the title
    if t.startswith("#"):
        t = t.lstrip("#").strip()

    # Collapse multiple whitespaces
    t = " ".join(t.split())

    # Cut off at first sentence if too long
    for sep in ("\n", ". ", "? ", "! "):
        idx = t.find(sep)
        if 15 < idx < 80:
            t = t[:idx]
            break

    if len(t) > 75:
        t = t[:72] + "..."

    return t if t else default


def parse_timestamp_to_epoch(ts) -> float:
    """Normalize any timestamp (ISO string, epoch ms, epoch sec) to epoch seconds."""
    if not ts:
        return time.time()
    if isinstance(ts, (int, float)):
        if ts > 1e11:  # milliseconds
            return float(ts) / 1000.0
        return float(ts)
    if isinstance(ts, str):
        ts = ts.strip()
        try:
            return float(ts)
        except ValueError:
            pass
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return dt.timestamp()
        except Exception:
            pass
        # Common formats
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(ts, fmt)
                return dt.replace(tzinfo=timezone.utc).timestamp()
            except Exception:
                continue
    return time.time()


class HermesAdapter(BaseAdapter):
    TOOL_NAME = "hermes"
    DISPLAY_NAME = "Hermes"

    def _find_state_dbs(self):
        """Locate candidate state.db files across all configured paths."""
        found = []
        for base in self.all_paths():
            if not os.path.isdir(base):
                continue
            candidate = os.path.join(base, "state.db")
            if os.path.isfile(candidate):
                found.append(candidate)
            for sub in ("hermes-wsl", "hermes", "_wsl_cache"):
                sub_candidate = os.path.join(base, sub, "state.db")
                if os.path.isfile(sub_candidate):
                    found.append(sub_candidate)
        seen, out = set(), []
        for p in found:
            norm = os.path.normpath(p)
            if norm not in seen:
                seen.add(norm)
                out.append(p)
        return out

    def _open_ro(self, db_path):
        return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)

    def discover_sessions(self) -> Generator[ParsedSession, None, None]:
        for db_path in self._find_state_dbs():
            try:
                conn = self._open_ro(db_path)
            except Exception:
                continue
            try:
                tables = {r[0] for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'")}
                if "sessions" not in tables:
                    continue
                cols_row = conn.execute("PRAGMA table_info(sessions)").fetchall()
                cols = {c[1] for c in cols_row}
                select_parts = ["id", "title", "model", "started_at", "ended_at", "message_count"]
                if "cwd" in cols:
                    select_parts.insert(2, "cwd")
                for token_col in ("input_tokens", "output_tokens", "cache_read_tokens",
                                  "cache_write_tokens", "reasoning_tokens", "api_call_count"):
                    if token_col in cols:
                        select_parts.append(token_col)
                if "session_key" in cols:
                    select_parts.append("session_key")
                rows = conn.execute(f"SELECT {', '.join(select_parts)} FROM sessions").fetchall()
                for row in rows:
                    r = dict(zip(select_parts, row))
                    sid = str(r["id"])
                    yield ParsedSession(
                        session_id=f"hermes:{sid}",
                        title=r.get("title") or None,
                        project_path=r.get("cwd"),
                        model=r.get("model"),
                        status="completed",
                        started_at=str(r.get("started_at")),
                        ended_at=str(r.get("ended_at")),
                        message_count=r.get("message_count") or 0,
                        input_tokens=r.get("input_tokens") or 0,
                        output_tokens=r.get("output_tokens") or 0,
                        cache_read_tokens=r.get("cache_read_tokens") or 0,
                        cache_write_tokens=r.get("cache_write_tokens") or 0,
                        reasoning_tokens=r.get("reasoning_tokens") or 0,
                        api_call_count=r.get("api_call_count") or 0,
                        file_path=db_path,
                        file_size_bytes=os.path.getsize(db_path),
                        file_mtime=os.path.getmtime(db_path),
                        raw_metadata={"db": db_path, "sid": sid},
                    )
            finally:
                conn.close()

    def parse_messages(self, session: ParsedSession) -> Generator[ParsedMessage, None, None]:
        db_path = session.file_path
        sid = (session.raw_metadata or {}).get("sid") or str(session.session_id).split("hermes:", 1)[-1]
        try:
            conn = self._open_ro(db_path)
        except Exception:
            return
        try:
            tables = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            if "messages" not in tables:
                return
            try:
                rows = conn.execute(
                    "SELECT id, role, content, timestamp, tool_name, reasoning "
                    "FROM messages WHERE session_id=? ORDER BY id", (sid,)
                ).fetchall()
            except sqlite3.OperationalError:
                rows = conn.execute(
                    "SELECT id, role, content, timestamp FROM messages "
                    "WHERE session_id=? ORDER BY id", (sid,)
                ).fetchall()
            seq = 0
            for row in rows:
                role = str(row[1] or "user")
                content = row[2] or ""
                seq += 1
                norm_role = role if role in ("user", "assistant", "system", "tool") else "assistant"
                yield ParsedMessage(
                    message_id=str(row[0]),
                    role=norm_role,
                    content_text=self._truncate(str(content), 20_000),
                    content_type="text",
                    timestamp=str(row[3]) if len(row) > 3 else None,
                    raw_json={"tool_name": row[4] if len(row) > 4 else None,
                              "reasoning": row[5] if len(row) > 5 else None},
                    seq=seq,
                )
        finally:
            conn.close()

    def export_session(self, session_id: str, title: str, messages: list,
                       destination_dir: str = "", target_db_path: str = HERMES_STATE_DB,
                       cwd: Optional[str] = None, model: Optional[str] = None,
                       started_at: Optional[float] = None) -> str:
        """Write a session directly into Hermes state.db (SQLite)."""
        if not os.path.isfile(target_db_path):
            raise FileNotFoundError(f"Hermes database not found at {target_db_path}")

        # Derive a clean unique Hermes session ID
        clean_sid = re.sub(r"[^A-Za-z0-9_-]", "_", session_id)
        if not clean_sid.startswith("migrated_"):
            clean_sid = f"migrated_{clean_sid}"

        # Timestamps
        t_start = parse_timestamp_to_epoch(started_at)
        t_end = t_start + max(1.0, len(messages) * 2.0)

        conn = sqlite3.connect(target_db_path, timeout=30.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL")

            # Clean title and resolve any collisions for idx_sessions_title_unique
            base_title = clean_title(title, default=f"Session {clean_sid}")
            final_title = base_title
            attempt = 1
            while True:
                colliding = conn.execute(
                    "SELECT id FROM sessions WHERE title=? AND id!=?", (final_title, clean_sid)
                ).fetchone()
                if not colliding:
                    break
                attempt += 1
                suffix = f" ({clean_sid[-6:]})" if attempt == 2 else f" ({clean_sid[-6:]}-{attempt})"
                final_title = f"{base_title[:60]}{suffix}"

            # Check if session already exists
            existing = conn.execute("SELECT id FROM sessions WHERE id=?", (clean_sid,)).fetchone()
            if existing:
                # Update title and message count
                conn.execute(
                    "UPDATE sessions SET title=?, message_count=? WHERE id=?",
                    (final_title, len(messages), clean_sid)
                )
            else:
                conn.execute("""
                    INSERT INTO sessions (
                        id, source, model, cwd, started_at, ended_at, message_count,
                        tool_call_count, input_tokens, output_tokens, cache_read_tokens,
                        cache_write_tokens, reasoning_tokens, api_call_count, title,
                        profile_name, pinned, archived, hidden
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0, 0, 0, ?, 'default', 0, 0, 0)
                """, (clean_sid, "migrated", model or "migrated-agent",
                      cwd or "C:\\Users\\LOQ", t_start, t_end, len(messages), final_title))

            # Delete any existing messages for this session
            conn.execute("DELETE FROM messages WHERE session_id=?", (clean_sid,))

            # Insert messages
            curr_time = t_start
            for m in messages:
                role = getattr(m, "role", "user")
                content = getattr(m, "content_text", "") or ""
                m_ts = parse_timestamp_to_epoch(getattr(m, "timestamp", None))
                if not m_ts or m_ts < 1000:
                    curr_time += 1.0
                    m_ts = curr_time
                conn.execute("""
                    INSERT INTO messages (
                        session_id, role, content, timestamp, active, observed, compacted
                    ) VALUES (?, ?, ?, ?, 1, 0, 0)
                """, (clean_sid, role, content, m_ts))

            conn.commit()
            return clean_sid
        finally:
            conn.close()
