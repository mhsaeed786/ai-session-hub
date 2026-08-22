"""Codex CLI adapter — parses ~/.codex/sessions/ JSONL rollout files."""

import json
import os
from typing import Generator

from adapters.base import BaseAdapter, ParsedSession, ParsedMessage


class CodexAdapter(BaseAdapter):
    TOOL_NAME = "codex"
    DISPLAY_NAME = "Codex CLI"

    def discover_sessions(self) -> Generator[ParsedSession, None, None]:
        for base in self.all_paths():
            sessions_dir = os.path.join(base, "sessions")
            if not os.path.isdir(sessions_dir):
                continue
            for root, _dirs, files in os.walk(sessions_dir):
                for fname in files:
                    if not fname.startswith("rollout-") or not fname.endswith(".jsonl"):
                        continue
                    # Skip *.migrated.* duplicates
                    if ".migrated." in fname:
                        continue
                    fpath = os.path.join(root, fname)
                    stat = os.stat(fpath)
                    session_id = fname.replace("rollout-", "").replace(".jsonl", "")
                    yield ParsedSession(
                        session_id=f"codex:{session_id}",
                        title=None, project_path=None, model=None,
                        status="completed", started_at=None, ended_at=None,
                        file_path=fpath, file_size_bytes=stat.st_size,
                        file_mtime=stat.st_mtime, raw_metadata=None,
                    )

    def parse_messages(self, session: ParsedSession) -> Generator[ParsedMessage, None, None]:
        seq = 0
        first_user_extracted = False
        for raw in self._safe_read_jsonl(session.file_path):
            msg_type = raw.get("type", "")
            if msg_type == "session_meta":
                payload = raw.get("payload", {})
                session.project_path = payload.get("cwd")
                session.model = payload.get("model_provider")
                session.started_at = raw.get("timestamp") or payload.get("timestamp")
                session.raw_metadata = {
                    "cli_version": payload.get("cli_version"),
                    "source": payload.get("source"),
                    "originator": payload.get("originator"),
                }
            elif msg_type == "response_item":
                payload = raw.get("payload", {})
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
                        session.title = self._truncate(text, 200)
                        first_user_extracted = True
                    seq += 1
                    norm_role = role if role in ("user", "assistant", "system") else "assistant"
                    yield ParsedMessage(
                        message_id=payload.get("id"), role=norm_role,
                        content_text=self._truncate(text, 5000),
                        content_type=block.get("type", "text"),
                        model=session.model, timestamp=raw.get("timestamp"), seq=seq,
                    )

    def export_session(self, session_id, title, messages, destination_dir):
        os.makedirs(destination_dir, exist_ok=True)
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
        sid = session_id or f"export-{ts}"
        out = os.path.join(destination_dir, f"rollout-{ts}-{sid[:8]}.jsonl")
        with open(out, "w", encoding="utf-8") as f:
            for m in messages:
                txt = (m.content_text or "").strip()
                if not txt:
                    continue
                f.write(json.dumps({
                    "timestamp": m.timestamp or datetime.now(timezone.utc).isoformat(),
                    "type": "response_item",
                    "payload": {"role": m.role, "content": [{"type": "text", "text": txt}]},
                }, ensure_ascii=False) + "\n")
        return out
