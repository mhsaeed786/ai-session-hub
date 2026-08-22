"""Gemini Antigravity adapter — indexes .pb / pbtxt metadata + readable text.

.pb files are protobuf/encrypted; we index them by metadata and, where a
human-readable text file (pbtxt / .md) exists, read its content.
"""

import os
from datetime import datetime, timezone
from typing import Generator

from adapters.base import BaseAdapter, ParsedSession, ParsedMessage


class GeminiAntigravityAdapter(BaseAdapter):
    TOOL_NAME = "gemini_antigravity"
    DISPLAY_NAME = "Gemini Antigravity"

    def discover_sessions(self) -> Generator[ParsedSession, None, None]:
        for base in self.all_paths():
            if not os.path.isdir(base):
                continue
            conv_dir = os.path.join(base, "conversations")
            if os.path.isdir(conv_dir):
                for fname in os.listdir(conv_dir):
                    if not fname.endswith(".pb"):
                        continue
                    fpath = os.path.join(conv_dir, fname)
                    stat = os.stat(fpath)
                    started = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
                    yield ParsedSession(
                        session_id=f"gemini_ag:{fname.replace('.pb','')}",
                        title=f"Antigravity Conversation ({fname[:20]}...)",
                        project_path=None, model="gemini", status="completed",
                        started_at=started, ended_at=None,
                        file_path=fpath, file_size_bytes=stat.st_size,
                        file_mtime=stat.st_mtime,
                        raw_metadata={"format": "pb", "note": "binary protobuf; indexed by metadata"},
                    )
            # Also index *.pbtxt / *.md files as readable "documents"
            for root, _dirs, files in os.walk(base):
                for fname in files:
                    if not fname.endswith((".pbtxt", ".md")):
                        continue
                    fpath = os.path.join(root, fname)
                    stat = os.stat(fpath)
                    rel = os.path.relpath(fpath, base)
                    yield ParsedSession(
                        session_id=f"gemini_ag:{rel.replace(os.sep,'__')}",
                        title=f"Antigravity note: {os.path.basename(fname)}",
                        project_path=None, model="gemini", status="completed",
                        started_at=None, ended_at=None,
                        file_path=fpath, file_size_bytes=stat.st_size,
                        file_mtime=stat.st_mtime,
                        raw_metadata={"format": "text", "rel": rel},
                    )

    def parse_messages(self, session: ParsedSession) -> Generator[ParsedMessage, None, None]:
        fmt = (session.raw_metadata or {}).get("format")
        if fmt != "text":
            # Binary .pb — we cannot extract a transcript, but index metadata.
            yield ParsedMessage(
                message_id="meta", role="system",
                content_text=(
                    f"Antigravity conversation stored in opaque .pb format "
                    f"(no readable transcript). File: {os.path.basename(session.file_path)}."
                ),
                content_type="text", seq=0,
            )
            return
        content = self._safe_read(session.file_path, limit=500_000)
        if not content:
            return
        yield ParsedMessage(
            message_id="doc", role="system",
            content_text=self._truncate(content, 20_000),
            content_type="text", seq=0,
        )
