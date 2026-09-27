"""Convert LIVE harness stores -> Claude-Code JSONL (the format Hermes imports).

Sources handled:
  * Goose live sessions.db  (83 sessions / 11,053 msgs)  <- never fully migrated
  * Antigravity (.gemini/antigravity/*.json + summaries db)
  * opencode storage, zcode, mimocode, codex_db, khoj/plandex/metagpt json
  * anything else that yields (session_id, title, messages)

Writes to: C:\\Users\\LOQ\\harness-migration\\converted\\<tool>\\<sid>.jsonl
Never modifies any source.
"""
import glob
import json
import os
import sqlite3

HOME = r"C:\Users\LOQ"
OUT = r"C:\Users\LOQ\harness-migration\converted"


def safe(s):
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in str(s))[:60]


def write_session(tool, sid, title, messages, meta=None):
    """messages: list of (role, text). Skips empty turns."""
    d = os.path.join(OUT, tool)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"{safe(sid)}.jsonl")
    written = 0
    with open(path, "w", encoding="utf-8") as f:
        first_user = next((t for r, t in messages if r == "user"
                           and t.strip()), None)
        if first_user and title:
            # seed the title with the first real user line (Hermes reads this)
            f.write(json.dumps({
                "type": "user",
                "message": {"role": "user", "content": first_user[:9000]},
            }, ensure_ascii=False) + "\n")
            written += 1
        for role, text in messages:
            if not text or not text.strip():
                continue
            if role == "user" and first_user and text == first_user:
                continue  # already seeded
            r = role if role in ("user", "assistant") else "user"
            f.write(json.dumps({
                "type": r,
                "message": {"role": r, "content": text[:40000]},
            }, ensure_ascii=False) + "\n")
            written += 1
    if written == 0:
        os.remove(path)
        return None
    return path, written


# ============ GOOSE LIVE ============
def convert_goose():
    src = os.path.join(HOME, r"AppData\Roaming\Block\goose\data\sessions\sessions.db")
    if not os.path.exists(src):
        return 0
    c = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    sessions = c.execute("SELECT * FROM sessions ORDER BY created_at").fetchall()
    n_ok = 0
    for s in sessions:
        msgs = c.execute(
            "SELECT role, content_json FROM messages WHERE session_id=? "
            "ORDER BY created_timestamp, id", (s["id"],)).fetchall()
        turns = []
        for m in msgs:
            raw = m["content_json"] or ""
            try:
                blocks = json.loads(raw)
            except json.JSONDecodeError:
                blocks = raw
            texts = []
            if isinstance(blocks, list):
                for b in blocks:
                    if isinstance(b, dict) and b.get("type") == "text":
                        texts.append(b.get("text", ""))
                    elif isinstance(b, str):
                        texts.append(b)
            elif isinstance(blocks, str):
                texts.append(blocks)
            text = "\n".join(t for t in texts if t).strip()
            if text:
                turns.append((m["role"], text))
        title = s["name"] or f"goose-{s['id']}"
        res = write_session("goose", f"goose_live_{s['id']}",
                            f"Goose - {title}", turns)
        if res:
            n_ok += 1
    c.close()
    return n_ok


# ============ ANTIGRAVITY ============
def convert_antigravity():
    n = 0
    base = os.path.join(HOME, r".gemini\antigravity")
    for fp in glob.glob(os.path.join(base, "**", "*.json"), recursive=True):
        try:
            with open(fp, encoding="utf-8", errors="replace") as f:
                d = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        turns = []
        title = None
        cid = os.path.splitext(os.path.basename(fp))[0]
        if isinstance(d, dict):
            title = d.get("name") or d.get("title") or d.get("summary")
            for key in ("messages", "conversation", "history", "turns"):
                items = d.get(key)
                if isinstance(items, list):
                    for it in items:
                        if not isinstance(it, dict):
                            continue
                        role = it.get("role") or it.get("author") or "user"
                        content = (it.get("content") or it.get("text")
                                   or it.get("message") or "")
                        if isinstance(content, list):
                            content = " ".join(
                                x.get("text", "") if isinstance(x, dict)
                                else str(x) for x in content)
                        if content:
                            turns.append((str(role), str(content)))
                    if turns:
                        break
        elif isinstance(d, list):
            for it in d:
                if isinstance(it, dict):
                    role = it.get("role", "user")
                    content = it.get("content") or it.get("text") or ""
                    if isinstance(content, list):
                        content = " ".join(
                            x.get("text", "") if isinstance(x, dict)
                            else str(x) for x in content)
                    if content:
                        turns.append((role, str(content)))
        if not turns:
            continue
        res = write_session("antigravity", f"ag_{cid}",
                            f"Antigravity - {title or cid}", turns)
        if res:
            n += 1
    return n


# ============ GENERIC: any sqlite with sessions+messages ============
def convert_generic_sqlite(path, tool, sess_table="sessions",
                           msg_table="messages", id_col="id",
                           title_cols=("name", "title", "summary"),
                           body_col="content", role_col="role"):
    n = 0
    try:
        c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        c.row_factory = sqlite3.Row
        tabs = [r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")]
        if sess_table not in tabs or msg_table not in tabs:
            c.close()
            return 0
        scols = [r[1] for r in c.execute(f"PRAGMA table_info({sess_table})")]
        mcols = [r[1] for r in c.execute(f"PRAGMA table_info({msg_table})")]
        # find the FK from messages -> sessions
        fk = next((x for x in mcols if x in ("session_id", "session_fk",
                                             "conversation_id", "thread_id",
                                             "sid")), None)
        if not fk:
            c.close()
            return 0
        scol = id_col if id_col in scols else scols[0]
        tcol = next((t for t in title_cols if t in scols), None)
        for s in c.execute(f"SELECT * FROM {sess_table}").fetchall():
            rows = c.execute(
                f"SELECT * FROM {msg_table} WHERE {fk}=? ORDER BY rowid",
                (s[scol],)).fetchall()
            turns = []
            for m in rows:
                body = m[body_col] if body_col in mcols else (
                    m[mcols[-1]] if mcols else None)
                if body is None:
                    continue
                if isinstance(body, (bytes, bytearray)):
                    continue
                text = str(body)
                if text.startswith(("[{", "{\"")):
                    try:
                        parsed = json.loads(text)
                        if isinstance(parsed, list):
                            text = "\n".join(
                                b.get("text", "") for b in parsed
                                if isinstance(b, dict))
                        elif isinstance(parsed, dict):
                            text = (parsed.get("text")
                                    or parsed.get("content")
                                    or json.dumps(parsed))
                    except json.JSONDecodeError:
                        pass
                role = m[role_col] if role_col in mcols else "user"
                if text.strip():
                    turns.append((str(role), text))
            if not turns:
                continue
            title = s[tcol] if tcol else None
            res = write_session(tool, f"{os.path.basename(path)}_{s[scol]}",
                                f"{tool.title()} - {title or s[scol]}", turns)
            if res:
                n += 1
        c.close()
    except sqlite3.Error:
        return 0
    return n


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    print("converting...")
    g = convert_goose()
    print(f"  goose live      : {g} sessions")
    a = convert_antigravity()
    print(f"  antigravity     : {a} sessions")

    targets = [
        (r".local\share\opencode\opencode.db", "opencode", "session", "message"),
        (r".local\share\mimocode\mimocode.db", "mimocode", "sessions", "messages"),
        (r".zcode\cli\db\db.sqlite", "zcode", "sessions", "messages"),
        (r".codex\state_5.sqlite", "codexdb", "threads", "messages"),
    ]
    for pattern, tool, st, mt in targets:
        for p in glob.glob(os.path.join(HOME, pattern)):
            k = convert_generic_sqlite(p, tool, st, mt)
            print(f"  {tool:15s}: {k} sessions")

    # summary of what landed
    total = 0
    for d in glob.glob(os.path.join(OUT, "*")):
        n = len(glob.glob(os.path.join(d, "*.jsonl")))
        total += n
        print(f"  OUT {os.path.basename(d):16s} {n} files")
    print(f"TOTAL converted: {total} session files -> {OUT}")
