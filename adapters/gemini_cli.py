"""Gemini CLI adapter — parses ~/.gemini/antigravity-cli/ history.jsonl."""

import os
from datetime import datetime, timezone
from typing import Generator

from adapters.base import BaseAdapter, ParsedSession, ParsedMessage


class GeminiCliAdapter(BaseAdapter):
    TOOL_NAME = "gemini_cli"
    DISPLAY_NAME = "Gemini CLI"

    def discover_sessions(self) -> Generator[ParsedSession, None, None]:
        for base in self.all_paths():
            history_path = os.path.join(base, "history.jsonl")
            if not os.path.isfile(history_path):
                continue
            conversations = {}
            for raw in self._safe_read_jsonl(history_path):
                conv_id = raw.get("conversationId", "unknown")
                conversations.setdefault(conv_id, []).append(raw)
            for conv_id, entries in conversations.items():
                if not entries:
                    continue
                first, last = entries[0], entries[-1]
                display = first.get("display", "")
                workspace = first.get("workspace", "")
                ts_ms = first.get("timestamp")
                started = None
                if isinstance(ts_ms, (int, float)):
                    try:
                        started = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()
                    except (ValueError, OSError):
                        started = None
                # One representative file path
                stat = None
                try:
                    stat = os.stat(history_path)
                except OSError:
                    pass
                yield ParsedSession(
                    session_id=f"gemini_cli:{conv_id}",
                    title=display or f"Gemini CLI conversation {conv_id[:8]}",
                    project_path=workspace or None,
                    model=first.get("model") or first.get("modelId"),
                    status="completed",
                    started_at=started,
                    ended_at=None,
                    file_path=history_path,
                    file_size_bytes=stat.st_size if stat else 0,
                    file_mtime=stat.st_mtime if stat else 0.0,
                    raw_metadata={"conv_id": conv_id, "entries": len(entries)},
                )

    def parse_messages(self, session: ParsedSession) -> Generator[ParsedMessage, None, None]:
        conv_id = (session.raw_metadata or {}).get("conv_id")
        seq = 0
        for raw in self._safe_read_jsonl(session.file_path):
            if raw.get("conversationId") != conv_id:
                continue
            role = raw.get("role", "user")
            text = raw.get("text") or raw.get("display") or ""
            if isinstance(text, (dict, list)):
                text = str(text)
            if not text:
                continue
            seq += 1
            ts_ms = raw.get("timestamp")
            ts = None
            if isinstance(ts_ms, (int, float)):
                try:
                    ts = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()
                except (ValueError, OSError):
                    ts = None
            yield ParsedMessage(
                message_id=raw.get("id") or str(seq), role=role,
                content_text=self._truncate(str(text), 5000),
                content_type="text", model=raw.get("model"),
                timestamp=ts, seq=seq,
            )
