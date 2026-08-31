"""Lifetime token usage - EXACT where recorded, tiktoken-estimated elsewhere.

Sources:
1. Hermes state.db   - exact (input/output/cache/reasoning + cost columns)
2. Goose exports     - exact (total/input/output/accumulated)
3. Claude Code jsonl - exact (usage events)
4. Codex rollouts    - tiktoken estimate (no recorded stats)
5. Hermes WSL backup - exact (older db has token cols? probe)
Note: data migrated from old PC is included, so this IS the lifetime archive.
"""
import sqlite3
import os
import glob
import json

import tiktoken

import os
HOME = os.environ.get("ASH_HOME") or str(__import__("pathlib").Path.home())
enc = tiktoken.get_encoding("o200k_base")


def count(text):
    if not text:
        return 0
    return len(enc.encode(text, disallowed_special=()))


def fmt(n):
    if n is None:
        return "?"
    if n >= 1_000_000_000:
        return f"{n/1_000_000_000:.2f}B"
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


results = []

# ---------- 1. Hermes live (exact) ----------
db = os.path.join(HOME, r"AppData\Local\hermes\state.db")
c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
r = c.execute("""
    SELECT SUM(input_tokens), SUM(output_tokens), SUM(cache_read_tokens),
           SUM(cache_write_tokens), SUM(reasoning_tokens),
           SUM(estimated_cost_usd), SUM(actual_cost_usd), COUNT(*)
    FROM sessions""").fetchone()
h_in, h_out, h_cr, h_cw, h_reason, h_est, h_act, h_n = r
results.append(("Hermes (recorded)", h_in, h_out,
                f"{h_n} sessions | cache_r={fmt(h_cr)} cache_w={fmt(h_cw)} "
                f"reasoning={fmt(h_reason)} | est ${h_est or 0:.2f} / "
                f"actual ${h_act or 0:.2f}"))

# ---------- 2. Goose (recorded) ----------
g_in = g_out = g_n = 0
for fp in glob.glob(os.path.join(
        HOME, r"session-migration-backup-20260822\quarantine\goose\*.json")):
    try:
        with open(fp, encoding="utf-8") as f:
            d = json.load(f)
        g_n += 1
        g_in += d.get("input_tokens") or 0
        g_out += d.get("output_tokens") or 0
    except (OSError, json.JSONDecodeError):
        pass
results.append(("Goose (recorded)", g_in, g_out, f"{g_n} sessions"))

# ---------- 3. Claude Code (recorded) ----------
cc_in = cc_out = cc_calls = 0
for fp in glob.glob(os.path.join(
        HOME, r"session-migration-backup-20260822\quarantine\*.jsonl")):
    with open(fp, encoding="utf-8", errors="replace") as f:
        for line in f:
            if '"usage"' not in line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            usage = (d.get("message") or {}).get("usage") or d.get("usage")
            if usage:
                cc_calls += 1
                cc_in += usage.get("input_tokens", 0) or 0
                cc_out += usage.get("output_tokens", 0) or 0
results.append(("Claude Code (recorded)", cc_in, cc_out,
                f"{cc_calls} api calls"))

# ---------- 4. Codex rollouts (tiktoken estimate from raw content) ----------
cx_tok = cx_calls = 0
cx_files = glob.glob(os.path.join(
    HOME, r"session-migration-backup-20260822\quarantine\codex-sessions\*.jsonl"))
for fp in cx_files:
    with open(fp, encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            payload = d.get("payload") or {}
            # user/assistant messages in event_msg / response_item payloads
            ptype = payload.get("type", d.get("type", ""))
            if ptype in ("user_message", "agent_message", "message",
                         "user", "assistant"):
                content = payload.get("message") or payload.get("content") or ""
                if isinstance(content, list):
                    content = " ".join(
                        x.get("text", "") if isinstance(x, dict) else str(x)
                        for x in content)
                if content:
                    cx_tok += count(str(content))
                if ptype in ("agent_message", "assistant"):
                    cx_calls += 1
results.append(("Codex (tiktoken est.)", cx_tok, None,
                f"{len(cx_files)} rollouts, ~{cx_calls} assistant turns"))

# ---------- 5. Hermes WSL backup (exact if cols exist, else tiktoken) ----------
wsl_db = os.path.join(HOME, r"hermes-sessions\hermes-wsl\state.db")
if os.path.exists(wsl_db):
    wc = sqlite3.connect(f"file:{wsl_db}?mode=ro", uri=True)
    wcols = {r[1] for r in wc.execute("PRAGMA table_info(sessions)")}
    if "input_tokens" in wcols:
        wr = wc.execute("SELECT SUM(input_tokens), SUM(output_tokens) "
                        "FROM sessions").fetchone()
        results.append(("Hermes WSL backup (recorded)", wr[0] or 0,
                        wr[1] or 0, "older schema with token cols"))
    else:
        # tiktoken over messages
        wtok = 0
        mcols = {r[1] for r in wc.execute("PRAGMA table_info(messages)")}
        if "content" in mcols or "content_text" in mcols:
            col = "content_text" if "content_text" in mcols else "content"
            for (txt,) in wc.execute(f"SELECT {col} FROM messages"):
                wtok += count(txt)
        results.append(("Hermes WSL backup (tiktoken est.)", wtok, None,
                        "no token cols - estimated"))
    wc.close()

# ---------- 6. Z.AI logs (tiktoken estimate of conversation content) ----------
zai_tok = 0
zai_files = glob.glob(os.path.join(
    HOME, r"session-migration-backup-20260822\quarantine\zai\*.log"))
# zai logs are MCP server logs, mostly boilerplate - count anyway (honest)
for fp in zai_files[:5]:
    with open(fp, encoding="utf-8", errors="replace") as f:
        zai_tok += count(f.read())
results.append(("Z.AI logs (tiktoken est., 5 of "
                f"{len(zai_files)} sampled)", zai_tok, None,
                "server logs, not conversations"))

# ---------- Totals ----------
print("=" * 80)
print("LIFETIME AI TOKEN USAGE (machine archive = full history incl. old PC)")
print("=" * 80)
tot_in = tot_out = 0
recorded_in = 0
for name, i, o, note in results:
    print(f"\n{name}")
    print(f"  input : {fmt(i)}{'  (tiktoken estimate)' if 'est' in name else '  (recorded by tool)'}")
    if o is not None:
        print(f"  output: {fmt(o)}")
    print(f"  {note}")
    if i:
        tot_in += i
        if "est" not in name:
            recorded_in += i
    if o:
        tot_out += o

print()
print("=" * 80)
print(f"TOTAL INPUT : {fmt(tot_in)}")
print(f"TOTAL OUTPUT: {fmt(tot_out)}")
print(f"GRAND TOTAL : {fmt(tot_in + tot_out)}")
print(f"  of which tool-recorded: {fmt(recorded_in)}")
print(f"  tiktoken-estimated   : {fmt(tot_in - recorded_in)}")
print("=" * 80)
