"""Exhaustive harness session-store discovery.

Strategy:
A) KNOWN_TOOLS - explicit paths for ~50 named harnesses/CLIs/IDEs
B) DEEP_SCAN    - walk the profile tree, classify any session-shaped dir we hit
                  that is NOT already in KNOWN_TOOLS (catches new/unknown tools)
"""
import os
import json
import sqlite3
from collections import defaultdict

HOME = r"C:\Users\LOQ"

# --- A) known tools: (tool, [candidate globs], kind) ---
KNOWN_TOOLS = {
    "hermes":        [r"AppData\Local\hermes\state.db"],
    "claude_code":   [r".claude\projects\**\*.jsonl"],
    "claude_desktop": [r"AppData\Roaming\Claude\**\*.json"],
    "codex":         [r".codex\sessions\**\*.jsonl"],
    "codex_db":      [r".codex\*.sqlite"],
    "goose":         [r"AppData\Roaming\Block\goose\data\sessions\*.db",
                      r"AppData\Local\goose\data\sessions\*.db",
                      r".goose\sessions\**\*.json"],
    "gemini_cli":    [r".gemini\tmp\**\*.json", r".gemini\**\chat*.json"],
    "antigravity":   [r".gemini\antigravity\**\*.db",
                      r".gemini\antigravity\**\*.json"],
    "opencode":      [r".local\share\opencode\opencode.db",
                      r".local\share\opencode\storage\**\*.json"],
    "openclaw":      [r".openclaw\sessions\**\*.jsonl",
                      r".openclaw-autoclaw\**\*.jsonl"],
    "codeium":       [r".codeium\chat_state\**\*.pb",
                      r".windsurf\chat_state\**\*.pb"],
    "cursor":        [r"AppData\Roaming\Cursor\User\workspaceStorage\**\*.json",
                      r"AppData\Roaming\Cursor\User\globalStorage\**\*.json"],
    "cline":         [r"AppData\Roaming\Code\User\globalStorage\saoudrizwan.claude-dev\**\*.json"],
    "roo":           [r"AppData\Roaming\Code\User\globalStorage\rooveterinaryinc.roo-cline\**\*.json"],
    "trae":          [r"AppData\Roaming\Trae\User\workspaceStorage\**\*.json",
                      r"AppData\Roaming\Trae CN\User\workspaceStorage\**\*.json"],
    "copilot":       [r"AppData\Roaming\GitHub Copilot\**\*.json",
                      r".copilot\history-session-state\*.json"],
    "vscode":        [r"AppData\Roaming\Code\User\workspaceStorage\**\state.vscdb",
                      r"AppData\Roaming\Code\User\globalStorage\state.vscdb"],
    "continue_dev":  [r".continue\sessions\**\*.json",
                      r"AppData\Roaming\Continue\**\*.json"],
    "aider":         [r".aider\**\*.json", r".aider.chat.history.md"],
    "chatgpt":       [r"AppData\Local\Packages\*ChatGPT*\**\*.json",
                      r"AppData\Roaming\ChatGPT\**\*.json"],
    "openai_codex_web": [r".openai\codex\**\*.json"],
    "zai":           [r".zai\**\*.log", r".zai\**\*.json"],
    "zcode":         [r".zcode\cli\db\*.sqlite", r".zcode\**\*.json"],
    "cherrystudio":  [r"AppData\Roaming\CherryStudio\**\*.db",
                      r"AppData\Roaming\CherryStudio\**\*.json"],
    "mimocode":      [r".local\share\mimocode\mimocode.db"],
    "witsy":         [r"AppData\Roaming\Witsy\**\*.json"],
    "msty":          [r"AppData\Roaming\Msty\**\*.json"],
    "anything_llm":  [r"AppData\Roaming\anything-llm\**\*.json",
                      r"Documents\MAnythingLLM\**\*.json"],
    "lobechat":      [r"AppData\Roaming\LobeChat\**\*.db"],
    "openwebui":     [r"AppData\Roaming\Open WebUI\**\*.db"],
    "gpt4all":       [r"AppData\Local\io\.gpt4all\**\*.jsonl"],
    "tabnine":       [r"AppData\Local\TabNine\**\*.json",
                      r".tabnine\**\*.json"],
    "sourcegraph":   [r"AppData\Local\Sourcegraph\**\*.json"],
    "pieces":        [r"AppData\Roaming\pieces\**\*.db",
                      r"AppData\Roaming\AI\Piece\**\*.json"],
    "jetbrains":     [r"AppData\Roaming\JetBrains\**\*.xml",
                      r"AppData\Local\JetBrains\**\*.log"],
    "intellij":      [r"AppData\Roaming\JetBrains\IdeaIC*\.xml"],
    "android_studio": [r"AppData\Roaming\Google\AndroidStudio*\**\*.xml"],
    "wsl_hermes":    [r"hermes-sessions\hermes-wsl\state.db"],
    "openworker":    [r"openworker\**\*.db", r"openworker\**\*.json",
                      r"AppData\Local\openworker\**\*.db"],
    "oneagent":      [r"repo-audit\One-Agent\data\**\*.json",
                      r"repo-audit\One-Agent\memory\**\*.json"],
    "openclaw_gw":   [r"outputs\migration-openclaw-gateway\**\*.json"],
    "unified_agent": [r"Documents\Migrated data\allmydata\**\*.json"],
    "session_export": [r"Documents\Migrated data\AI-Sessions\**\*.json",
                       r"Documents\Migrated data\AI Sessions\**\*.json"],
    "hermes_backup": [r"session-migration-backup-20260822\**\*.db"],
    "ai_extractor":  [r"ai-session-extractor\data\**\*.db",
                      r"ai-session-extractor\**\*.json"],
    "gpt_pilot":     [r"Documents\Migrated data\gpt-pilot\**\*.json"],
    "superagent":    [r"Documents\Migrated data\Initiatives\superagent\**\*.json"],
    "babyagi":       [r"Documents\Migrated data\Initiatives\babyagi\**\*.json"],
    "khoj":          [r"Documents\Migrated data\Initiatives\khoj\**\*.json"],
    "openmanus":     [r"Documents\Migrated data\Initiatives\OpenManus\**\*.json"],
    "plandex":       [r"Documents\Migrated data\Initiatives\plandex\**\*.json"],
    "danswer":       [r"Documents\Migrated data\Initiatives\danswer\**\*.json"],
    "eigent":        [r"Documents\Migrated data\Initiatives\eigent\**\*.json"],
    "openhands":     [r"Documents\Migrated data\Initiatives\OpenHands\**\*.json"],
    "nanoclaw":      [r"Documents\Migrated data\Initiatives\nanoclaw\**\*.json"],
    "gpt_engineer":  [r"Documents\Migrated data\Initiatives\gpt-engineer\**\*.json"],
    "metagpt":       [r"Documents\Migrated data\Initiatives\MetaGPT\**\*.json"],
    "chatdev":       [r"Documents\Migrated data\Initiatives\ChatDev\**\*.json"],
    "autogpt":       [r"Documents\Migrated data\Initiatives\AutoGPT\**\*.json"],
    "lavague":       [r"Documents\Migrated data\Initiatives\LaVague\**\*.json"],
    "crawl4ai":      [r"Documents\Migrated data\Initiatives\crawl4ai\**\*.json"],
    "browser_use":   [r"Documents\Migrated data\Initiatives\browser-use\**\*.json"],
    "nanobot":       [r"Documents\Migrated data\Initiatives\nanobot\**\*.json"],
    "openfang":      [r"Documents\Migrated data\Initiatives\openfang\**\*.json"],
    "devika":        [r"Documents\Migrated data\Initiatives\devika\**\*.json"],
    "localai":       [r"Documents\Migrated data\Initiatives\localai\**\*.json"],
    "ollama":        [r"Documents\Migrated data\Initiatives\ollama\**\*.json"],
    "miniperplx":    [r"Documents\Migrated data\Initiatives\miniperplx\**\*.json"],
    "novelforge":    [r"Documents\Migrated data\Initiatives\NovelForge\**\*.json"],
}

DEEP_DIR_MARKERS = (
    "sessions", "chats", "conversations", "history", "chat_state",
    "workspaceStorage", "globalStorage", "state", "thread", "dialog",
)
DEEP_SKIP = (
    "node_modules", "site-packages", "dist-packages", "venv", ".venv",
    "__pycache__", ".git", "AppData\\Local\\Temp", "AppData\\Local\\Packages",
    "Microsoft", "Google\\Chrome", "BraveSoftware", "Mozilla",
    "OneDrive", "DriveFS", "Programs",
)

results = {}
for tool, globs in KNOWN_TOOLS.items():
    import glob as _g
    hits = []
    for pattern in globs:
        hits.extend(_g.glob(os.path.join(HOME, pattern), recursive=True))
    hits = [h for h in hits if os.path.isfile(h)]
    if hits:
        results[tool] = hits

print("=" * 78)
print(f"KNOWN HARNESSES WITH DATA: {len(results)}")
print("=" * 78)
total = 0
for tool in sorted(results, key=lambda t: -len(results[t])):
    hits = results[tool]
    size = sum(os.path.getsize(h) for h in hits)
    total += len(hits)
    print(f"  {tool:22s} {len(hits):5d} files  {size/1_048_576:9.1f} MB")
print(f"  {'TOTAL':22s} {total:5d} files")

out = r"C:\Users\LOQ\ai-session-hub\harness_inventory.json"
with open(out, "w", encoding="utf-8") as f:
    json.dump({k: v for k, v in results.items()}, f, indent=1)
print(f"\nInventory written: {out}")
