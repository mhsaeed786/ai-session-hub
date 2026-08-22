"""Cursor adapter — parses ~/.cursor/projects/*/agent-transcripts/ JSONL files."""

import json
import os
from typing import Generator

from adapters.base import BaseAdapter, ParsedSession, ParsedMessage


class CursorAdapter(BaseAdapter):
    TOOL_NAME = "cursor"
    DISPLAY_NAME = "Cursor"

    def discover_sessions(self) -> Generator[ParsedSession, None, None]:
        for base in self.all_paths():
            projects_dir = os.path.join(base, "projects")
            if not os.path.isdir(projects_dir):
                continue
            for proj_dir_name in os.listdir(projects_dir):
                proj_path = os.path.join(projects_dir, proj_dir_name)
                if not os.path.isdir(proj_path):
                    continue
                project_path = proj_dir_name.replace("-", os.sep)
                transcripts = os.path.join(proj_path, "agent-transcripts")
                if not os.path.isdir(transcripts):
                    continue
                for sess_dir in os.listdir(transcripts):
                    sess_path = os.path.join(transcripts, sess_dir)
                    if not os.path.isdir(sess_path):
                        continue
                    for fname in os.listdir(sess_path):
                        if not fname.endswith(".jsonl"):
                            continue
                        fpath = os.path.join(sess_path, fname)
                        stat = os.stat(fpath)
                        yield ParsedSession(
                            session_id=f"cursor:{sess_dir}:{fname.replace('.jsonl','')}",
                            title=f"Cursor agent: {sess_dir[:16]}",
                            project_path=project_path, model=None, status="completed",
                            started_at=None, ended_at=None,
                            file_path=fpath, file_size_bytes=stat.st_size,
                            file_mtime=stat.st_mtime, raw_metadata=None,
                        )

    def parse_messages(self, session: ParsedSession) -> Generator[ParsedMessage, None, None]:
        seq = 0
        for raw in self._safe_read_jsonl(session.file_path):
            if not isinstance(raw, dict):
                continue
            role = raw.get("role") or raw.get("type", "user")
            text = raw.get("text") or raw.get("content") or raw.get("message") or ""
            if isinstance(text, list):
                texts = []
                for b in text:
                    if isinstance(b, dict):
                        if b.get("type") == "text":
                            texts.append(b.get("text", ""))
                        elif b.get("type") in ("input_text", "output_text"):
                            texts.append(b.get("text", ""))
                        else:
                            texts.append(json.dumps(b, ensure_ascii=False))
                    else:
                        texts.append(str(b))
                text = "\n".join(t for t in texts if t)
            elif isinstance(text, dict):
                text = json.dumps(text, ensure_ascii=False)
            if not str(text).strip():
                continue
            seq += 1
            norm_role = role if role in ("user", "assistant", "system", "tool") else "user"
            yield ParsedMessage(
                message_id=raw.get("id") or str(seq), role=norm_role,
                content_text=self._truncate(str(text), 5000), content_type="text",
                model=raw.get("model"), timestamp=raw.get("timestamp"), seq=seq,
            )
