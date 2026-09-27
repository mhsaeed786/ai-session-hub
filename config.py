"""Central configuration for AI Session Hub."""

import os

HOME = os.path.expanduser("~")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "db", "session_hub.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "db", "schema.sql")

WEB_HOST = "127.0.0.1"
WEB_PORT = 5100


def _h(*parts):
    return os.path.join(HOME, *parts)


# --- Tool Data Paths -------------------------------------------------------
TOOL_CONFIGS = {
    "hermes": {
        "display_name": "Hermes",
        "adapter_class": "HermesAdapter",
        "data_path": os.path.join(HOME, "AppData", "Local", "hermes"),
        "extra_paths": [
            os.path.join(HOME, "hermes-sessions", "hermes-wsl"),
            os.path.join(HOME, "Goose Chats (Old)", "_wsl_cache"),
            os.path.join(HOME, "Documents", "Migrated data"),
        ],
        "enabled": True,
    },
    "claude_code": {
        "display_name": "Claude Code",
        "adapter_class": "ClaudeCodeAdapter",
        "data_path": os.path.join(HOME, ".claude"),
        "extra_paths": [
            os.path.join(HOME, "Documents", "Migrated data", ".claude"),
            os.path.join(HOME, "session-migration-backup-20260822", "quarantine"),
            os.path.join(HOME, "session-migration-backup-20260822", "c", "Users", "LOQ", ".claude"),
        ],
        "enabled": True,
    },
    "codex": {
        "display_name": "Codex CLI",
        "adapter_class": "CodexAdapter",
        "data_path": os.path.join(HOME, ".codex"),
        "extra_paths": [
            os.path.join(HOME, "session-migration-backup-20260822", "quarantine", "codex-sessions"),
        ],
        "enabled": True,
    },
    "gemini_antigravity": {
        "display_name": "Gemini Antigravity",
        "adapter_class": "GeminiAntigravityAdapter",
        "data_path": os.path.join(HOME, ".gemini", "antigravity"),
        "enabled": True,
    },
    "gemini_cli": {
        "display_name": "Gemini CLI",
        "adapter_class": "GeminiCliAdapter",
        "data_path": os.path.join(HOME, ".gemini", "antigravity-cli"),
        "enabled": True,
    },
    "codeium": {
        "display_name": "Codeium / Windsurf",
        "adapter_class": "CodeiumAdapter",
        "data_path": os.path.join(HOME, ".codeium"),
        "enabled": True,
    },
    "openclaw": {
        "display_name": "OpenClaw",
        "adapter_class": "OpenClawAdapter",
        "data_path": os.path.join(HOME, ".openclaw"),
        "extra_paths": [
            os.path.join(HOME, ".openclaw-autoclaw"),
            os.path.join(HOME, "session-migration-backup-20260822", "quarantine", "openclaw"),
            os.path.join(HOME, "Goose Chats (Old)", "_wsl_cache"),
        ],
        "enabled": True,
    },
    "goose": {
        "display_name": "Goose",
        "adapter_class": "GooseAdapter",
        "data_path": os.path.join(HOME, "AppData", "Roaming", "Block", "goose", "data", "sessions"),
        "extra_paths": [
            os.path.join(HOME, "Goose Chats (Old)"),
            os.path.join(HOME, "session-migration-backup-20260822", "quarantine", "goose"),
        ],
        "enabled": True,
    },
    "mimocode": {
        "display_name": "Mimocode",
        "adapter_class": "MimocodeAdapter",
        "data_path": os.path.join(HOME, ".local", "share", "mimocode"),
        "enabled": True,
    },
    "opencode": {
        "display_name": "Opencode",
        "adapter_class": "OpencodeAdapter",
        "data_path": os.path.join(HOME, ".local", "share", "opencode"),
        "enabled": True,
    },
    "chatgpt": {
        "display_name": "ChatGPT",
        "adapter_class": "ChatGptAdapter",
        "data_path": os.path.join(HOME, ".chatgpt"),
        "enabled": True,
    },
    "trae": {
        "display_name": "Trae AI",
        "adapter_class": "TraeAdapter",
        "data_path": os.path.join(HOME, ".trae"),
        "extra_paths": [
            os.path.join(HOME, ".trae-old"),
        ],
        "enabled": True,
    },
    "cursor": {
        "display_name": "Cursor",
        "adapter_class": "CursorAdapter",
        "data_path": os.path.join(HOME, ".cursor"),
        "enabled": True,
    },
    "cline": {
        "display_name": "Cline",
        "adapter_class": "ClineAdapter",
        "data_path": os.path.join(HOME, ".cline"),
        "enabled": True,
    },
    "copilot": {
        "display_name": "GitHub Copilot",
        "adapter_class": "CopilotAdapter",
        "data_path": os.path.join(HOME, ".copilot"),
        "enabled": True,
    },
    "zai": {
        "display_name": "Z.AI",
        "adapter_class": "ZaiAdapter",
        "data_path": os.path.join(HOME, ".zai"),
        "extra_paths": [
            os.path.join(HOME, "session-migration-backup-20260822", "quarantine", "zai"),
        ],
        "enabled": True,
    },
    "cherrystudio": {
        "display_name": "Cherry Studio",
        "adapter_class": "CherryStudioAdapter",
        "data_path": os.path.join(HOME, ".cherrystudio"),
        "enabled": True,
    },
    "tabnine": {
        "display_name": "Tabnine",
        "adapter_class": "GenericAdapter",
        "data_path": os.path.join(HOME, ".tabnine"),
        "enabled": True,
    },
    "oneagent": {
        "display_name": "OneAgent",
        "adapter_class": "OneAgentAdapter",
        "data_path": os.path.join(HOME, ".oneagent"),
        "enabled": True,
    },
    "zcode": {
        "display_name": "ZCode",
        "adapter_class": "GenericAdapter",
        "data_path": os.path.join(HOME, ".zcode"),
        "enabled": True,
    },
    "ai_session_extractor": {
        "display_name": "AI Session Extractor exports",
        "adapter_class": "GenericAdapter",
        "data_path": os.path.join(HOME, "ai-session-extractor", "data"),
        "enabled": True,
    },
    "master_index": {
        "display_name": "AI-Agent-Sessions-Master",
        "adapter_class": "MasterIndexAdapter",
        "data_path": os.path.join(HOME, "AI-Agent-Sessions-Master"),
        "extra_paths": [
            os.path.join(HOME, "Documents", "Migrated data", "AI-Agent-Sessions-Master"),
        ],
        "enabled": True,
    },
}


def get_adapter(tool_name: str):
    """Instantiate and return the adapter for a tool."""
    from adapters import ADAPTER_REGISTRY

    cfg = TOOL_CONFIGS.get(tool_name)
    if not cfg:
        return None
    cls = ADAPTER_REGISTRY.get(cfg["adapter_class"])
    if not cls:
        return None
    return cls(data_path=cfg["data_path"], extra_paths=cfg.get("extra_paths", []))


def all_tool_names():
    return [n for n, c in TOOL_CONFIGS.items() if c.get("enabled", True)]
