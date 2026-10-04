"""Round 2 for Antigravity: the store REGENERATED after quarantine.

1. Find every brain/<cid> transcript.jsonl on disk now.
2. Convert ones we have not already converted (dir = converted/antigravity_transcripts).
3. Import the new ones into Hermes.
4. Then the caller re-quarantines the whole directory.
"""
import glob
import json
import os
import sqlite3
import subprocess

HOME = r"C:\Users\LOQ"
BRAIN = os.path.join(HOME, r".gemini\antigravity\brain")
OUT = r"C:\Users\LOQ\harness-migration\converted\antigravity_transcripts"
HERMES_DB = os.path.join(HOME, r"AppData\Local\hermes\state.db")
os.makedirs(OUT, exist_ok=True)

# titles from summaries db if present
titles = {}
sumdb = os.path.join(HOME, r".gemini\antigravity\conversation_summaries.db")
if os.path.exists(sumdb):
    try:
        c = sqlite3.connect(f"file:{sumdb}?mode=ro", uri=True)
        for cid, t, prev in c.execute(
                "SELECT conversation_id, title, preview FROM conversation_summaries"):
            titles[cid] = (t or "").strip() or (prev or "").strip()[:70]
        c.close()
    except sqlite3.Error:
        pass


def safe(s):
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in str(s))[:56]


def clean(t):
    t = str(t or "")
    for tag in ("USER_REQUEST", "ADDITIONAL_METADATA", "SYSTEM_MESSAGE",
                "EPHEMERAL_MESSAGE"):
        t = t.replace(f"<{tag}>", "").replace(f"</{tag}>", "")
    return t.strip()


def role_of(d):
    return "user" if ((d.get("source") or "").upper() == "USER_EXPLICIT"
                      or (d.get("type") or "").upper() == "USER_INPUT") \
        else "assistant"


# what's already converted
already = {os.path.splitext(os.path.basename(f))[0]
           for f in glob.glob(os.path.join(OUT, "*.jsonl"))}

all_tx = glob.glob(os.path.join(BRAIN, "*", ".system_generated", "logs",
                                "transcript.jsonl"))
print(f"transcripts on disk now: {len(all_tx)}   already converted: {len(already)}")

new_files = []
total_steps = 0
for fp in all_tx:
    cid = fp.split(os.sep + "brain" + os.sep)[1].split(os.sep)[0]
    if safe(cid) in already:
        continue
    turns = []
    try:
        with open(fp, encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ct = clean(d.get("content"))
                if ct:
                    turns.append((role_of(d), ct))
    except OSError:
        continue
    if not turns:
        continue  # empty transcript - nothing to lose
    total_steps += len(turns)
    path = os.path.join(OUT, f"{safe(cid)}.jsonl")
    with open(path, "w", encoding="utf-8") as f:
        for role, text in turns:
            f.write(json.dumps({"type": role, "message": {"role": role,
                       "content": text[:40000]}}, ensure_ascii=False) + "\n")
    new_files.append(path)

print(f"NEW converted: {len(new_files)} transcripts ({total_steps} steps)")

ok = fail = 0
for fp in new_files:
    try:
        r = subprocess.run(["hermes", "sessions", "import", "--from", "claude",
                            fp.replace("\\", "/")],
                           capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        fail += 1
        continue
    if "Imported" in (r.stdout + r.stderr):
        ok += 1
    else:
        fail += 1

print(f"imported: ok={ok} fail={fail}")
c = sqlite3.connect(f"file:{HERMES_DB}?mode=ro", uri=True)
print("Hermes sessions:", c.execute("SELECT COUNT(*) FROM sessions").fetchone()[0])
c.close()
