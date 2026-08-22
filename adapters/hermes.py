"""Hermes adapter.

Imports sessions from a Hermes state.db (SQLite) in READ-ONLY mode. The live
database is never modified. Exports write a portable markdown transcript.
"""

import os
import sqlite3
from typing import Generator

from adapters.base import BaseAdapter, ParsedSession, ParsedMessage


class HermesAdapter(BaseAdapter):
    TOOL_NAME = "hermes"
    DISPLAY_NAME = "Hermes"

    def _find_state_dbs(self):
        """Locate candidate state.db files across all configured paths."""
        found = []
        for base in self.all_paths():
            if not os.path.isdir(base):
                continue
            # Primary: <base>/state.db (Hermes home layout)
            candidate = os.path.join(base, "state.db")
            if os.path.isfile(candidate):
                found.append(candidate)
            # WSL-export layout: <base>/hermes-wsl/state.db
            for sub in ("hermes-wsl", "hermes", "_wsl_cache"):
                sub_candidate = os.path.join(base, sub, "state.db")
                if os.path.isfile(sub_candidate):
                    found.append(sub_candidate)
        # De-duplicate preserving order
        seen, out = set(), []
        for p in found:
            norm = os.path.normpath(p)
            if norm not in seen:
                seen.add(norm)
                out.append(p)
        return out

    def _open_ro(self, db_path):
        """Open a SQLite DB read-only using the URI trick. Never writes."""
        return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)

    def discover_sessions(self) -> Generator[ParsedSession, None, None]:
        for db_path in self._find_state_dbs():
            try:
                conn = self._open_ro(db_path)
            except Exception:
                continue
            try:
                # Validate schema has the tables we need
                tables = {r[0] for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'")}
                if "sessions" not in tables:
                    continue
                # Introspect columns so the adapter works across schema versions
                # (e.g. the older hermes-wsl backup lacks `cwd`).
                cols_row = conn.execute("PRAGMA table_info(sessions)").fetchall()
                cols = {c[1] for c in cols_row}
                select_parts = ["id", "title", "model", "started_at", "ended_at",
                                 "message_count"]
                if "cwd" in cols:
                    select_parts.insert(2, "cwd")
                for token_col in ("input_tokens", "output_tokens", "cache_read_tokens",
                                  "cache_write_tokens", "reasoning_tokens", "api_call_count"):
                    if token_col in cols:
                        select_parts.append(token_col)
                if "session_key" in cols:
                    select_parts.append("session_key")
                if "chat_id" in cols:
                    select_parts.append("chat_id")
                if "chat_type" in cols:
                    select_parts.append("chat_type")
                rows = conn.execute(
                    f"SELECT {', '.join(select_parts)} FROM sessions"
                ).fetchall()
                for row in rows:
                    # Build a name->value map so we don't depend on column order
                    r = dict(zip(select_parts, row))
                    sid = str(r["id"])
                    yield ParsedSession(
                        session_id=f"hermes:{sid}",
                        title=r.get("title") or None,
                        project_path=r.get("cwd"),
                        model=r.get("model"),
                        status="completed",
                        started_at=r.get("started_at"),
                        ended_at=r.get("ended_at"),
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
        sid = (session.raw_metadata or {}).get("sid") or \
            str(session.session_id).split("hermes:", 1)[-1]
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
                # tool / system roles map cleanly for the hub
                norm_role = role
                if role not in ("user", "assistant", "system", "tool"):
                    norm_role = "assistant"
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
