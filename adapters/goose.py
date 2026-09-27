"""Goose adapter — parses both Goose SQLite database and chat export JSON files."""

import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Generator

from adapters.base import BaseAdapter, ParsedSession, ParsedMessage


class GooseAdapter(BaseAdapter):
    TOOL_NAME = "goose"
    DISPLAY_NAME = "Goose"

    def _find_sqlite_dbs(self):
        found = []
        for base in self.all_paths():
            candidate = os.path.join(base, "sessions.db") if os.path.isdir(base) else base
            if os.path.isfile(candidate):
                found.append(candidate)
        return found

    def _find_export_files(self):
        for base in self.all_paths():
            if not os.path.isdir(base):
                continue
            for root, _dirs, files in os.walk(base):
                lowered = root.lower()
                if any(x in lowered for x in ("node_modules", "\\cache", "code cache", "local storage", "\\logs")):
                    continue
                for fname in files:
                    if not fname.endswith(".json"):
                        continue
                    yield os.path.join(root, fname)

    def discover_sessions(self) -> Generator[ParsedSession, None, None]:
        seen = set()

        # 1. Discover from SQLite DBs (Live Goose)
        for db_path in self._find_sqlite_dbs():
            try:
                conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
                conn.row_factory = sqlite3.Row
                tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if "sessions" not in tables:
                    conn.close()
                    continue
                sessions = conn.execute("SELECT * FROM sessions ORDER BY created_at").fetchall()
                stat = os.stat(db_path)
                for s in sessions:
                    sid = str(s["id"])
                    key = f"goose:sqlite:{sid}"
                    if key in seen:
                        continue
                    seen.add(key)
                    msg_cnt = conn.execute("SELECT count(*) FROM messages WHERE session_id=?", (s["id"],)).fetchone()[0]
                    yield ParsedSession(
                        session_id=key,
                        title=s["name"] or f"Goose Session {sid}",
                        project_path=s["working_dir"],
                        model=None,
                        status="completed",
                        started_at=s["created_at"],
                        ended_at=s["updated_at"],
                        message_count=msg_cnt,
                        file_path=db_path,
                        file_size_bytes=stat.st_size,
                        file_mtime=stat.st_mtime,
                        raw_metadata={"type": "sqlite", "sid": s["id"], "db": db_path},
                    )
                conn.close()
            except Exception:
                continue

        # 2. Discover from JSON exports
        for fpath in self._find_export_files():
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    data = json.load(f)
            except Exception:
                continue
            if not isinstance(data, dict) or not isinstance(data.get("conversation"), list):
                continue
            sid = data.get("id") or os.path.basename(fpath).replace(".json", "")
            key = f"goose:json:{sid}"
            if key in seen:
                continue
            seen.add(key)
            stat = os.stat(fpath)
            yield ParsedSession(
                session_id=key,
                title=data.get("name") or os.path.basename(fpath).replace(".json", ""),
                project_path=data.get("working_dir"),
                model=(data.get("model_config") or {}).get("model") if isinstance(data.get("model_config"), dict) else None,
                status="completed",
                started_at=data.get("created_at"),
                ended_at=data.get("updated_at"),
                message_count=len(data.get("conversation", [])),
                file_path=fpath,
                file_size_bytes=stat.st_size,
                file_mtime=stat.st_mtime,
                raw_metadata={"type": "json", "provider": data.get("provider_name")},
            )

    def parse_messages(self, session: ParsedSession) -> Generator[ParsedMessage, None, None]:
        mtype = (session.raw_metadata or {}).get("type")
        if mtype == "sqlite":
            db_path = session.file_path
            sid = session.raw_metadata.get("sid")
            try:
                conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
                conn.row_factory = sqlite3.Row
                msgs = conn.execute("SELECT * FROM messages WHERE session_id=? ORDER BY created_timestamp, id", (sid,)).fetchall()
                seq = 0
                for m in msgs:
                    raw = m["content_json"] or ""
                    try:
                        blocks = json.loads(raw)
                    except Exception:
                        blocks = raw
                    texts = []
                    if isinstance(blocks, list):
                        for b in blocks:
                            if isinstance(b, dict):
                                if b.get("type") == "text":
                                    texts.append(b.get("text", ""))
                                elif b.get("type") == "thinking":
                                    texts.append(f"[Thinking]\n{b.get('thinking', '')}")
                                elif b.get("type") == "toolRequest":
                                    texts.append(f"[Tool Request: {b.get('id')}]")
                                elif b.get("type") == "toolResponse":
                                    texts.append("[Tool Response]")
                            elif isinstance(b, str):
                                texts.append(b)
                    elif isinstance(blocks, str):
                        texts.append(blocks)
                    txt = "\n".join(t for t in texts if t).strip()
                    if not txt:
                        continue
                    seq += 1
                    role = m["role"] if m["role"] in ("user", "assistant", "system", "tool") else "user"
                    ts = m["created_timestamp"]
                    yield ParsedMessage(
                        message_id=str(m["id"]),
                        role=role,
                        content_text=self._truncate(txt, 20_000),
                        content_type="text",
                        timestamp=str(ts) if ts else None,
                        seq=seq,
                    )
                conn.close()
            except Exception:
                return
        else:
            try:
                with open(session.file_path, "r", encoding="utf-8", errors="replace") as f:
                    data = json.load(f)
            except Exception:
                return
            conv = data.get("conversation", [])
            seq = 0
            for item in conv:
                if not isinstance(item, dict):
                    continue
                role = item.get("role", "user")
                if role == "assistant" and item.get("tool_name"):
                    role = "tool"
                content_blocks = item.get("content", [])
                texts = []
                if isinstance(content_blocks, str):
                    texts.append(content_blocks)
                elif isinstance(content_blocks, list):
                    for block in content_blocks:
                        if isinstance(block, dict):
                            if block.get("type") == "text":
                                texts.append(block.get("text", ""))
                            elif block.get("type") == "thinking":
                                texts.append(f"[Thinking]\n{block.get('thinking', '')}")
                            elif block.get("type") == "tool_result":
                                for i in block.get("content", []):
                                    if isinstance(i, dict) and i.get("type") == "text":
                                        texts.append(i.get("text", ""))
                content = "\n".join(texts).strip()
                if not content:
                    continue
                seq += 1
                ts = item.get("created")
                if isinstance(ts, (int, float)):
                    try:
                        ts = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
                    except Exception:
                        ts = None
                yield ParsedMessage(
                    message_id=str(item.get("id", seq)),
                    role=role if role in ("user", "assistant", "tool", "system") else "user",
                    content_text=self._truncate(content, 20_000),
                    content_type="text",
                    model=item.get("model"),
                    timestamp=ts,
                    seq=seq,
                )
