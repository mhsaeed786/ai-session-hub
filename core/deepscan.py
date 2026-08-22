"""Deep discovery — scans the entire PC for folders that look like session data.

Looks for patterns that match known session file formats:
- *.jsonl in folders named "sessions", "projects", "conversations", "chat", "history"
- *.db / *.sqlite with "sessions" or "messages" tables
- *.pb / *.pbtxt in folders named "chat_state", "antigravity", "codeium"
- Goose export *.json (have "conversation" key)
- Any folder named ".claude", ".codex", ".openclaw", ".gemini", ".hermes", etc.

Runs read-only. Never modifies anything.
"""

import json
import os
import sqlite3
from fnmatch import fnmatch
from typing import Generator

from config import HOME

# Folder name patterns that strongly suggest session data
SESSION_DIR_PATTERNS = [
    "sessions", "session", "conversations", "conversation", "chats", "chat",
    "history", "projects", "project", "transcripts", "messages",
    "chat_state", "chatstate", "state", "data", "backup", "backups",
    "exports", "agent", "agents", "workspace", "memory", "logs",
]

# Hidden config dirs we know about (and their common backup locations)
KNOWN_DOTDIRS = [
    ".claude", ".codex", ".openclaw", ".openclaw-autoclaw", ".gemini",
    ".hermes", ".hermes-wsl", ".trae", ".cursor", ".cline", ".chatgpt",
    ".antigravity", ".codeium", ".copilot", ".zai", ".cherrystudio",
    ".tabnine", ".ollama", ".agents", ".oneagent", ".zcode", ".dsh",
    ".kimi-webbridge", ".unsloth", ".ai_completion", ".playwright-mcp",
]

# Skip these heavy / irrelevant directories entirely
SKIP_DIRS = {
    "node_modules", "__pycache__", ".git", ".svn", ".hg", "venv", ".venv",
    "venv-win", "dist", "build", ".next", ".nuxt", ".cache", "Cache",
    "Code Cache", "GPUCache", "Dictionaries", "Crashpad",
    "CrashpadMetrics", "BrowserMetrics", "ShaderCache", "GrShaderCache",
    "extensions_crx_cache", "component_crx_cache", "Local Storage",
    "Session Storage", "IndexedDB", "databases", "blob_storage",
    "platform_exports", "Code Cache", "Service Worker",
    "windows", "win32", "win64", "linux", "darwin",
    "Assets", "resources", "assets", "content", "packs",
}

# File patterns that suggest session data
SESSION_FILE_PATTERNS = [
    "*.jsonl", "*.json", "*.db", "*.sqlite", "*.sqlite3", "*.pb", "*.pbtxt",
]

# Max folder size to consider (bytes) — skip if larger
MAX_DIR_SIZE = 2 * 1024 * 1024 * 1024  # 2 GB


def _dir_size(path: str) -> int:
    """Quick size estimate (first 100 files)."""
    total = 0
    count = 0
    for root, dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
            count += 1
            if count > 100:
                return total
    return total


def _is_session_folder(path: str) -> tuple:
    """Check if a folder likely contains session data.

    Returns (is_session: bool, tool_hint: str, confidence: float).
    """
    base = os.path.basename(path).lower()

    # Strong signal: known hidden config dir
    clean = base.lstrip(".")
    for dotdir in KNOWN_DOTDIRS:
        if base == dotdir or base.startswith(dotdir):
            return True, dotdir.lstrip("."), 1.0

    # Strong signal: contains session-named subdir
    try:
        entries = set(os.listdir(path))
    except (OSError, PermissionError):
        return False, "", 0.0

    for sub in entries:
        if sub.lower() in SESSION_DIR_PATTERNS:
            return True, sub.lower(), 0.8

    # Medium signal: contains session-like files
    session_files = 0
    tool_hint = ""
    for f in entries:
        for pat in SESSION_FILE_PATTERNS:
            if fnmatch(f.lower(), pat):
                session_files += 1
                if f.endswith((".db", ".sqlite")):
                    tool_hint = "sqlite"
                elif f.endswith(".jsonl"):
                    tool_hint = "jsonl"
                elif f.endswith(".pb"):
                    tool_hint = "protobuf"
                break

    if session_files >= 2:
        return True, tool_hint, 0.7
    if session_files == 1 and base in SESSION_DIR_PATTERNS:
        return True, tool_hint, 0.9

    # Check for Goose export JSON (has "conversation" key)
    for f in list(entries)[:10]:
        if f.endswith(".json"):
            fpath = os.path.join(path, f)
            try:
                size = os.path.getsize(fpath)
                if 100 < size < 10_000_000:
                    with open(fpath, "r", encoding="utf-8", errors="replace") as fh:
                        head = fh.read(500)
                    if '"conversation"' in head and '"role"' in head:
                        return True, "goose", 0.85
            except (OSError, PermissionError):
                pass

    return False, "", 0.0


def _has_session_table(db_path: str) -> bool:
    """Check if a SQLite DB has sessions/messages tables."""
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
        return "sessions" in tables or "messages" in tables
    except Exception:
        return False


def deep_scan(paths: list = None, max_depth: int = 6) -> dict:
    """Scan specified paths (or the whole user home) for session folders.

    Returns {folders: [{path, tool_hint, confidence, file_count}], total}.
    """
    if paths is None:
        paths = [HOME]
        # Also scan root of C: for backup folders
        if os.path.isdir("C:/"):
            paths.append("C:/")

    found = []
    seen = set()

    for start_path in paths:
        if not os.path.isdir(start_path):
            continue
        for root, dirs, files in os.walk(start_path):
            # Prune
            dirs[:] = [
                d for d in dirs
                if d.lower() not in SKIP_DIRS
                and not d.startswith(".")
                or d.lower() in {p.lower() for p in KNOWN_DOTDIRS}
            ]

            # Depth limit
            depth = root.replace(start_path, "").count(os.sep)
            if depth > max_depth:
                dirs.clear()
                continue

            norm = os.path.normpath(root)
            if norm in seen:
                dirs.clear()
                continue
            seen.add(norm)

            is_session, tool_hint, confidence = _is_session_folder(root)
            if not is_session:
                continue

            file_count = len(files)
            # Skip tiny or empty
            if file_count == 0:
                continue

            found.append({
                "path": norm,
                "tool_hint": tool_hint,
                "confidence": confidence,
                "file_count": file_count,
                "depth": depth,
            })

            # Don't recurse deeper into confirmed session dirs
            if confidence >= 0.8:
                dirs.clear()

    # Sort by confidence then file_count
    found.sort(key=lambda x: (-x["confidence"], -x["file_count"]))
    return {"folders": found, "total": found}


def scan_and_import_deep(paths: list = None) -> dict:
    """Deep scan + auto-import discovered folders."""
    from adapters.generic import GenericAdapter

    scan = deep_scan(paths)
    imported = 0
    errors = 0
    adapter_paths = []

    conn = get_conn()
    for folder in scan["folders"]:
        path = folder["path"]
        try:
            adapter = GenericAdapter(data_path=path, extra_paths=[])
            sessions = list(adapter.discover_sessions())
            if not sessions:
                continue
            for session in sessions:
                composite = f"deep:{session.session_id}"
                raw_meta = json.dumps({"deep_scan": True, "source_path": path})
                now = __import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc).isoformat()
                msgs = list(adapter.parse_messages(session))
                conn.execute(
                    "INSERT OR IGNORE INTO sessions "
                    "(id, tool, session_id, title, project_path, model, status, "
                    "started_at, ended_at, message_count, file_path, file_size_bytes, "
                    "file_mtime, raw_metadata, first_synced_at, last_synced_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (composite, "deep_scan", session.session_id, session.title,
                     session.project_path, session.model, "completed",
                     session.started_at, session.ended_at, len(msgs),
                     session.file_path, session.file_size_bytes, session.file_mtime,
                     raw_meta, now, now))
                imported += 1
            conn.commit()
            adapter_paths.append(path)
        except Exception as e:
            errors += 1
            print(f"  [!] Error importing {path}: {e}")

    conn.close()
    return {
        "folders_found": scan["total"],
        "sessions_imported": imported,
        "errors": errors,
        "adapter_paths": adapter_paths,
    }
