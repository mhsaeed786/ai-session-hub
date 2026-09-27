"""Adapter registry — maps class names to adapter classes."""

from adapters.base import BaseAdapter
from adapters.claude_code import ClaudeCodeAdapter
from adapters.codex import CodexAdapter
from adapters.goose import GooseAdapter
from adapters.hermes import HermesAdapter
from adapters.openclaw import OpenClawAdapter
from adapters.gemini_cli import GeminiCliAdapter
from adapters.gemini_antigravity import GeminiAntigravityAdapter
from adapters.codeium import CodeiumAdapter
from adapters.chatgpt import ChatGptAdapter
from adapters.trae import TraeAdapter
from adapters.cursor import CursorAdapter
from adapters.cline import ClineAdapter
from adapters.misc import CopilotAdapter, ZaiAdapter, CherryStudioAdapter, OneAgentAdapter
from adapters.generic import GenericAdapter
from adapters.master_index import MasterIndexAdapter
from adapters.mimocode import MimocodeAdapter
from adapters.opencode import OpencodeAdapter

ADAPTER_REGISTRY = {
    "HermesAdapter": HermesAdapter,
    "ClaudeCodeAdapter": ClaudeCodeAdapter,
    "CodexAdapter": CodexAdapter,
    "GooseAdapter": GooseAdapter,
    "OpenClawAdapter": OpenClawAdapter,
    "GeminiCliAdapter": GeminiCliAdapter,
    "GeminiAntigravityAdapter": GeminiAntigravityAdapter,
    "CodeiumAdapter": CodeiumAdapter,
    "ChatGptAdapter": ChatGptAdapter,
    "TraeAdapter": TraeAdapter,
    "CursorAdapter": CursorAdapter,
    "ClineAdapter": ClineAdapter,
    "CopilotAdapter": CopilotAdapter,
    "ZaiAdapter": ZaiAdapter,
    "CherryStudioAdapter": CherryStudioAdapter,
    "OneAgentAdapter": OneAgentAdapter,
    "GenericAdapter": GenericAdapter,
    "MasterIndexAdapter": MasterIndexAdapter,
    "MimocodeAdapter": MimocodeAdapter,
    "OpencodeAdapter": OpencodeAdapter,
}
