"""Categorization + smart renaming.

Reads each session's messages and derives:
- category: an intent/domain bucket (FHIR, web-app, data, automation, research, ...)
- tags:     notable keywords
- title:    a meaningful, human name based on the FIRST user instruction and
            the project it belongs to.

All heuristics run offline (no API cost) and are overridable in the UI.
"""

import os
import re
import sqlite3

from core.sync import get_conn

# Domain keywords -> category. Order matters: first match wins.
CATEGORY_RULES = [
    ("FHIR", ["fhir", "hl7", "smart on fhir", "uscdi", "ecr", "cdc", "ehr",
              "search parameter", "curemd", "smiledr", "encounter context",
              "group cohort", "provenance", "bundle", "resource mapping"]),
    ("web-app", ["react", "next.js", "nextjs", "frontend", "website", "portal",
                 "dashboard", "web app", "ui", "landing page", "tailwind",
                 "css", "html", "javascript", "typescript", "spa"]),
    ("backend-api", ["api", "flask", "fastapi", "django", "rest", "endpoint",
                     "graphql", "server", "backend", "database schema", "sql",
                     "postgres", "mysql", "sqlite", "microservice"]),
    ("automation", ["automate", "automation", "script", "cron", "scheduled",
                    "task scheduler", "batch", "workflow", "pipeline",
                    "watcher", "monitor", "scrape", "scraper", "bot"]),
    ("data", ["csv", "excel", "xlsx", "data", "mapping", "etl", "pandas",
              "dataframe", "spreadsheet", "dataset", "analysis", "query"]),
    ("devops", ["docker", "kubernetes", "k8s", "deploy", "ci/cd", "github actions",
                "terraform", "aws", "azure", "gcp", "linux", "bash", "shell",
                "nginx", "ssh", "server setup"]),
    ("research", ["research", "paper", "arxiv", "literature", "survey", "study",
                  "academic", "review", "compare", "analysis of"]),
    ("music", ["music", "song", "audio", "sun", "melody", "beat", "lyrics",
               "sound", "spotify", "production"]),
    ("learning", ["tutorial", "learn", "course", "udemy", "lesson", "practice",
                  "exercises", "basics", "guide", "how to"]),
    ("docs", ["documentation", "readme", "doc", "spec", "write-up", "changelog"]),
    ("agent", ["agent", "multi-agent", "orchestration", "subagent", "llm",
               "prompt engineering", "openclaw", "goose", "claude", "codex",
               "autonomous"]),
    ("general", []),
]

# Stop-words removed when building a title from the first user message.
TITLE_STOPWORDS = {
    "please", "pls", "hey", "hello", "hi", "can", "could", "would", "will",
    "want", "need", "i", "me", "my", "the", "a", "an", "and", "or", "to", "of",
    "in", "on", "for", "with", "you", "your", "this", "that", "it", "is", "are",
    "be", "help", "me", "make", "build", "create", "do", "etc", "kindly",
}


def _clean_keywords(rules):
    out = []
    for cat, kws in rules:
        out.append((cat, [k.lower() for k in kws]))
    return out


CATEGORY_RULES_LOWER = _clean_keywords(CATEGORY_RULES)


def categorize_text(text: str) -> tuple:
    """Return (category, confidence 0..1, matched_keywords)."""
    t = (text or "").lower()
    best_cat, best_kws = "general", []
    best_score = 0.0
    for cat, kws in CATEGORY_RULES_LOWER:
        hits = [k for k in kws if k in t]
        if hits:
            score = len(hits) / max(1, len(kws)) + min(1.0, len(hits) / 3.0)
            if score > best_score:
                best_cat, best_kws, best_score = cat, hits, score
    confidence = min(1.0, best_score)
    return best_cat, confidence, best_kws


def infer_project(project_path: str, text: str) -> str:
    """Derive a short, human project name from the working dir + text."""
    if project_path:
        base = os.path.basename(os.path.normpath(project_path))
        if base and not base.startswith(("C:", "D:", "/")):
            return base
        # fall back to parent dir name
        parent = os.path.basename(os.path.dirname(os.path.normpath(project_path)))
        if parent:
            return parent
    return ""


def build_title(session_row, first_user_text: str) -> str:
    """Build a meaningful title from project + first instruction."""
    project = infer_project(session_row.get("project_path") or "",
                            first_user_text or "")
    if first_user_text:
        title = _summarize_first_prompt(first_user_text, max_words=8)
        if project and project.lower() not in title.lower():
            return f"{project}: {title}"
        return title or project or "Untitled session"
    return project or "Untitled session"


def _summarize_first_prompt(text: str, max_words: int = 8) -> str:
    """Condense the first user prompt into a short title phrase."""
    t = text.strip()
    # Cut at likely sentence enders
    for sep in ("\n\n", ". ", "? ", "! ", "\n"):
        idx = t.find(sep)
        if 0 < idx < 250:
            t = t[:idx]
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'\-_/]*", t)
    filtered = [w for w in words if w.lower() not in TITLE_STOPWORDS]
    if not filtered:
        filtered = words
    phrase = " ".join(filtered[:max_words])
    return phrase[:120] or "Untitled session"


def enrich_all_sessions(dry_run: bool = False) -> dict:
    """Re-categorize and re-title every session that lacks a category/title.

    Returns a summary dict.
    """
    conn = get_conn()
    updated = 0
    rows = conn.execute(
        "SELECT s.id, s.title, s.project_path, s.category, s.tags, "
        "s.started_at, s.message_count FROM sessions s").fetchall()
    for row in rows:
        first_user = conn.execute(
            "SELECT content_text FROM messages WHERE session_fk=? AND role='user' "
            "AND content_text IS NOT NULL AND content_text != '' "
            "ORDER BY seq, id LIMIT 1", (row["id"],)).fetchone()
        first_text = first_user["content_text"] if first_user else ""
        cat, conf, kws = categorize_text(
            (first_text or "") + " " + (row["title"] or ""))
        tags = ", ".join(kws[:6])
        new_title = build_title(dict(row), first_text) if not row["title"] \
            else row["title"]
        if not dry_run:
            conn.execute(
                "UPDATE sessions SET category=?, category_confidence=?, tags=?, title=? "
                "WHERE id=?",
                (cat, round(conf, 3), tags, new_title, row["id"]))
            updated += 1
    conn.commit()
    conn.close()
    return {"updated": updated}


def get_connection():
    return get_conn()
