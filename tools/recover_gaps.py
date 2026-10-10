"""Content-based coverage check + recovery.

ID matching is unreliable (Hermes renames Claude/Codex imports). Instead take
the first substantive user text from each quarantined session file and search
Hermes' message text for it. Anything genuinely absent gets converted+imported.
"""
import glob
import json
import os
import sqlite3
import subprocess

HOME = r"C:\Users\LOQ"
BASE = os.path.join(HOME, "harness-migration")
HERMES = os.path.join(HOME, r"AppData\Local\hermes\state.db")
OUT = os.path.join(BASE, "converted", "recovered")
os.makedirs(OUT, exist_ok=True)

c = sqlite3.connect(f"file:{HERMES}?mode=ro", uri=True)
print("loading Hermes message index...")
BLOBS = []
for (txt,) in c.execute(
        "SELECT substr(content,1,120) FROM messages WHERE "
        "LENGTH(COALESCE(content,''))>40 LIMIT 400000"):
    if txt:
        BLOBS.append(txt.strip().replace("\n", " ")[:70])
c.close()
BLOB = " ||| ".join(BLOBS)
print(f"  indexed {len(BLOBS)} message heads")


def already_in_hermes(text):
    key = (text or "").strip().replace("\n", " ")[:70]
    return len(key) > 25 and key in BLOB


def qdirs():
    return sorted(glob.glob(os.path.join(BASE, "quarantine-*")))


def qfiles(store, exts):
    out = []
    for qd in qdirs():
        p = os.path.join(qd, store)
        if not os.path.isdir(p):
            continue
        for root, _, names in os.walk(p):
            for n in names:
                if n.endswith(exts):
                    out.append(os.path.join(root, n))
    return out


def safe(s):
    return "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in str(s))[:56]


def import_jsonl(rows, name):
    """rows: list[(role, text)] -> write + import. Returns 'imported'/'skip'."""
    rows = [(r, t) for r, t in rows if t and str(t).strip()]
    if not rows:
        return "skip"
    fp = os.path.join(OUT, f"{safe(name)}.jsonl")
    with open(fp, "w", encoding="utf-8") as f:
        for role, text in rows:
            rr = role if role in ("user", "assistant") else "user"
            f.write(json.dumps({"type": rr, "message": {"role": rr,
                       "content": str(text)[:40000]}}, ensure_ascii=False) + "\n")
    try:
        r = subprocess.run(["hermes", "sessions", "import", "--from", "claude",
                            fp.replace("\\", "/")],
                           capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        return "fail"
    return "imported" if "Imported" in (r.stdout + r.stderr) else "fail"


# ---------- Claude history.jsonl ----------
print("\n=== claude_history/history.jsonl ===")
for fp in qfiles("claude_history", (".jsonl",)):
    rows = []
    with open(fp, encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            txt = d.get("display") or d.get("prompt") or d.get("text") or ""
            if txt:
                rows.append(("user", txt))
    first = rows[0][1] if rows else ""
    if already_in_hermes(first):
        print("  already covered:", os.path.basename(fp))
        continue
    print(f"  {len(rows)} prompts ->", import_jsonl(rows, "claude_history"))

# ---------- Claude projects ----------
print("\n=== claude_projects ===")
for fp in qfiles("claude_projects", (".jsonl",)):
    rows = []
    with open(fp, encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            m = d.get("message") or {}
            ct = m.get("content")
            if isinstance(ct, list):
                ct = "\n".join(x.get("text", "") for x in ct
                               if isinstance(x, dict) and x.get("type") == "text")
            if ct and str(ct).strip():
                rows.append((m.get("role", "user"), str(ct)))
    first = next((t for r, t in rows if r == "user"), "")
    if already_in_hermes(first):
        print("  already covered:", os.path.basename(fp)[:40])
        continue
    print(f"  {len(rows)} msgs ->",
          import_jsonl(rows, "claude_" + os.path.basename(fp)[:20]))

# ---------- Codex rollouts ----------
print("\n=== codex_sessions ===")
for fp in qfiles("codex_sessions", (".jsonl",)):
    rows = []
    with open(fp, encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            p = d.get("payload") or d
            if not isinstance(p, dict):
                continue
            ct = p.get("content") or p.get("text") or p.get("message")
            if isinstance(ct, list):
                ct = "\n".join(x.get("text", "") for x in ct
                               if isinstance(x, dict))
            if ct and str(ct).strip():
                rows.append((p.get("role") or "user", str(ct)))
    first = next((t for r, t in rows if r == "user"), "")
    if already_in_hermes(first):
        print("  already covered:", os.path.basename(fp)[:40])
        continue
    print(f"  {len(rows)} msgs ->",
          import_jsonl(rows, "codex_" + os.path.basename(fp)[:20]))

# ---------- Z.AI logs ----------
print("\n=== zai_logs ===")
for fp in qfiles("zai_logs", (".log",)):
    txt = open(fp, encoding="utf-8", errors="replace").read()
    if len(txt.strip()) < 50:
        continue
    if already_in_hermes(txt):
        print("  already covered:", os.path.basename(fp)[:40])
        continue
    print(f"  {len(txt)} chars ->",
          import_jsonl([("user", txt[:60000])],
                       "zai_" + os.path.basename(fp)[:20]))
