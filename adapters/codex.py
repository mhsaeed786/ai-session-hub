"""Codex CLI adapter — parses ~/.codex/sessions/ JSONL rollout files and state_5.sqlite."""

import json
import os
import sqlite3
from typing import Generator

from adapters.base import BaseAdapter, ParsedSession, ParsedMessage


class CodexAdapter(BaseAdapter):
    TOOL_NAME = "codex"
    DISPLAY_NAME = "Codex CLI"

    def _load_sqlite_meta(self) -> dict:
        meta = {}
        for base in self.all_paths():
            db_path = os.path.join(base, "state_5.sqlite") if os.path.isdir(base) else base
            if os.path.isfile(db_path):
                try:
                    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
                    conn.row_factory = sqlite3.Row
                    for r in conn.execute("SELECT * FROM threads"):
                        tid = r["id"]
                        meta[tid] = {
                            "title": (r["title"] or "").strip(),
                            "model": r["model"],
                            "cwd": r["cwd"],
                            "created_at": r["created_at"],
                            "updated_at": r["updated_at"],
                        }
                    conn.close()
                except Exception:
                    pass
        return meta

    def discover_sessions(self) -> Generator[ParsedSession, None, None]:
        seen = set()
        sqlite_meta = self._load_sqlite_meta()

        for base in self.all_paths():
            if not os.path.isdir(base):
                continue
            for root, _dirs, files in os.walk(base):
                for fname in files:
                    if not (fname.startswith("rollout-") and fname.endswith(".jsonl")):
                        continue
                    if ".migrated." in fname:
                        continue
                    fpath = os.path.join(root, fname)
                    stat = os.stat(fpath)
                    # Extract session UUID from filename
                    parts = fname.replace(".jsonl", "").split("-")
                    sid = "-".join(parts[-5:]) if len(parts) >= 5 else fname.replace("rollout-", "").replace(".jsonl", "")
                    if sid in seen:
                        continue
                    seen.add(sid)
                    smeta = sqlite_meta.get(sid, {})
                    title = smeta.get("title")
                    if title and len(title) > 60:
                        title = title[:57] + "..."
                    yield ParsedSession(
                        session_id=f"codex:{sid}",
                        title=title,
                        project_path=smeta.get("cwd"),
                        model=smeta.get("model"),
                        status="completed",
                        started_at=str(smeta.get("created_at")) if smeta.get("created_at") else None,
                        ended_at=str(smeta.get("updated_at")) if smeta.get("updated_at") else None,
                        file_path=fpath,
                        file_size_bytes=stat.st_size,
                        file_mtime=stat.st_mtime,
                        raw_metadata={"sid": sid},
                    )

    def parse_messages(self, session: ParsedSession) -> Generator[ParsedMessage, None, None]:
        seq = 0
        first_user_extracted = bool(session.title)
        for raw in self._safe_read_jsonl(session.file_path):
            msg_type = raw.get("type", "")
            if msg_type == "session_meta":
                payload = raw.get("payload", {})
                if not session.project_path:
                    session.project_path = payload.get("cwd")
                if not session.model:
                    session.model = payload.get("model_provider")
                if not session.started_at:
                    session.started_at = raw.get("timestamp") or payload.get("timestamp")
            elif msg_type == "response_item":
                payload = raw.get("payload", {})
                ptype = payload.get("type")
                role = payload.get("role", "unknown")
                content_blocks = payload.get("content") or []
                if isinstance(content_blocks, str):
                    content_blocks = [{"type": "text", "text": content_blocks}]
                if not isinstance(content_blocks, list):
                    content_blocks = []
                for block in content_blocks:
                    if not isinstance(block, dict):
                        continue
                    text = block.get("text", "")
                    if not text:
                        continue
                    if not first_user_extracted and role == "user":
                        session.title = self._truncate(text, 100)
                        first_user_extracted = True
                    seq += 1
                    norm_role = role if role in ("user", "assistant", "system", "tool") else "assistant"
                    yield ParsedMessage(
                        message_id=payload.get("id", str(seq)),
                        role=norm_role,
                        content_text=self._truncate(text, 20_000),
                        content_type=block.get("type", "text"),
                        model=session.model,
                        timestamp=raw.get("timestamp"),
                        seq=seq,
                    )
