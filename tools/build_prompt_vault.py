"""Consolidate EVERY prompt ever given, grouped project-wise and task-wise.

Scans all sessions in the hub DB, assigns each session to a project cluster,
then writes one file per project containing every prompt ever given to any
AI tool for that project.

Output: C:\\Users\\LOQ\\prompt-vault\\<Project>.md
"""
import sqlite3
import os
import re
from collections import defaultdict

DB = r"C:\Users\LOQ\ai-session-hub\db\session_hub.db"
OUT = r"C:\Users\LOQ\prompt-vault"
os.makedirs(OUT, exist_ok=True)

# Project clusters: keywords in title/first-prompts -> project name
CLUSTERS = [
    ("AI Super App", ["super app", "super-app", "superagent", "super agent",
                      "ba qa", "ba-qa", "automation suite", "monolith"]),
    ("OneAgent", ["oneagent", "one-agent", "one agent"]),
    ("AI Sessions Hub", ["session hub", "sessions hub", "universal ai session",
                         "ai session hub", "import.*sessions", "hermes sessions"]),
    ("AI Session Extractor", ["session extractor", "chat extractor", "extract chats",
                              "ai-session-extractor", "dom dump", "extract.*ai.*web",
                              "chat downloader"]),
    ("Teams Scraper & Work History", ["teams", "teams scraper", "work hours",
                                      "graph api", "outlook", "daily work",
                                      "work history", "email scraper"]),
    ("Udemy Automation", ["udemy", "autonomous learning", "course.*enroll"]),
    ("AI Researcher", ["research", "deep research", "gpt-researcher", "miniperplx",
                       "perplexity", "research pipeline", "saas opportunity"]),
    ("OmniMedia Agency", ["omnimedia", "content automation", "ai writer",
                          "blog poster", "seo.*article", "content agency"]),
    ("Novel Writing", ["novel", "novelforge", "story generation", "prose"]),
    ("FHIR Work (CureMD)", ["fhir", "uscdi", "ecr", "hl7", "smart on fhir",
                            "search parameter", "questionnaire", "provenance",
                            "leap", "onc", "inferno"]),
    ("OpenClaw & Agents Infra", ["openclaw", "goose", "discord gateway",
                                 "gateway", "wsl", "mcp", "ollama"]),
    ("GitHub & DevOps", ["github sync", "push.*github", "repo audit",
                         "git ", "devops", "reorganize folders", "sync code"]),
    ("AI Music", ["music", "song", "suno", "melody"]),
    ("Music & Media", ["media agency", "video"]),
]


def classify(text):
    t = text.lower()
    for project, kws in CLUSTERS:
        for kw in kws:
            if re.search(kw, t):
                return project
    return None


conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

# also include raw hermes db (some sessions only exist there)
rows = conn.execute(
    "SELECT id, tool, title, message_count FROM sessions "
    "ORDER BY message_count DESC").fetchall()

vault = defaultdict(lambda: defaultdict(list))  # project -> task(session) -> prompts

for r in rows:
    prompts = conn.execute(
        "SELECT seq, content_text FROM messages "
        "WHERE session_fk=? AND role='user' AND length(content_text)>15 "
        "ORDER BY seq", (r["id"],)).fetchall()
    if not prompts:
        continue

    # classify by title + all prompts text
    all_text = (r["title"] or "") + " " + " ".join(
        (p["content_text"] or "")[:400] for p in prompts[:10])
    project = classify(all_text)
    if not project:
        project = "Uncategorized"

    task_name = (r["title"] or "untitled").strip()[:80] or "untitled"
    # strip think-prefix noise
    task_name = re.sub(r"^<think>.*?\.\.\.\s*", "", task_name)
    task_name = task_name.replace("\n", " ")[:80]

    for p in prompts:
        text = (p["content_text"] or "").strip()
        # skip system-ish noise
        if text.startswith("[CONTEXT COMPACTION") or text.startswith("<environment"):
            continue
        if "maximum number of tool-calling iterations" in text:
            continue
        vault[project][f"{task_name} [{r['tool']}]"].append(text[:2000])

# write one file per project
total_prompts = 0
index_lines = ["# Prompt Vault - Every prompt ever given, by project", ""]
for project in sorted(vault):
    safe = re.sub(r"[^A-Za-z0-9_\- ]", "", project).replace(" ", "_")
    fp = os.path.join(OUT, f"{safe}.md")
    lines = [f"# {project}", "",
             f"Sessions: {len(vault[project])}", ""]
    count = 0
    for task, prompts in vault[project].items():
        lines.append(f"## Task: {task}")
        lines.append(f"*({len(prompts)} prompts)*")
        lines.append("")
        for i, pr in enumerate(prompts, 1):
            pr_clean = pr.replace("\n", " ").strip()
            lines.append(f"{i}. {pr_clean}")
            count += 1
        lines.append("")
    with open(fp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    total_prompts += count
    index_lines.append(f"- **{project}**: {len(vault[project])} sessions, "
                       f"{count} prompts -> {safe}.md")
    print(f"{project}: {len(vault[project])} tasks, {count} prompts")

with open(os.path.join(OUT, "_INDEX.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(index_lines))
print(f"\nTOTAL: {total_prompts} prompts across {len(vault)} projects")
print(f"Vault: {OUT}")
