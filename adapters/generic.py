"""Generic + MasterIndex adapters.

- GenericAdapter: indexes any folder of JSON/MD/TXT files (fallback for tools
  without a dedicated adapter).
- MasterIndexAdapter: reads the AI-Agent-Sessions-Master markdown index files
  (prior work that already aggregated sessions by tool into readable .md).
"""

import json
import os
from typing import Generator

from adapters.base import BaseAdapter, ParsedSession, ParsedMessage


class GenericAdapter(BaseAdapter):
    TOOL_NAME = "generic"
    DISPLAY_NAME = "Generic"

    SUFFIXES = (".json", ".jsonl", ".md", ".txt", ".html", ".csv")

    def discover_sessions(self) -> Generator[ParsedSession, None, None]:
        for base in self.all_paths():
            if not os.path.isdir(base):
                continue
            for root, _dirs, files in os.walk(base):
                lowered = root.lower()
                if any(x in lowered for x in ("node_modules", "\\.git", "\\cache",
                                              "code cache", "local storage", "__pycache__")):
                    continue
                for fname in files:
                    if not fname.endswith(self.SUFFIXES):
                        continue
                    fpath = os.path.join(root, fname)
                    stat = os.stat(fpath)
                    rel = os.path.relpath(fpath, base)
                    yield ParsedSession(
                        session_id=f"{self.TOOL_NAME}:{rel.replace(os.sep,'__')}",
                        title=os.path.splitext(fname)[0],
                        project_path=os.path.dirname(fpath), model=None,
                        status="completed", started_at=None, ended_at=None,
                        file_path=fpath, file_size_bytes=stat.st_size, file_mtime=stat.st_mtime,
                        raw_metadata={"rel": rel},
                    )

    def parse_messages(self, session: ParsedSession) -> Generator[ParsedMessage, None, None]:
        content = self._safe_read(session.file_path, limit=500_000)
        if content:
            yield ParsedMessage("doc", "system", self._truncate(content, 20_000), seq=0)
        else:
            yield ParsedMessage(
                "meta", "system",
                f"Data file: {session.raw_metadata.get('rel')}", seq=0,
            )


class MasterIndexAdapter(BaseAdapter):
    TOOL_NAME = "master_index"
    DISPLAY_NAME = "AI-Agent-Sessions-Master"

    def discover_sessions(self) -> Generator[ParsedSession, None, None]:
        seen = set()
        for base in self.all_paths():
            if not os.path.isdir(base):
                continue
            for root, _dirs, files in os.walk(base):
                for fname in files:
                    if not fname.endswith(".md"):
                        continue
                    fpath = os.path.join(root, fname)
                    stat = os.stat(fpath)
                    rel = os.path.relpath(fpath, base)
                    tool_dir = os.path.basename(os.path.dirname(fpath))
                    key = f"master:{tool_dir}:{fname}"
                    if key in seen:
                        continue
                    seen.add(key)
                    yield ParsedSession(
                        session_id=key,
                        title=f"Master index: {tool_dir} / {os.path.splitext(fname)[0]}",
                        project_path=None, model=None, status="completed",
                        started_at=None, ended_at=None,
                        file_path=fpath, file_size_bytes=stat.st_size, file_mtime=stat.st_mtime,
                        raw_metadata={"tool_dir": tool_dir},
                    )

    def parse_messages(self, session: ParsedSession) -> Generator[ParsedMessage, None, None]:
        content = self._safe_read(session.file_path, limit=1_000_000)
        if content:
            yield ParsedMessage(
                "doc", "system", self._truncate(content, 20_000),
                content_type="text", seq=0,
            )
