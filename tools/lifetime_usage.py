"""Lifetime token usage across every AI tool on this PC.

Sources:
1. Hermes state.db  - token/cost columns if present, else estimate from messages
2. Hub DB           - sessions already have cost data ($10.86 / 1,239 calls computed earlier)
3. Claude Code jsonl - usage fields in raw jsonl (quarantined)
4. Codex rollouts    - token_count events in raw jsonl (quarantined)
5. Goose exports     - message counts (no token data)
"""
import sqlite3
import os
import glob
import json
import re

import os
HOME = os.environ.get("ASH_HOME") or str(__import__("pathlib").Path.home())
report = []


def add(tool, tokens_in, tokens_out, calls, note=""):
    report.append({
        "tool": tool,
        "input_tokens": tokens_in,
        "output_tokens": tokens_out,
        "api_calls": calls,
        "note": note,
    })


def fmt(n):
    if n is None:
        return "?"
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


# ---------- 1. Hermes live DB ----------
hermes_db = os.path.join(HOME, r"AppData\Local\hermes\state.db")
try:
    c = sqlite3.connect(f"file:{hermes_db}?mode=ro", uri=True)
    cols = {r[1] for r in c.execute("PRAGMA table_info(sessions)")}
    msgs_cols = set()
    if os.path.isdir(os.path.join(HOME, "AppData/Local/hermes")):
        try:
            msgs_cols = {r[1] for r in c.execute("PRAGMA table_info(messages)")}
        except sqlite3.OperationalError:
            pass
    ti = to = 0
    for col in ("input_tokens", "prompt_tokens", "total_tokens"):
        if col in cols:
            v = c.execute(f"SELECT SUM({col}) FROM sessions").fetchone()[0] or 0
            ti += v
    tok_calls = None
    if "api_calls" in cols:
        tok_calls = c.execute("SELECT SUM(api_calls) FROM sessions").fetchone()[0]
    n_sess = c.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    n_msgs = c.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    add("Hermes (live)", ti, 0, tok_calls or n_sess,
        f"{n_sess} sessions / {n_msgs} messages" +
        ("" if ti else " - no token columns in schema"))
    c.close()
except Exception as e:
    add("Hermes (live)", None, None, None, f"error: {e}")

# ---------- 2. Claude Code quarantined jsonl ----------
cc_total_in = cc_total_out = cc_calls = 0
cc_files = glob.glob(
    os.path.join(HOME, r"session-migration-backup-20260822\quarantine\*.jsonl"))
for fp in cc_files:
    try:
        with open(fp, encoding="utf-8", errors="replace") as f:
            for line in f:
                if cc_calls == 0 and '"usage"' not in line and "token" not in line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                msg = d.get("message") or {}
                usage = msg.get("usage") or d.get("usage")
                if usage:
                    cc_calls += 1
                    cc_total_in += usage.get("input_tokens", 0) or 0
                    cc_total_out += usage.get("output_tokens", 0) or 0
                elif "token_count" in str(d)[:200]:
                    cc_calls += 1
    except OSError:
        pass
add("Claude Code", cc_total_in, cc_total_out, cc_calls,
    f"{len(cc_files)} jsonl files scanned")

# ---------- 3. Codex rollouts (quarantined) ----------
cx_in = cx_out = cx_calls = 0
cx_files = glob.glob(
    os.path.join(HOME, r"session-migration-backup-20260822\quarantine\codex-sessions\*.jsonl"))
for fp in cx_files:
    try:
        with open(fp, encoding="utf-8", errors="replace") as f:
            for line in f:
                if "token" not in line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                info = d.get("payload") or d
                tc = info.get("token_count") or info.get("usage")
                if isinstance(tc, dict):
                    cx_calls += 1
                    cx_in += tc.get("input_tokens", 0) or 0
                    cx_out += tc.get("output_tokens", 0) or 0
    except OSError:
        pass
add("Codex", cx_in, cx_out, cx_calls, f"{len(cx_files)} rollout files")

# ---------- 4. Hub DB cost data (computed earlier) ----------
hub_db = os.path.join(HOME, r"ai-session-hub\db\session_hub.db")
try:
    c = sqlite3.connect(f"file:{hub_db}?mode=ro", uri=True)
    cols = {r[1] for r in c.execute("PRAGMA table_info(sessions)")}
    if "cost_usd" in cols:
        tot_cost = c.execute(
            "SELECT SUM(cost_usd) FROM sessions").fetchone()[0] or 0
        tot_calls = c.execute(
            "SELECT SUM(api_calls) FROM sessions").fetchone()[0] or 0
        tin = c.execute(
            "SELECT SUM(input_tokens) FROM sessions").fetchone()[0] or 0
        tout = c.execute(
            "SELECT SUM(output_tokens) FROM sessions").fetchone()[0] or 0
        add("Hub-tracked (Hermes history)", tin, tout, tot_calls,
            f"tracked cost ${tot_cost:.2f}")
    c.close()
except Exception as e:
    add("Hub DB", None, None, None, f"error: {e}")

# ---------- 5. Goose (message counts only - no token data in exports) ----------
goose_dir = os.path.join(
    HOME, r"session-migration-backup-20260822\quarantine\goose")
goose_msgs = 0
for fp in glob.glob(os.path.join(goose_dir, "*.json")):
    try:
        with open(fp, encoding="utf-8") as f:
            d = json.load(f)
        goose_msgs += len(d.get("conversation") or [])
    except (OSError, json.JSONDecodeError):
        pass
add("Goose", None, None, None,
    f"{goose_msgs} messages - exports contain no token counts")

# ---------- Print ----------
print("=" * 78)
print("LIFETIME AI TOKEN & API USAGE (all discoverable sources)")
print("=" * 78)
ti_sum = to_sum = call_sum = 0
have_tokens = False
for r in report:
    print(f"\n{r['tool']}")
    print(f"  input tokens : {fmt(r['input_tokens'])}")
    print(f"  output tokens: {fmt(r['output_tokens'])}")
    print(f"  api calls    : {fmt(r['api_calls'])}")
    if r["note"]:
        print(f"  note         : {r['note']}")
    if r["input_tokens"]:
        have_tokens = True
        ti_sum += r["input_tokens"] or 0
        to_sum += r["output_tokens"] or 0
    if r["api_calls"]:
        call_sum += r["api_calls"] or 0

print()
print("=" * 78)
if have_tokens:
    print(f"TOTAL verified: {fmt(ti_sum)} in / {fmt(to_sum)} out | "
          f"~{call_sum} api calls")
else:
    print(f"API calls found: ~{call_sum} (most tools do not record token counts)")
print("=" * 78)
