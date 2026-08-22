"""Master prompt generator.

For any session, build a compact, paste-ready prompt that either:
- RECAP:   gives a fast summary of what the session was about, or
- REPLICATE: lets you re-run / continue the same work in any other tool.

This solves "it's a pain to dig through old sessions."
"""

import re
import textwrap
from collections import Counter

from core.sync import get_conn
from core.categorize import categorize_text


def _top_themes(text: str, n: int = 8) -> list:
    """Extract the most informative keywords as 'key themes'."""
    if not text:
        return []
    STOP = {
        "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "with",
        "is", "are", "was", "were", "be", "it", "this", "that", "you", "your",
        "i", "me", "my", "we", "our", "they", "them", "please", "can", "could",
        "would", "will", "want", "need", "not", "no", "do", "does", "did",
        "have", "has", "had", "been", "being", "as", "at", "by", "from",
        "about", "into", "than", "then", "there", "their", "what", "which",
        "how", "when", "where", "who", "why", "help", "make", "build",
    }
    words = re.findall(r"[A-Za-z][A-Za-z0-9\-_]{2,}", text.lower())
    freqs = Counter(w for w in words if w not in STOP and not w.isdigit())
    # Prefer longer/more-specific words slightly
    return [w for w, _ in freqs.most_common(n)]


def _first_user_prompt(conn, session_id: str) -> str:
    row = conn.execute(
        "SELECT content_text FROM messages WHERE session_fk=? AND role='user' "
        "AND content_text IS NOT NULL AND content_text != '' "
        "ORDER BY seq, id LIMIT 1", (session_id,)).fetchone()
    return (row["content_text"] or "").strip() if row else ""


def _assistant_snippets(conn, session_id: str, n: int = 3, each: int = 160) -> list:
    rows = conn.execute(
        "SELECT content_text FROM messages WHERE session_fk=? AND role='assistant' "
        "AND content_text IS NOT NULL AND content_text != '' "
        "ORDER BY seq, id LIMIT 12", (session_id,)).fetchall()
    out = []
    for r in rows:
        t = r["content_text"].strip().replace("\n", " ")
        if t:
            out.append(t[:each])
        if len(out) >= n:
            break
    return out


def _objectives(conn, session_id: str) -> list:
    """Collect user messages that look like discrete instructions."""
    rows = conn.execute(
        "SELECT content_text FROM messages WHERE session_fk=? AND role='user' "
        "AND content_text IS NOT NULL AND content_text != '' "
        "ORDER BY seq, id LIMIT 20", (session_id,)).fetchall()
    objs = []
    for r in rows:
        t = r["content_text"].strip().replace("\n", " ")
        if t and len(t) < 400:
            objs.append(t)
    return objs


def build_master_prompt(session_id: str, mode: str = "replicate") -> str:
    """Generate a master prompt for a session.

    mode:
      'replicate' -> a paste-ready prompt that re-runs/continues the work.
      'recap'     -> a short human summary / quick recap.
    """
    conn = get_conn()
    s = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
    if not s:
        conn.close()
        return f"Session not found: {session_id}"

    first = _first_user_prompt(conn, session_id)
    all_text = " ".join(
        r["content_text"] or "" for r in conn.execute(
            "SELECT content_text FROM messages WHERE session_fk=? AND "
            "content_text IS NOT NULL", (session_id,)).fetchall())
    themes = _top_themes(all_text, 8)
    cat, _conf, _ = categorize_text(all_text)
    snippets = _assistant_snippets(conn, session_id)
    objectives = _objectives(conn, session_id)
    conn.close()

    line = "=" * 78
    lines = [line,
             f"  SESSION: {s['title'] or '(untitled)'}",
             f"  TOOL:    {s['tool']}   |   CATEGORY: {cat}",
             f"  ID:      {session_id}",
             line, ""]

    if s["project_path"]:
        lines.append(f"Project: {s['project_path']}")
    if s["started_at"]:
        lines.append(f"Started: {s['started_at']}")
    lines.append(f"Messages: {s['message_count'] or 0}")
    lines.append("")

    lines.append("OBJECTIVE (original instruction):")
    lines.append(textwrap.fill(first or "(no user message captured)", width=74,
                               initial_indent="  ", subsequent_indent="  "))
    lines.append("")

    if themes:
        lines.append("KEY THEMES:")
        lines.append("  " + ", ".join(themes))
        lines.append("")

    if objectives:
        lines.append("MAIN INSTRUCTIONS GIVEN:")
        for i, o in enumerate(objectives, 1):
            lines.append(f"  {i}. {o[:200]}")
        lines.append("")

    if snippets:
        lines.append("NOTABLE ANSWERS / OUTCOMES:")
        for snip in snippets:
            lines.append(f"  - {snip}...")
        lines.append("")

    if mode == "replicate":
        lines.append("MASTER PROMPT (paste into any tool to resume/re-run):")
        master = (
            f"Continue/resume the work from this session. Context:\n"
            f"- Objective: {first or s['title'] or 'see session'}\n"
            f"- Domain/category: {cat}\n"
            f"- Key themes: {', '.join(themes) if themes else 'n/a'}\n"
            f"- Project: {s['project_path'] or 'not recorded'}\n"
            f"Pick up where this left off and complete the stated objective. "
            f"If the original work is finished, summarize the outcome."
        )
        for w in textwrap.wrap(master, width=74, initial_indent="  ",
                               subsequent_indent="  "):
            lines.append(w)
    else:
        lines.append("QUICK RECAP:")
        recap = (
            f"This session used {s['tool']} and focused on "
            f"{cat} work: {first or s['title'] or '(no detail captured)'}. "
            f"Key themes: {', '.join(themes) if themes else 'n/a'}."
        )
        for w in textwrap.wrap(recap, width=74, initial_indent="  ",
                               subsequent_indent="  "):
            lines.append(w)

    lines.append("")
    lines.append("-" * 78)
    return "\n".join(lines)
