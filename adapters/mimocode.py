"""Mimocode adapter — parses ~/.local/share/mimocode/mimocode.db."""

import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Generator

from adapters.base import BaseAdapter, ParsedSession, ParsedMessage


class MimocodeAdapter(BaseAdapter):
    TOOL_NAME = "mimocode"
    DISPLAY_NAME = "Mimocode"

    def discover_sessions(self) -> Generator[ParsedSession, None, None]:
        for base in self.all_paths():
            db_path = os.path.join(base, "mimocode.db") if os.path.isdir(base) else base
            if not os.path.isfile(db_path):
                continue
            try:
                conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
                conn.row_factory = sqlite3.Row
                tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if "session" not in tables or "part" not in tables:
                    conn.close()
                    continue
                rows = conn.execute("SELECT * FROM session ORDER BY time_created").fetchall()
                stat = os.stat(db_path)
                for r in rows:
                    d = dict(r)
                    sid = d.get("id")
                    title = d.get("title") or d.get("slug")
                    started = datetime.fromtimestamp(d["time_created"] / 1000.0, tz=timezone.utc).isoformat() if d.get("time_created") else None
                    ended = datetime.fromtimestamp(d["time_updated"] / 1000.0, tz=timezone.utc).isoformat() if d.get("time_updated") else None
                    msg_cnt = conn.execute("SELECT count(*) FROM message WHERE session_id=?", (sid,)).fetchone()[0]
                    yield ParsedSession(
                        session_id=f"mimocode:{sid}",
                        title=title,
                        project_path=d.get("directory"),
                        model=d.get("model", "mimocode"),
                        status="completed",
                        started_at=started,
                        ended_at=ended,
                        message_count=msg_cnt,
                        input_tokens=d.get("tokens_input") or 0,
                        output_tokens=d.get("tokens_output") or 0,
                        reasoning_tokens=d.get("tokens_reasoning") or 0,
                        cache_read_tokens=d.get("tokens_cache_read") or 0,
                        cache_write_tokens=d.get("tokens_cache_write") or 0,
                        file_path=db_path,
                        file_size_bytes=stat.st_size,
                        file_mtime=stat.st_mtime,
                        raw_metadata={"db": db_path, "sid": sid},
                    )
                conn.close()
            except Exception:
                continue

    def parse_messages(self, session: ParsedSession) -> Generator[ParsedMessage, None, None]:
        db_path = session.file_path
        sid = (session.raw_metadata or {}).get("sid") or str(session.session_id).split("mimocode:", 1)[-1]
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            # Load messages to map message_id -> role
            msg_roles = {}
            for m in conn.execute("SELECT id, data FROM message WHERE session_id=?", (sid,)).fetchall():
                try:
                    d = json.loads(m["data"] or "{}")
                    msg_roles[m["id"]] = d.get("role", "user")
                except Exception:
                    msg_roles[m["id"]] = "user"

            parts = conn.execute("SELECT * FROM part WHERE session_id=? ORDER BY time_created, id", (sid,)).fetchall()
            seq = 0
            for p in parts:
                try:
                    d = json.loads(p["data"] or "{}")
                except Exception:
                    continue
                ptype = d.get("type")
                txt = d.get("text")
                if not txt:
                    continue
                role = msg_roles.get(p["message_id"], "user")
                if ptype == "reasoning":
                    role = "assistant"
                    txt = f"[Thinking]\n{txt}"
                seq += 1
                ts = datetime.fromtimestamp(p["time_created"] / 1000.0, tz=timezone.utc).isoformat() if p["time_created"] else None
                yield ParsedMessage(
                    message_id=p["id"],
                    role=role if role in ("user", "assistant", "system", "tool") else "user",
                    content_text=self._truncate(txt, 20_000),
                    content_type="text",
                    timestamp=ts,
                    seq=seq,
                )
            conn.close()
        except Exception:
            return
