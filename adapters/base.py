"""Base adapter interface for all AI tool session parsers.

Every adapter is a single class with BOTH halves:
- import:  tool-native files -> ParsedSession / ParsedMessage (neutral)
- export:  neutral session -> a file in that tool's native cache

This is what makes bidirectional migration between tools possible.
"""

import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Generator, Optional


@dataclass
class ParsedSession:
    """A discovered session from an AI tool (neutral format)."""
    session_id: str
    title: Optional[str] = None
    project_path: Optional[str] = None
    model: Optional[str] = None
    status: str = "completed"
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    message_count: int = 0
    file_path: str = ""
    file_size_bytes: int = 0
    file_mtime: float = 0.0
    raw_metadata: Optional[dict] = None


@dataclass
class ParsedMessage:
    """A single message within a session (neutral format)."""
    message_id: Optional[str] = None
    role: str = "user"
    content_text: Optional[str] = None
    content_type: str = "text"
    model: Optional[str] = None
    timestamp: Optional[str] = None
    token_input: Optional[int] = None
    token_output: Optional[int] = None
    raw_json: Optional[dict] = None
    parent_id: Optional[str] = None
    seq: int = 0


class BaseAdapter(ABC):
    """Abstract base class for AI tool session adapters."""

    TOOL_NAME: str = ""
    DISPLAY_NAME: str = ""

    def __init__(self, data_path: str = "", extra_paths: Optional[list] = None):
        self.data_path = data_path
        self.extra_paths = extra_paths or []

    # --- Path resolution: main path + any backup/previous-PC paths ---------
    def all_paths(self):
        """Yield the primary data path plus any extra (backup) paths."""
        seen = set()
        for p in [self.data_path] + self.extra_paths:
            if not p:
                continue
            norm = os.path.normpath(p)
            if norm in seen:
                continue
            seen.add(norm)
            yield p

    # --- Import half --------------------------------------------------------
    @abstractmethod
    def discover_sessions(self) -> Generator[ParsedSession, None, None]:
        """Walk the tool's data directories and yield session descriptors."""
        pass

    @abstractmethod
    def parse_messages(self, session: ParsedSession) -> Generator[ParsedMessage, None, None]:
        """Given a session descriptor, parse and yield its messages."""
        pass

    # --- Export half --------------------------------------------------------
    def export_session(self, session_id: str, title: str,
                       messages: list, destination_dir: str) -> str:
        """Write a neutral session into this tool's native cache format.

        Returns the path written. Must be overridden by tools with a real
        native format; the default writes a portable Markdown transcript.
        """
        os.makedirs(destination_dir, exist_ok=True)
        safe = "".join(c for c in (title or session_id) if c.isalnum() or c in " -_")[:60] \
            or session_id[:20]
        out = os.path.join(destination_dir, f"{safe}.md")
        with open(out, "w", encoding="utf-8") as f:
            f.write(f"# {title or session_id}\n\n")
            for m in messages:
                role = m.role if isinstance(m.role, str) else "user"
                txt = (m.content_text or "").strip()
                if not txt:
                    continue
                f.write(f"## {role.capitalize()}\n{txt}\n\n")
        return out

    # --- Helpers -------------------------------------------------------------
    def is_available(self) -> bool:
        return any(os.path.isdir(p) for p in self.all_paths())

    def _truncate(self, text: Optional[str], max_len: int = 500) -> Optional[str]:
        if not text:
            return text
        if len(text) <= max_len:
            return text
        return text[:max_len] + "..."

    def _safe_read_jsonl(self, path: str) -> Generator[dict, None, None]:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        continue
        except (OSError, PermissionError):
            return

    def _safe_read(self, path: str, limit: int = 2_000_000) -> Optional[str]:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return f.read(limit)
        except (OSError, PermissionError):
            return None

    def _file_stat(self, path: str):
        try:
            return os.stat(path)
        except OSError:
            return None
