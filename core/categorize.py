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

# Domain keywords -> category. More keywords, ordered by specificity.
CATEGORY_RULES = [
    ("FHIR", ["fhir", "hl7", "smart on fhir", "uscdi", "ecr", "cdc", "ehr",
              "search parameter", "healthcare org", "smiledr", "encounter context",
              "group cohort", "provenance", "bundle", "resource mapping",
              "fhir developer portal", "fhir server", "smart app",
              "fhir resource", "fhir api", "patient resource", "observation",
              "condition resource", "bundle", "trigger", "data sync",
              "fhir r4", "structure definition", "implementation guide"]),
    ("web-app", ["react", "next.js", "nextjs", "frontend", "website", "portal",
                 "dashboard", "web app", "ui", "landing page", "tailwind",
                 "css", "html", "javascript", "typescript", "spa",
                 "single page app", "component", "tailwindcss", "chakra",
                 "material ui", "bootstrap", "svelte", "vue"]),
    ("backend-api", ["api", "flask", "fastapi", "django", "rest", "endpoint",
                     "graphql", "server", "backend", "database schema", "sql",
                     "postgres", "mysql", "sqlite", "microservice",
                     "express", "nodejs", "spring boot", "api route",
                     "middleware", "authentication", "jwt", "oauth",
                     "database migration", "orm", "endpoint", "crud"]),
    ("automation", ["automate", "automation", "script", "cron", "scheduled",
                    "task scheduler", "batch", "workflow", "pipeline",
                    "watcher", "monitor", "scrape", "scraper", "bot",
                    "sync", "backup", "deploy", "ci/cd", "github actions",
                    "continuous integration", "task automation",
                    "file watcher", "file sync", "scheduled task"]),
    ("data", ["csv", "excel", "xlsx", "data", "mapping", "etl", "pandas",
              "dataframe", "spreadsheet", "dataset", "analysis", "query",
              "sql query", "data analysis", "data processing", "etl",
              "data pipeline", "data transformation", "data migration",
              "chart", "visualization", "graph", "plot", "dashboard",
              "report", "export", "import", "extract"]),
    ("devops", ["docker", "kubernetes", "k8s", "deploy", "ci/cd", "github actions",
                "terraform", "aws", "azure", "gcp", "linux", "bash", "shell",
                "nginx", "ssh", "server setup", "infrastructure", "helm",
                "container", "docker compose", "swarm", "ansible", "puppet",
                "chef", "jenkins", "gitlab ci", "circleci", "travisci",
                "monitoring", "logging", "prometheus", "grafana", "elk"]),
    ("research", ["research", "paper", "arxiv", "literature", "survey", "study",
                  "academic", "review", "compare", "analysis of", "deep dive",
                  "investigation", "explore", "understand", "learn about",
                  "find out", "what is", "how does", "comparison"]),
    ("music", ["music", "song", "audio", "sun", "melody", "beat", "lyrics",
               "sound", "spotify", "production", "compose", "record",
               "mix", "master", "track", "album", "playlist"]),
    ("learning", ["tutorial", "learn", "course", "udemy", "lesson", "practice",
                  "exercises", "basics", "guide", "how to", "teach",
                  "explain", "study", "training", "workshop", "curriculum",
                  "course", "class", "mooc"]),
    ("docs", ["documentation", "readme", "doc", "spec", "write-up", "changelog",
              "release notes", "wiki", "knowledge base", "manual", "guide",
              "instruction", "howto", "how-to", "faq", "troubleshooting",
              "runbook", "playbook", "policy", "procedure"]),
    ("agent", ["agent", "multi-agent", "orchestration", "subagent", "llm",
               "prompt engineering", "openclaw", "goose", "claude", "codex",
               "autonomous", "ai agent", "ai tool", "ai system", "chatbot",
               "large language model", "gpt", "gemini", "llama", "ollama",
               "ai assistant", "ai model", "fine-tune", "fine-tuning",
               "model training", "inference", "rag", "retrieval augmented",
               "vector", "embedding", "chromadb", "pinecone", "weaviate"]),
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
    """Return (category, confidence 0..1, matched_keywords).

    Scans the whole conversation text. Even one strong keyword hit is enough
    for a specific category — we only fall back to 'general' if NOTHING matches.
    """
    t = (text or "").lower()
    if not t.strip():
        return "general", 0.0, []
    best_cat, best_kws = "general", []
    best_score = 0.0
    for cat, kws in CATEGORY_RULES_LOWER:
        hits = [k for k in kws if k in t]
        if hits:
            # Reward multiple hits, but even 1 hit gives a usable category
            score = min(1.0, 0.4 + len(hits) * 0.2)
            if score > best_score:
                best_cat, best_kws, best_score = cat, hits, score
    return best_cat, best_score, best_kws


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

    Strategy: scan ALL user+assistant messages (capped) and pick the
    category that accumulates the most keyword hits across the whole
    conversation, then normalize. This avoids the "first message is hello"
    problem that made everything 'general'.

    Returns a summary dict.
    """
    conn = get_conn()
    updated = 0
    rows = conn.execute(
        "SELECT s.id, s.title, s.project_path, s.category, s.tags, "
        "s.started_at, s.message_count FROM sessions s").fetchall()
    for row in rows:
        # Gather text from the whole conversation (capped for speed)
        msgs = conn.execute(
            "SELECT role, content_text FROM messages WHERE session_fk=? "
            "AND content_text IS NOT NULL AND content_text != '' "
            "ORDER BY seq, id LIMIT 200", (row["id"],)).fetchall()
        all_text = " ".join((m["content_text"] or "") for m in msgs)
        title_text = _first_substantive_user(msgs)

        cat, conf, kws = categorize_text(all_text)
        tags = ", ".join(kws[:6])
        new_title = build_title(dict(row), title_text) if not row["title"] \
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


def _first_substantive_user(msgs, min_len=20):
    """Return the first user message that looks like a real instruction
    (not just 'hello' / 'hey' / 'hi')."""
    for m in msgs:
        if m["role"] != "user":
            continue
        text = (m["content_text"] or "").strip()
        if len(text) >= min_len and text.lower() not in (
                "hello", "hey", "hi", "hello!", "hey there", "hi there"):
            return text
    # Fallback: first user message of any length
    for m in msgs:
        if m["role"] == "user":
            return (m["content_text"] or "").strip()
    return ""


def get_connection():
    return get_conn()
