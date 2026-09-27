"""Antigravity: recover conversations from conversation_summaries.db.

The db holds conversation_id/title/preview/step_count/workspace/status.
Full step text lives in the protobuf .pb files keyed by conversation id.
We build one session per conversation using preview + any recoverable steps.
"""
import glob
import json
import os
import re
import sqlite3

HOME = r"C:\Users\LOQ"
BASE = os.path.join(HOME, r".gemini\antigravity")
OUT = r"C:\Users\LOQ\harness-migration\converted\antigravity"
os.makedirs(OUT, exist_ok=True)


def safe(s):
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in str(s))[:56]


# Load raw pb bytes per conversation (they may embed the conv id)
pb_blobs = []
for fp in glob.glob(os.path.join(BASE, "**", "*.pb"), recursive=True):
    with open(fp, "rb") as f:
        pb_blobs.append((fp, f.read()))


def text_from_pb(raw, conv_id):
    """Pull readable human/assistant text lines tied to a conversation."""
    txt = raw.decode("utf-8", errors="ignore")
    # keep only lines that look like natural language, not binary noise
    lines = []
    for m in re.finditer(r'[\x20-\x7e\u00a0-\uffff]{25,600}', txt):
        s = m.group(0).strip()
        if not s or s.count(" ") < 3:
            continue
        if re.search(r'[{}<>\\]{3,}', s):      # skip json/proto noise
            continue
        if len(s) < 30:
            continue
        lines.append(s)
    return lines[:400]


db = os.path.join(BASE, "conversation_summaries.db")
c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
c.row_factory = sqlite3.Row
rows = c.execute("SELECT * FROM conversation_summaries").fetchall()
c.close()
print(f"conversations in db: {len(rows)}")

n_ok = 0
for r in rows:
    cid = r["conversation_id"]
    title = (r["title"] or "").strip()
    preview = (r["preview"] or "").strip()
    steps = r["step_count"] or 0
    # title fallback: first ~8 words of preview
    if not title:
        title = (preview[:70] + "...") if preview else f"conversation {cid[:8]}"

    turns = []
    if preview:
        turns.append(("user", preview))
    # attach any pb text we can recover
    for fp, raw in pb_blobs:
        if cid.encode() in raw or cid[:8].encode() in raw:
            for line in text_from_pb(raw, cid):
                turns.append(("assistant", line))
            break

    if not turns:
        turns = [("user", preview or title)]

    path = os.path.join(OUT, f"{safe(cid)}.jsonl")
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"type": "user",
                            "message": {"role": "user",
                                        "content": turns[0][1][:9000]}},
                           ensure_ascii=False) + "\n")
        for role, text in turns[1:]:
            f.write(json.dumps({"type": "assistant",
                                "message": {"role": "assistant",
                                            "content": text[:40000]}},
                               ensure_ascii=False) + "\n")
    n_ok += 1
    meta = {
        "conversation_id": cid, "title": title, "step_count": steps,
        "status": r["status"], "source": r["source"],
        "workspace": (r["workspace_uris"] or "")[:200],
        "last_modified": r["last_modified_time"],
    }
    with open(path + ".meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1)

print(f"wrote {n_ok} antigravity conversation files")

# report what we know
for r in sorted(rows, key=lambda x: -(x["step_count"] or 0))[:10]:
    t = (r["title"] or (r["preview"] or "")[:50]).strip()
    print(f"  {r['step_count']:5d} steps  {t[:60]}")
