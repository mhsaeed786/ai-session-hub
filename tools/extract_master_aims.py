"""Extract the AIM of every AI session on this PC into one master report."""
import sqlite3
import os
import re
from collections import defaultdict

DB = r"C:\Users\LOQ\ai-session-hub\db\session_hub.db"
OUT = r"C:\Users\LOQ\session-audit-20260822\MASTER-AIMS-REPORT.md"

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

# Goal-category keywords -> life theme (from Hassan's 12 categories)
THEMES = [
    ("FHIR/Healthcare IT career", ["fhir", "hl7", "smart on fhir", "uscdi", "ecr",
     "ehr", "onc", "inferno", "questionnaire", "provenance", "smiledr",
     "healthcare", "keycloak", "patient"]),
    ("AI Super App / polymath empire", ["super app", "super-app", "superagent",
     "oneagent", "polymath", "billionaire", "chief of staff", "monolith",
     "clickup alternative", "manus alternative"]),
    ("Automation & agents", ["automation", "automate", "orchestrator", "scrape",
     "scraper", "bot", "workflow", "pipeline", "watcher", "goose", "openclaw"]),
    ("Session/knowledge management", ["session hub", "sessions", "chat export",
     "extract chats", "master prompt", "knowledge base", "backup"]),
    ("Content & media creation", ["novel", "music", "blog", "content automation",
     "youtube", "writer", "seo", "social media"]),
    ("Learning systems", ["udemy", "tutorial", "learn", "course", "curriculum",
     "study", "practice"]),
    ("Career & income", ["resume", "career", "job", "freelance", "income",
     "revenue", "monetize", "merchandise"]),
    ("DevOps & repos", ["github", "repo", "git ", "sync", "deploy", "docker",
     "devops", "azure"]),
]


def classify(text):
    t = text.lower()
    scores = []
    for theme, kws in THEMES:
        hits = sum(1 for k in kws if k in t)
        if hits:
            scores.append((hits, theme))
    if not scores:
        return "Other"
    scores.sort(reverse=True)
    return scores[0][1]


rows = conn.execute(
    "SELECT id, tool, title, category, message_count, project_path FROM sessions "
    "ORDER BY message_count DESC").fetchall()

by_theme = defaultdict(list)
for r in rows:
    # gather aim signal: title + first 2 user messages
    msgs = conn.execute(
        "SELECT content_text FROM messages WHERE session_fk=? AND role='user' "
        "AND length(content_text)>20 ORDER BY seq LIMIT 2",
        (r["id"],)).fetchall()
    aim_text = (r["title"] or "") + " || " + " || ".join(
        (m["content_text"] or "")[:300] for m in msgs)
    theme = classify(aim_text)
    first = msgs[0]["content_text"][:250].replace("\n", " ") if msgs else "(no instructions)"
    by_theme[theme].append({
        "id": r["id"], "tool": r["tool"], "title": r["title"],
        "msgs": r["message_count"], "aim": first,
        "project": r["project_path"] or "",
    })

lines = ["# MASTER AIMS REPORT - Every AI Session Analyzed", "",
         f"Total sessions analyzed: {len(rows)}", "",
         "Extracted from: Hermes, Goose, Codex, Claude Code, Gemini, Z.AI, "
         "Codeium, OpenClaw, Trae, Copilot archives.", "",
         "## LIFE GOALS SYNTHESIS", "",
         "From the user's own memory files + 92 instruction files:", "",
         "1. **Become a billionaire polymath** - build/automate/create/deploy at elite speed",
         "2. **Master Healthcare IT** - FHIR/ONC expert track (version migration work)",
         "3. **Build an AI Super App empire** - OneAgent/super-agent that merges everything",
         "4. **Never lose knowledge** - session capture, backups, master prompts",
         "5. **Automate all repetitive work** - scraping, reporting, DevOps",
         "6. **Create content/media products** - novels, music, blogs, courses",
         "7. **Learn relentlessly** - Udemy autonomous learning systems",
         "", "---", ""]

order = sorted(by_theme.items(), key=lambda kv: -sum(s["msgs"] for s in kv[1]))
for theme, sessions in order:
    total_msgs = sum(s["msgs"] for s in sessions)
    lines.append(f"## THEME: {theme}")
    lines.append(f"Sessions: {len(sessions)} | Total messages: {total_msgs} | "
                 f"Effort share: {total_msgs*100//max(1,sum(sum(s['msgs'] for s in v) for _,v in by_theme.items()))}%")
    lines.append("")
    for s in sessions[:15]:
        lines.append(f"### [{s['tool']}] {s['title'] or '(untitled)'} ({s['msgs']} msgs)")
        if s["project"]:
            lines.append(f"- Project path: `{s['project']}`")
        lines.append(f"- AIM: {s['aim']}")
        lines.append("")

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print(f"Wrote {OUT}")
print(f"\nTheme breakdown:")
for theme, sessions in order:
    tm = sum(s["msgs"] for s in sessions)
    print(f"  {theme}: {len(sessions)} sessions, {tm} msgs")
