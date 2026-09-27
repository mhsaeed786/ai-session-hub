"""OpenClaw adapter — parses ~/.openclaw/sessions/*.jsonl session transcripts."""

import json
import os
from typing import Generator

from adapters.base import BaseAdapter, ParsedSession, ParsedMessage


class OpenClawAdapter(BaseAdapter):
    TOOL_NAME = "openclaw"
    DISPLAY_NAME = "OpenClaw"

    def discover_sessions(self) -> Generator[ParsedSession, None, None]:
        for base in self.all_paths():
            if not os.path.isdir(base):
                continue
            sessions_dir = os.path.join(base, "sessions")
            if os.path.isdir(sessions_dir):
                for fname in os.listdir(sessions_dir):
                    if not fname.endswith(".jsonl"):
                        continue
                    if ".migrated." in fname or ".deleted." in fname:
                        continue
                    fpath = os.path.join(sessions_dir, fname)
                    stat = os.stat(fpath)
                    yield ParsedSession(
                        session_id=f"openclaw:{fname.replace('.jsonl','')}",
                        title=f"OpenClaw Session: {fname.replace('.jsonl','')[:12]}",
                        project_path=None, model=None, status="completed",
                        started_at=None, ended_at=None,
                        file_path=fpath, file_size_bytes=stat.st_size,
                        file_mtime=stat.st_mtime, raw_metadata={"source": "sessions"},
                    )
            # AutoClaw layout: agents/main/sessions/
            agents_dir = os.path.join(base, "agents", "main", "sessions")
            if os.path.isdir(agents_dir):
                for fname in os.listdir(agents_dir):
                    if not fname.endswith(".jsonl"):
                        continue
                    if ".migrated." in fname or ".deleted." in fname:
                        continue
                    fpath = os.path.join(agents_dir, fname)
                    stat = os.stat(fpath)
                    yield ParsedSession(
                        session_id=f"openclaw:{fname.replace('.jsonl','')}",
                        title=f"AutoClaw Session: {fname.replace('.jsonl','')[:12]}",
                        project_path=None, model=None, status="completed",
                        started_at=None, ended_at=None,
                        file_path=fpath, file_size_bytes=stat.st_size,
                        file_mtime=stat.st_mtime, raw_metadata={"source": "autoclaw"},
                    )
            # Direct jsonl in base
            for fname in os.listdir(base):
                if not fname.endswith(".jsonl"):
                    continue
                if ".migrated." in fname or ".deleted." in fname:
                    continue
                fpath = os.path.join(base, fname)
                stat = os.stat(fpath)
                yield ParsedSession(
                    session_id=f"openclaw:{fname.replace('.jsonl','')}",
                    title=f"OpenClaw Session: {fname.replace('.jsonl','')[:12]}",
                    project_path=None, model=None, status="completed",
                    started_at=None, ended_at=None,
                    file_path=fpath, file_size_bytes=stat.st_size,
                    file_mtime=stat.st_mtime, raw_metadata={"source": "direct"},
                )

    def parse_messages(self, session: ParsedSession) -> Generator[ParsedMessage, None, None]:
        seq = 0
        for raw in self._safe_read_jsonl(session.file_path):
            if not isinstance(raw, dict):
                continue
            etype = raw.get("type", "")
            if etype == "session":
                session.started_at = raw.get("timestamp")
                session.project_path = raw.get("cwd")
                session.model = raw.get("model")
                continue
            if etype in ("assistant", "user", "system", "tool"):
                role = etype
                content = raw.get("message") or raw.get("content") or ""
                if isinstance(content, (dict, list)):
                    content = json.dumps(content, ensure_ascii=False)
                seq += 1
                yield ParsedMessage(
                    message_id=raw.get("id") or str(seq),
                    role=role,
                    content_text=self._truncate(str(content), 5000),
                    content_type="text",
                    model=raw.get("model"),
                    timestamp=raw.get("timestamp"),
                    raw_json=raw, seq=seq,
                )
