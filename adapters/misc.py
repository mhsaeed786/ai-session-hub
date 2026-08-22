"""Copilot / Z.AI / CherryStudio / OneAgent lightweight adapters.

These tools store sessions server-side or in opaque/IDE-managed formats, so
they are indexed (discovered, categorized, master-prompted) rather than parsed
into full transcripts.
"""

import os
from typing import Generator

from adapters.base import BaseAdapter, ParsedSession, ParsedMessage


class _MetadataAdapter(BaseAdapter):
    """Generic adapter that indexes the contents of a directory tree."""

    SUFFIXES = (".json", ".jsonl", ".md", ".txt", ".log")
    LABEL = "data"

    def discover_sessions(self) -> Generator[ParsedSession, None, None]:
        for base in self.all_paths():
            if not os.path.isdir(base):
                continue
            for root, _dirs, files in os.walk(base):
                lowered = root.lower()
                if any(x in lowered for x in ("node_modules", "\\cache",
                                              "code cache", "local storage")):
                    continue
                for fname in files:
                    if not fname.endswith(self.SUFFIXES):
                        continue
                    fpath = os.path.join(root, fname)
                    stat = os.stat(fpath)
                    rel = os.path.relpath(fpath, base)
                    yield ParsedSession(
                        session_id=f"{self.TOOL_NAME}:{rel.replace(os.sep,'__')}",
                        title=f"{self.DISPLAY_NAME}: {os.path.basename(fname)}",
                        project_path=None, model=None, status="completed",
                        started_at=None, ended_at=None,
                        file_path=fpath, file_size_bytes=stat.st_size, file_mtime=stat.st_mtime,
                        raw_metadata={"rel": rel},
                    )

    def parse_messages(self, session: ParsedSession) -> Generator[ParsedMessage, None, None]:
        content = self._safe_read(session.file_path, limit=200_000)
        if content:
            yield ParsedMessage("doc", "system", self._truncate(content, 5000), seq=0)
        else:
            yield ParsedMessage(
                "meta", "system",
                f"{self.DISPLAY_NAME} data file: {session.raw_metadata.get('rel')}", seq=0,
            )


class CopilotAdapter(_MetadataAdapter):
    TOOL_NAME = "copilot"
    DISPLAY_NAME = "GitHub Copilot"
    LABEL = "IDE logs"


class ZaiAdapter(_MetadataAdapter):
    TOOL_NAME = "zai"
    DISPLAY_NAME = "Z.AI"
    LABEL = "logs"


class CherryStudioAdapter(_MetadataAdapter):
    TOOL_NAME = "cherrystudio"
    DISPLAY_NAME = "Cherry Studio"
    LABEL = "config"


class OneAgentAdapter(_MetadataAdapter):
    TOOL_NAME = "oneagent"
    DISPLAY_NAME = "OneAgent"
    LABEL = "sessions"
