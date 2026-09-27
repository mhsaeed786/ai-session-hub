"""Import Antigravity transcript.jsonl files (the REAL full chat history).

Location: .gemini/antigravity/brain/<conversation-id>/.system_generated/logs/transcript.jsonl
Format:  one JSON per step {step_index, source, type, status, created_at, content}

These are the full step-by-step transcripts - far richer than the summaries db.
"""
import glob
import json
import os
import sqlite3
import subprocess

HOME = r"C:\Users\LOQ"
BRAIN = os.path.join(HOME, r".gemini\antigravity\brain")
OUT = r"C:\Users\LOQ\harness-migration\converted\antigravity_transcripts"
os.makedirs(OUT, exist_ok=True)
HERMES_DB = os.path.join(HOME, r"AppData\Local\hermes\state.db")

# conversation titles from the summaries db (if it still exists)
titles = {}
sumdb = os.path.join(HOME, r".gemini\antigravity\conversation_summaries.db")
if os.path.exists(sumdb):
    try:
        c = sqlite3.connect(f"file:{sumdb}?mode=ro", uri=True)
        for cid, t, prev, steps in c.execute(
                "SELECT conversation_id, title, preview, step_count "
                "FROM conversation_summaries"):
            titles[cid] = (t or "").strip() or (prev or "").strip()[:70]
        c.close()
    except sqlite3.Error:
        pass


def safe(s):
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in str(s))[:56]


def clean(text):
    """Strip antigravity's XML wrapper tags but keep the human text."""
    t = str(text or "")
    for tag in ("USER_REQUEST", "ADDITIONAL_METADATA",
                "SYSTEM_MESSAGE", "EPHEMERAL_MESSAGE"):
        t = t.replace(f"<{tag}>", "").replace(f"</{tag}>", "")
    return t.strip()


def role_of(step):
    src = (step.get("source") or "").upper()
    typ = (step.get("type") or "").upper()
    if src == "USER_EXPLICIT" or typ == "USER_INPUT":
        return "user"
    return "assistant"


converted = 0
total_steps = 0
for fp in glob.glob(os.path.join(BRAIN, "*", ".system_generated", "logs",
                                 "transcript.jsonl")):
    cid = fp.split(os.sep + "brain" + os.sep)[1].split(os.sep)[0]
    turns = []
    try:
        with open(fp, encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                content = clean(d.get("content"))
                if not content:
                    continue
                turns.append((role_of(d), content))
    except OSError:
        continue
    if not turns:
        continue
    total_steps += len(turns)
    title = titles.get(cid) or cid[:8]
    path = os.path.join(OUT, f"{safe(cid)}.jsonl")
    with open(path, "w", encoding="utf-8") as f:
        for role, text in turns:
            f.write(json.dumps({
                "type": role,
                "message": {"role": role, "content": text[:40000]},
            }, ensure_ascii=False) + "\n")
    converted += 1

print(f"converted {converted} antigravity transcripts ({total_steps} steps)")

# import into Hermes
ok = fail = 0
for fp in sorted(glob.glob(os.path.join(OUT, "*.jsonl"))):
    win = fp.replace("\\", "/")
    try:
        r = subprocess.run(
            ["hermes", "sessions", "import", "--from", "claude", win],
            capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        fail += 1
        continue
    out = (r.stdout + r.stderr)
    if "Imported" in out:
        ok += 1
    else:
        fail += 1

print(f"imported into Hermes: ok={ok} fail={fail}")
c = sqlite3.connect(f"file:{HERMES_DB}?mode=ro", uri=True)
print("Hermes sessions now:", c.execute("SELECT COUNT(*) FROM sessions").fetchone()[0])
c.close()
