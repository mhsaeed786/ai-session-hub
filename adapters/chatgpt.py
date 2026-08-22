"""ChatGPT desktop adapter — parses ~/.chatgpt/ config + any conversation exports."""

import json
import os
from typing import Generator

from adapters.base import BaseAdapter, ParsedSession, ParsedMessage


class ChatGptAdapter(BaseAdapter):
    TOOL_NAME = "chatgpt"
    DISPLAY_NAME = "ChatGPT"

    def discover_sessions(self) -> Generator[ParsedSession, None, None]:
        for base in self.all_paths():
            if not os.path.isdir(base):
                continue
            for root, _dirs, files in os.walk(base):
                lowered = root.lower()
                if any(x in lowered for x in ("node_modules", "\\cache")):
                    continue
                for fname in files:
                    if not fname.endswith(".json"):
                        continue
                    fpath = os.path.join(root, fname)
                    try:
                        with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                            data = json.load(f)
                    except (OSError, json.JSONDecodeError):
                        continue
                    # ChatGPT export = list of conversations, or dict with conversations key
                    if isinstance(data, list):
                        for conv in data:
                            if isinstance(conv, dict) and conv.get("id"):
                                stat = os.stat(fpath)
                                yield ParsedSession(
                                    session_id=f"chatgpt:{conv['id']}",
                                    title=conv.get("title") or f"ChatGPT: {str(conv['id'])[:8]}",
                                    project_path=None, model=conv.get("model"),
                                    status="completed",
                                    started_at=self._iso(conv.get("create_time")),
                                    ended_at=self._iso(conv.get("update_time")),
                                    file_path=fpath, file_size_bytes=stat.st_size,
                                    file_mtime=stat.st_mtime,
                                    raw_metadata={"conv_id": conv["id"]},
                                )

    def parse_messages(self, session: ParsedSession) -> Generator[ParsedMessage, None, None]:
        conv_id = (session.raw_metadata or {}).get("conv_id")
        try:
            with open(session.file_path, "r", encoding="utf-8", errors="replace") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return
        convs = data if isinstance(data, list) else data.get("conversations", [])
        seq = 0
        for conv in convs:
            if not isinstance(conv, dict) or conv.get("id") != conv_id:
                continue
            mapping = conv.get("mapping", {})
            for node in mapping.values():
                if not isinstance(node, dict):
                    continue
                msg = node.get("message") or {}
                author = msg.get("author") or {}
                role = author.get("role", "user")
                content = msg.get("content") or {}
                parts = content.get("parts") or []
                text = "\n".join(str(p) for p in parts if p)
                if not text:
                    continue
                seq += 1
                yield ParsedMessage(
                    message_id=str(msg.get("id", seq)), role=role,
                    content_text=self._truncate(text, 5000), content_type="text",
                    timestamp=self._iso(msg.get("create_time")), seq=seq,
                )

    @staticmethod
    def _iso(val):
        if not val:
            return None
        try:
            from datetime import datetime, timezone
            return datetime.fromtimestamp(float(val), tz=timezone.utc).isoformat()
        except (TypeError, ValueError, OSError):
            return None
