"""Codeium / Windsurf adapter — indexes .pb chat_state files by metadata."""

import os
from datetime import datetime, timezone
from typing import Generator

from adapters.base import BaseAdapter, ParsedSession, ParsedMessage


class CodeiumAdapter(BaseAdapter):
    TOOL_NAME = "codeium"
    DISPLAY_NAME = "Codeium / Windsurf"

    def discover_sessions(self) -> Generator[ParsedSession, None, None]:
        for base in self.all_paths():
            chat_state = os.path.join(base, "chat_state")
            if not os.path.isdir(chat_state):
                continue
            for fname in os.listdir(chat_state):
                if not fname.endswith(".pb"):
                    continue
                if ".migrated." in fname:
                    continue
                fpath = os.path.join(chat_state, fname)
                stat = os.stat(fpath)
                # Filename encodes project path: codeium_chat_state_file_c_3A_allmydata.pb
                project = "unknown"
                if "_file_" in fname:
                    raw = fname.split("_file_", 1)[1].replace(".pb", "").replace(".migrated", "")
                    project = raw.replace("_", os.sep).replace("c_3A", "C:").replace("c_3a", "c:")
                started = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
                yield ParsedSession(
                    session_id=f"codeium:{fname.replace('.pb','')}",
                    title=f"Codeium/Windsurf chat ({os.path.basename(fname)[:24]}...)",
                    project_path=project, model=None, status="completed",
                    started_at=started, ended_at=None,
                    file_path=fpath, file_size_bytes=stat.st_size,
                    file_mtime=stat.st_mtime,
                    raw_metadata={"format": "pb"},
                )

    def parse_messages(self, session: ParsedSession) -> Generator[ParsedMessage, None, None]:
        yield ParsedMessage(
            message_id="meta", role="system",
            content_text=(
                f"Codeium/Windsurf chat stored in opaque .pb format (no readable transcript). "
                f"Project: {session.project_path}. File: {os.path.basename(session.file_path)}."
            ),
            content_type="text", seq=0,
        )
