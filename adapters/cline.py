"""Cline adapter — parses ~/.cline task history and state databases."""

import json
import os
from typing import Generator

from adapters.base import BaseAdapter, ParsedSession, ParsedMessage


class ClineAdapter(BaseAdapter):
    TOOL_NAME = "cline"
    DISPLAY_NAME = "Cline"

    def discover_sessions(self) -> Generator[ParsedSession, None, None]:
        for base in self.all_paths():
            if not os.path.isdir(base):
                continue
            # tasks dir
            tasks_dir = os.path.join(base, "tasks")
            if os.path.isdir(tasks_dir):
                for fname in os.listdir(tasks_dir):
                    if not fname.endswith(".json"):
                        continue
                    fpath = os.path.join(tasks_dir, fname)
                    stat = os.stat(fpath)
                    yield ParsedSession(
                        session_id=f"cline:task:{fname.replace('.json','')}",
                        title=f"Cline task: {fname.replace('.json','')[:24]}",
                        project_path=None, model=None, status="completed",
                        started_at=None, ended_at=None,
                        file_path=fpath, file_size_bytes=stat.st_size, file_mtime=stat.st_mtime,
                        raw_metadata={"type": "task"},
                    )
            # globalState / sqlite dbs
            for fname in os.listdir(base):
                if fname.endswith((".sqlite", ".db")):
                    fpath = os.path.join(base, fname)
                    stat = os.stat(fpath)
                    yield ParsedSession(
                        session_id=f"cline:db:{fname}",
                        title=f"Cline state: {fname}", project_path=None, model=None,
                        status="completed", started_at=None, ended_at=None,
                        file_path=fpath, file_size_bytes=stat.st_size, file_mtime=stat.st_mtime,
                        raw_metadata={"type": "db"},
                    )

    def parse_messages(self, session: ParsedSession) -> Generator[ParsedMessage, None, None]:
        if session.raw_metadata.get("type") == "task":
            content = self._safe_read(session.file_path, limit=200_000)
            if content:
                try:
                    data = json.loads(content)
                    task = data.get("task") if isinstance(data, dict) else str(data)
                except json.JSONDecodeError:
                    task = content
                yield ParsedMessage("task", "user", self._truncate(str(task), 5000), seq=0)
            return
        yield ParsedMessage("meta", "system", f"Cline state database: {session.file_path}", seq=0)
