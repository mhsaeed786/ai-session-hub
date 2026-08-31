"""Audit prompt vault purity: how much role=user content is NOT real user text?"""
import sqlite3
import re
import collections

import os
DB = os.environ.get("ASH_DB") or str(__import__("pathlib").Path(__file__).resolve().parent.parent / "db" / "session_hub.db")
c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row
rows = c.execute(
    "SELECT s.tool AS tool, m.content_text AS content_text "
    "FROM messages m JOIN sessions s ON m.session_fk = s.id "
    "WHERE m.role='user' AND length(m.content_text)>15").fetchall()

patterns = collections.Counter()
examples = collections.defaultdict(list)

AGENT_SUMMARY = re.compile(
    r"^(A (call|shell|file|Python|configuration|browser|text|TODO|directory|"
    r"Playwright|tool|text replacement|file edit|Python module|Python file|"
    r"Python script|comprehensive|shell command|todo item|system)"
    r"|Created a|The (system|tool|todo|assistant|file|script|response|"
    r"Discudemy|browser)|An? (editable|integration|browser)|"
    r"Now let me run|Successfully)")

for r in rows:
    t = (r["content_text"] or "").strip()
    if t.startswith(("[System:", "[CONTEXT COMPACTION", "[OUT-OF-BAND",
                     "[PRIOR CONTEXT", "[Context from", "[IMPORTANT",
                     "[Continuing toward", "System Instruction:",
                     "[response interrupted", "<think>")):
        kind = "system/marker noise"
    elif AGENT_SUMMARY.match(t):
        kind = "agent tool-summary (goose)"
    elif t.startswith(("A tool call", "The todo", "[tool_call]", "[TOOL_CALL]")):
        kind = "tool-call echo"
    else:
        kind = "REAL user instruction"
    patterns[kind] += 1
    if len(examples[kind]) < 3:
        examples[kind].append(t[:110])

for k, v in patterns.most_common():
    print(f"{v:6d}  {k}")
    for ex in examples[k]:
        print(f"        e.g. {ex}")
