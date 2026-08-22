"""Goose adapter — parses Goose chat export JSON files.

Goose exports have this structure:
{
  "id", "name", "working_dir", "created_at", "updated_at", "message_count",
  "conversation": [ { "id", "role", "created", "content": [{"type":"text","text":...}] } ]
}
"""

import json
import os
from datetime import datetime, timezone
from typing import Generator

from adapters.base import BaseAdapter, ParsedSession, ParsedMessage


class GooseAdapter(BaseAdapter):
    TOOL_NAME = "goose"
    DISPLAY_NAME = "Goose"

    def _find_export_files(self):
        """Find .json Goose chat export files across all paths."""
        for base in self.all_paths():
            if not os.path.isdir(base):
                continue
            for root, _dirs, files in os.walk(base):
                # Skip heavy dirs we don't need
                lowered = root.lower()
                if any(x in lowered for x in ("node_modules", "\\cache", "code cache",
                                              "local storage", "\\logs")):
                    continue
                for fname in files:
                    if not fname.endswith(".json"):
                        continue
                    fpath = os.path.join(root, fname)
                    yield fpath

    def discover_sessions(self) -> Generator[ParsedSession, None, None]:
        seen = set()
        for fpath in self._find_export_files():
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue
            # Only treat as a Goose export if it has a 'conversation' list
            if not isinstance(data, dict) or not isinstance(data.get("conversation"), list):
                continue
            sid = data.get("id") or os.path.basename(fpath).replace(".json", "")
            key = f"goose:{sid}"
            if key in seen:
                continue
            seen.add(key)
            stat = os.stat(fpath)
            yield ParsedSession(
                session_id=key,
                title=data.get("name"),
                project_path=data.get("working_dir"),
                model=(data.get("model_config") or {}).get("model") if isinstance(
                    data.get("model_config"), dict) else None,
                status="completed",
                started_at=data.get("created_at"),
                ended_at=data.get("updated_at"),
                message_count=len(data.get("conversation", [])),
                file_path=fpath, file_size_bytes=stat.st_size,
                file_mtime=stat.st_mtime,
                raw_metadata={"provider": data.get("provider_name")},
            )

    def parse_messages(self, session: ParsedSession) -> Generator[ParsedMessage, None, None]:
        try:
            with open(session.file_path, "r", encoding="utf-8", errors="replace") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
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
                        elif block.get("type") == "tool_result":
                            inner = block.get("content", [])
                            if isinstance(inner, list):
                                for i in inner:
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
                except (ValueError, OSError):
                    ts = None
            yield ParsedMessage(
                message_id=str(item.get("id", "")),
                role=role if role in ("user", "assistant", "tool", "system") else "user",
                content_text=self._truncate(content, 20_000),
                content_type="text",
                model=item.get("model"),
                timestamp=ts, seq=seq,
            )
