"""Strict prompt vault v2 - ONLY genuine human-typed instructions.

Filters out (verified by audit):
- goose agent tool-summaries ("A call was made...", "Created a...")
- system/compaction/background markers
- Claude Code slash-command payloads (<command-message>, skill dumps)
- tool-call echoes
"""
import sqlite3
import os
import re
from collections import defaultdict

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prompt_filter import is_real_prompt

import os
DB = os.environ.get("ASH_DB") or str(__import__("pathlib").Path(__file__).resolve().parent.parent / "db" / "session_hub.db")
OUT = os.environ.get("PROMPT_VAULT_OUT") or str(__import__("pathlib").Path.home() / "prompt-vault")
os.makedirs(OUT, exist_ok=True)

CLUSTERS = [
    ("AI Super App", ["super app", "super-app", "superagent", "super agent",
                      "ba qa", "ba-qa", "automation suite", "monolith"]),
    ("OneAgent", ["oneagent", "one-agent", "one agent"]),
    ("AI Sessions Hub", ["session hub", "sessions hub", "universal ai session",
                         "ai session hub"]),
    ("AI Session Extractor", ["session extractor", "chat extractor",
                              "extract chats", "ai-session-extractor",
                              "chat downloader", "dom dump"]),
    ("Teams Scraper & Work History", ["teams", "work hours", "graph api",
                                      "outlook", "daily work", "work history",
                                      "email scraper"]),
    ("Udemy Automation", ["udemy", "autonomous learning"]),
    ("AI Researcher", ["research", "miniperplx", "perplexity",
                       "research pipeline", "saas opportunity", "deep research"]),
    ("OmniMedia Agency", ["omnimedia", "content automation", "ai writer",
                          "content agency", "seo.*article"]),
    ("Novel Writing", ["novel", "novelforge", "story generation", "prose"]),
    ("FHIR Work", ["fhir", "uscdi", "ecr", "hl7", "smart on fhir",
                            "search parameter", "questionnaire", "provenance",
                            "leap", "inferno"]),
    ("OpenClaw & Agents Infra", ["openclaw", "goose", "discord gateway",
                                 "gateway", "wsl", "mcp", "ollama"]),
    ("GitHub & DevOps", ["github sync", "repo audit", "git ", "devops",
                         "reorganize folders", "sync code", "push.*github"]),
    ("AI Music", ["music", "song", "suno"]),
]

REJECT_START = (
    "[System:", "[CONTEXT COMPACTION", "[OUT-OF-BAND", "[PRIOR CONTEXT",
    "[Context from", "[IMPORTANT", "[Continuing toward", "[Response",
    "System Instruction:", "[response interrupted", "<think>",
    "<command-message>", "<command-name>", "<local-command",
    "[TOOL_CALL]", "[tool_call]",
)

REJECT_ANY = (
    "maximum number of tool-calling iterations",
    "[Request interrupted",
)

# third-person agent summaries (goose writes these as role=user)
AGENT_SUMMARY = re.compile(
    r"^(A (call|shell|file|Python|configuration|browser|text|TODO|directory|"
    r"Playwright|tool|text replacement|file edit|Python module|Python file|"
    r"Python script|comprehensive|shell command|todo item|system|tool call"
    r"|full-stack|JSON|new|message|request)|"
    r"Created (a|an|the)|"
    r"The (system|tool|todo|assistant|file|script|response|browser|user|"
    r"Discudemy|error|output|issue|above|course|package|next|qbook)|"
    r"An? (editable|integration|browser|automated|attempt|error|"
    r"alternative|Python|output|debug|stealth|TypeScript|mkdir|edit"
    r"|README|code analysis|cleanup|PowerShell|syntax check|series"
    r"|delegation|requirements|todo list|command|env|.env"
    r"|\S+Agent class|\S+Engine class|\S+Store class|coder\.py|checkpoint"
    r"|write |write tool|batch script|startup bash|database module|translator"
    r"|multi-platform|Dockerfile|dockerfile|Reddit platform|supervisor|"
    r"write operation|write call|\d+-line)|"
    r"A .?(mkdir|debug|stealth|browser window|TypeScript|shell|call to the todo)|"
    r"Listed (the|all)|"
    r"Screenshots were|"
    r"Saved |Found \d|Fixed |Added |Updated |Running |"
    r"Now let me run|"
    r"Successfully|"
    r"(This|It) (time|will|means|confirms|suggests|indicates)|"
    r"(I|We) (need to|should|will|can)'?(?:t|)? (?:see|use|try|fix|run)|"
    r"(Okay|OK|Alright|Now|Next|Then|So)[,.] )")

# slash-command / skill file content
SKILL_DUMP = re.compile(r"^(# [A-Z].*(Skill|Config|Guide)|---$|"
                        r"^(name|description|metadata|allowed-tools):)",
                        re.MULTILINE)


def classify(text):
    t = text.lower()
    for project, kws in CLUSTERS:
        for kw in kws:
            if re.search(kw, t):
                return project
    return "Uncategorized"


conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

rows = conn.execute(
    "SELECT s.id, s.tool, s.title, s.message_count "
    "FROM sessions s ORDER BY s.message_count DESC").fetchall()

vault = defaultdict(lambda: defaultdict(list))
rejected = 0
kept = 0

for r in rows:
    prompts = conn.execute(
        "SELECT content_text FROM messages "
        "WHERE session_fk=? AND role='user' AND length(content_text)>15 "
        "ORDER BY seq", (r["id"],)).fetchall()
    if not prompts:
        continue

    real = [p["content_text"].strip() for p in prompts if is_real_prompt(p["content_text"])]
    rejected += len(prompts) - len(real)
    kept += len(real)
    if not real:
        continue

    sample = " ".join(real[:8])[:600]
    project = classify((r["title"] or "") + " " + sample)
    task_name = re.sub(r"^<think>.*?\.\.\.\s*", "", (r["title"] or "untitled"))
    task_name = task_name.replace("\n", " ").strip()[:80] or "untitled"

    vault[project][f"{task_name} [{r['tool']}]"] = real

total = 0
index = ["# Prompt Vault v2 - ONLY genuine user instructions", ""]
for project in sorted(vault):
    safe = re.sub(r"[^A-Za-z0-9_\- ]", "", project).replace(" ", "_")
    lines = [f"# {project}", "", f"Tasks: {len(vault[project])}", ""]
    for task, prompts in vault[project].items():
        lines.append(f"## Task: {task}")
        lines.append(f"*({len(prompts)} instructions)*")
        lines.append("")
        for i, p in enumerate(prompts, 1):
            lines.append(f"{i}. {p[:2000].replace(chr(10), ' ')}")
        lines.append("")
    with open(os.path.join(OUT, f"{safe}.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    total += len(prompts)
    index.append(f"- **{project}**: {len(vault[project])} tasks")
    print(f"{project}: {len(vault[project])} tasks")

with open(os.path.join(OUT, "_INDEX.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(index))

print(f"\nKEPT {kept} genuine instructions, REJECTED {rejected} non-user items")
print(f"Vault: {OUT}")
