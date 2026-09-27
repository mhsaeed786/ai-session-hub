"""Gemini Antigravity adapter — parses brain/*/.system_generated/logs/transcript.jsonl
and links with conversation_summaries.db.
"""

import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from typing import Generator

from adapters.base import BaseAdapter, ParsedSession, ParsedMessage


class GeminiAntigravityAdapter(BaseAdapter):
    TOOL_NAME = "gemini_antigravity"
    DISPLAY_NAME = "Gemini Antigravity"

    def _load_summaries(self, base: str) -> dict:
        sum_db = os.path.join(base, "conversation_summaries.db")
        summaries = {}
        if os.path.isfile(sum_db):
            try:
                conn = sqlite3.connect(f"file:{sum_db}?mode=ro", uri=True)
                conn.row_factory = sqlite3.Row
                for r in conn.execute("SELECT * FROM conversation_summaries"):
                    cid = r["conversation_id"]
                    summaries[cid] = {
                        "title": (r["title"] or "").strip(),
                        "preview": (r["preview"] or "").strip(),
                        "step_count": r["step_count"] or 0,
                        "workspace": (r["workspace_uris"] or "").strip(),
                        "status": r["status"] or "completed",
                        "mtime": r["last_modified_time"] or 0.0,
                    }
                conn.close()
            except Exception:
                pass
        return summaries

    def discover_sessions(self) -> Generator[ParsedSession, None, None]:
        seen = set()
        for base in self.all_paths():
            if not os.path.isdir(base):
                continue
            summaries = self._load_summaries(base)
            brain_dir = os.path.join(base, "brain")
            if os.path.isdir(brain_dir):
                for cid in os.listdir(brain_dir):
                    tpath = os.path.join(brain_dir, cid, ".system_generated", "logs", "transcript.jsonl")
                    if not os.path.isfile(tpath):
                        continue
                    if cid in seen:
                        continue
                    seen.add(cid)
                    meta = summaries.get(cid, {})
                    stat = os.stat(tpath)
                    title = meta.get("title")
                    preview = meta.get("preview")
                    if not title and preview:
                        title = preview[:60] + "..." if len(preview) > 60 else preview
                    if not title:
                        title = f"Antigravity Session {cid[:8]}"
                    started = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
                    yield ParsedSession(
                        session_id=f"gemini_ag:{cid}",
                        title=title,
                        project_path=meta.get("workspace"),
                        model="gemini",
                        status=meta.get("status", "completed"),
                        started_at=started,
                        ended_at=started,
                        file_path=tpath,
                        file_size_bytes=stat.st_size,
                        file_mtime=stat.st_mtime,
                        raw_metadata={"conversation_id": cid, "format": "transcript_jsonl"},
                    )

            # Also check conversations *.db if any lack a transcript
            conv_dir = os.path.join(base, "conversations")
            if os.path.isdir(conv_dir):
                for fname in os.listdir(conv_dir):
                    if not fname.endswith(".db"):
                        continue
                    cid = fname[:-3]
                    if cid in seen:
                        continue
                    seen.add(cid)
                    meta = summaries.get(cid, {})
                    fpath = os.path.join(conv_dir, fname)
                    stat = os.stat(fpath)
                    title = meta.get("title") or meta.get("preview") or f"Antigravity DB {cid[:8]}"
                    yield ParsedSession(
                        session_id=f"gemini_ag:{cid}",
                        title=title,
                        project_path=meta.get("workspace"),
                        model="gemini",
                        status=meta.get("status", "completed"),
                        started_at=None,
                        ended_at=None,
                        file_path=fpath,
                        file_size_bytes=stat.st_size,
                        file_mtime=stat.st_mtime,
                        raw_metadata={"conversation_id": cid, "format": "sqlite_db"},
                    )

    def parse_messages(self, session: ParsedSession) -> Generator[ParsedMessage, None, None]:
        fmt = (session.raw_metadata or {}).get("format")
        if fmt == "transcript_jsonl":
            seq = 0
            for raw in self._safe_read_jsonl(session.file_path):
                stype = raw.get("type")
                content = raw.get("content")
                thinking = raw.get("thinking")
                txt = ""
                role = "user"
                if stype == "USER_INPUT" and content:
                    txt = re.sub(r"<[^>]+>", "", str(content)).strip()
                    role = "user"
                elif stype == "PLANNER_RESPONSE":
                    role = "assistant"
                    if content:
                        txt = re.sub(r"<[^>]+>", "", str(content)).strip()
                    elif thinking:
                        txt = f"[Thinking]\n{thinking[:2000]}"
                elif stype == "GENERIC" and content:
                    role = "tool"
                    txt = str(content)[:5000]

                if not txt:
                    continue
                seq += 1
                yield ParsedMessage(
                    message_id=str(raw.get("step_index", seq)),
                    role=role,
                    content_text=self._truncate(txt, 20_000),
                    content_type="text",
                    model="gemini",
                    timestamp=raw.get("created_at"),
                    seq=seq,
                )
        elif fmt == "sqlite_db":
            try:
                conn = sqlite3.connect(f"file:{session.file_path}?mode=ro", uri=True)
                conn.row_factory = sqlite3.Row
                rows = conn.execute("SELECT * FROM steps ORDER BY idx").fetchall()
                seq = 0
                for r in rows:
                    stype = r["step_type"]
                    payload = r["step_payload"] or ""
                    role = "user" if "user" in stype.lower() else "assistant"
                    txt = str(payload)[:5000].strip()
                    if txt:
                        seq += 1
                        yield ParsedMessage(
                            message_id=str(r["idx"]),
                            role=role,
                            content_text=self._truncate(txt, 20_000),
                            content_type="text",
                            model="gemini",
                            seq=seq,
                        )
                conn.close()
            except Exception:
                return
