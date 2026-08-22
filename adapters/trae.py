"""Trae AI adapter — indexes ~/.trae worktrees and config for session context."""

import os
from typing import Generator

from adapters.base import BaseAdapter, ParsedSession, ParsedMessage


class TraeAdapter(BaseAdapter):
    TOOL_NAME = "trae"
    DISPLAY_NAME = "Trae AI"

    def discover_sessions(self) -> Generator[ParsedSession, None, None]:
        for base in self.all_paths():
            if not os.path.isdir(base):
                continue
            # worktrees carry project context
            wt = os.path.join(base, "worktrees")
            if os.path.isdir(wt):
                for entry in os.listdir(wt):
                    p = os.path.join(wt, entry)
                    if not os.path.isdir(p):
                        continue
                    yield ParsedSession(
                        session_id=f"trae:wt:{entry}",
                        title=f"Trae worktree: {entry}",
                        project_path=p, model=None, status="completed",
                        started_at=None, ended_at=None,
                        file_path=p, file_size_bytes=0, file_mtime=0.0,
                        raw_metadata={"type": "worktree"},
                    )
            # argv.json / config
            for cfg in ("argv.json", "skill-config.json"):
                cp = os.path.join(base, cfg)
                if os.path.isfile(cp):
                    stat = os.stat(cp)
                    yield ParsedSession(
                        session_id=f"trae:cfg:{cfg}",
                        title=f"Trae config: {cfg}",
                        project_path=None, model=None, status="completed",
                        started_at=None, ended_at=None,
                        file_path=cp, file_size_bytes=stat.st_size, file_mtime=stat.st_mtime,
                        raw_metadata={"type": "config"},
                    )

    def parse_messages(self, session: ParsedSession) -> Generator[ParsedMessage, None, None]:
        if session.raw_metadata.get("type") == "config":
            content = self._safe_read(session.file_path, limit=100_000)
            if content:
                yield ParsedMessage("cfg", "system", self._truncate(content, 5000), seq=0)
            return
        yield ParsedMessage(
            "meta", "system",
            f"Trae worktree for project: {session.project_path or session.session_id}", seq=0,
        )
