"""Decode Antigravity's protobuf chat_state + conversation summaries.

Antigravity stores conversations in .pb files and a summaries .db.
The .pb payload is length-delimited JSON in practice - try both paths.
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
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in str(s))[:60]


def write_session(sid, title, turns):
    path = os.path.join(OUT, f"{safe(sid)}.jsonl")
    n = 0
    with open(path, "w", encoding="utf-8") as f:
        first_user = next((t for r, t in turns if r == "user" and t.strip()), None)
        if first_user:
            f.write(json.dumps({"type": "user",
                                "message": {"role": "user",
                                            "content": first_user[:9000]}},
                               ensure_ascii=False) + "\n")
            n += 1
        for role, text in turns:
            if not text.strip():
                continue
            if role == "user" and text == first_user:
                continue
            r = role if role in ("user", "assistant") else "user"
            f.write(json.dumps({"type": r,
                                "message": {"role": r, "content": text[:40000]}},
                               ensure_ascii=False) + "\n")
            n += 1
    if n == 0:
        os.remove(path)
        return None
    return path, n


def try_extract_json_blobs(raw):
    """Pull JSON objects out of a protobuf-ish byte blob."""
    out = []
    text = raw.decode("utf-8", errors="ignore")
    for m in re.finditer(r'\{"[^\n]{20,}?\}', text):
        blob = m.group(0)
        # try to extend to a balanced object
        depth = 0
        for i in range(len(blob) - 1, -1, -1):
            if blob[i] == "}":
                depth += 1
            elif blob[i] == "{":
                depth -= 1
                if depth == 0:
                    blob = blob[:i + 1]
                    break
        try:
            out.append(json.loads(blob))
        except json.JSONDecodeError:
            continue
    return out


total = 0
pbs = glob.glob(os.path.join(BASE, "**", "*.pb"), recursive=True)
print(f"antigravity .pb files: {len(pbs)}")

for fp in pbs:
    with open(fp, "rb") as f:
        raw = f.read()
    objs = try_extract_json_blobs(raw)
    for obj in objs:
        if not isinstance(obj, dict):
            continue
        # find message-ish arrays
        turns = []
        for key in ("messages", "conversation", "history", "turns", "chat"):
            items = obj.get(key)
            if isinstance(items, list):
                for it in items:
                    if not isinstance(it, dict):
                        continue
                    role = it.get("role") or it.get("author") or "user"
                    content = (it.get("content") or it.get("text")
                               or it.get("message") or it.get("body") or "")
                    if isinstance(content, list):
                        content = " ".join(
                            x.get("text", "") if isinstance(x, dict)
                            else str(x) for x in content)
                    if content and isinstance(content, str):
                        turns.append((str(role), content))
                if turns:
                    break
        if turns:
            sid = obj.get("id") or obj.get("conversationId") or \
                os.path.splitext(os.path.basename(fp))[0]
            title = obj.get("name") or obj.get("title") or sid
            r = write_session(f"ag_{sid}", f"Antigravity - {title}", turns)
            if r:
                total += 1

# conversation_summaries.db holds the titles/ids
for db in glob.glob(os.path.join(BASE, "*.db")):
    try:
        c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        tabs = [r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")]
        for t in tabs:
            cols = [r[1] for r in c.execute(f"PRAGMA table_info({t})")]
            n = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            print(f"  {os.path.basename(db)} :: {t} = {n} rows, cols={cols[:8]}")
            rows = c.execute(f"SELECT * FROM {t} LIMIT 3").fetchall()
            for r0 in rows:
                print("     ", [str(x)[:40] for x in r0][:6])
        c.close()
    except sqlite3.Error as e:
        print("  db err:", e)

print(f"\nconverted antigravity sessions: {total}")
for f in sorted(glob.glob(os.path.join(OUT, "*.jsonl")))[:5]:
    print("  ", os.path.basename(f), os.path.getsize(f), "bytes")
