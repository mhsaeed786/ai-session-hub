"""Dedupe the token hunt: many dbs are copies of the same data.

Real distinct sources:
1. Hermes live state.db (139.9M in) - the WSL backups are older copies of the
   SAME sessions (2.66M in - subset), don't double count
2. Goose sessions.db in AppData/Roaming/Block - usage_ledger 294M in!
   (the quarantined goose JSONs were only 21 exports = 1M; the REAL goose
   store has the full history)
3. Codex state_5.sqlite - threads.tokens_used=18.2M
4. opencode.db - 6.7K (tiny)
5. session_model_usage table (35.7M in, 18.9M cache) - need to find which db

Careful: 'OneDrive cxp_token', 'DriveFS token', 'auth refresh_tokens' are
NOT AI tokens - exclude.
"""
import sqlite3
import os

import os
HOME = os.environ.get("ASH_HOME") or str(__import__("pathlib").Path.home())

sources = {}

# 1. Hermes live
db = os.path.join(HOME, r"AppData\Local\hermes\state.db")
c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
i, o, cr = c.execute(
    "SELECT SUM(input_tokens), SUM(output_tokens), SUM(cache_read_tokens) "
    "FROM sessions").fetchone()
sources["Hermes (live, current PC)"] = (i, o, cr, "sessions table")
# also the per-model usage table if present
try:
    tables = [r[0] for r in c.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")]
    for t in tables:
        cols = [r[1] for r in c.execute(f"PRAGMA table_info({t})")]
        if "input_tokens" in cols and t != "sessions":
            i2, o2, cr2 = c.execute(
                f"SELECT SUM(input_tokens), SUM(output_tokens), "
                f"SUM(cache_read_tokens) FROM {t}").fetchone()
            if i2 and i2 > (i or 0) * 0.5:  # significant & not subset
                sources[f"Hermes {t} table"] = (i2, o2, cr2,
                                                f"per-model breakdown")
except sqlite3.Error:
    pass
c.close()

# 2. Goose real store
db = os.path.join(HOME, r"AppData\Roaming\Block\goose\data\sessions\sessions.db")
c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
tables = [r[0] for r in c.execute(
    "SELECT name FROM sqlite_master WHERE type='table'")]
if "usage_ledger" in tables:
    i, o, t, cr = c.execute(
        "SELECT SUM(input_tokens), SUM(output_tokens), SUM(total_tokens), "
        "SUM(cache_read_tokens) FROM usage_ledger").fetchone()
    sources["Goose (usage_ledger, full history)"] = (i, o, cr,
                                                     f"total {t:,}")
s = c.execute(
    "SELECT SUM(accumulated_input_tokens), SUM(accumulated_output_tokens), "
    "SUM(accumulated_total_tokens), SUM(accumulated_cache_read_tokens) "
    "FROM sessions").fetchone()
c.close()

# 3. Codex
db = os.path.join(HOME, r".codex\state_5.sqlite")
c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
i = c.execute("SELECT SUM(tokens_used) FROM threads").fetchone()[0]
c.close()
sources["Codex (threads.tokens_used)"] = (i, None, None,
                                          "combined in+out")

# 4. opencode
db = os.path.join(HOME, r".local\share\opencode\opencode.db")
if os.path.exists(db):
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        i, o = c.execute(
            "SELECT SUM(tokens_input), SUM(tokens_output) FROM session"
        ).fetchone()
        sources["OpenCode"] = (i or 0, o or 0, None, "tiny usage")
    except sqlite3.Error:
        pass
    c.close()

# find the session_model_usage db (35.7M in) - likely a goose/cherry variant
for cand in [r"AppData\Roaming\Block\goose\data\sessions\sessions.db",
             r"AppData\Local\hermes\state.db"]:
    p = os.path.join(HOME, cand)
    if not os.path.exists(p):
        continue
    c = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    tables = [r[0] for r in c.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")]
    if "session_model_usage" in tables:
        i, o, cr = c.execute(
            "SELECT SUM(input_tokens), SUM(output_tokens), "
            "SUM(cache_read_tokens) FROM session_model_usage").fetchone()
        sources[f"session_model_usage ({cand.split(chr(92))[0]})"] = (
            i, o, cr, "per-model usage ledger")
    c.close()

print("=" * 78)
print("LIFETIME TOKEN USAGE - deduplicated, distinct sources only")
print("=" * 78)
tin = tout = tcache = 0
for name, (i, o, cr, note) in sources.items():
    print(f"\n{name}")
    print(f"  input:  {i:,}" if i else "  input:  -")
    print(f"  output: {o:,}" if o else "  output: -")
    if cr:
        print(f"  cache_read: {cr:,}")
    print(f"  ({note})")
    tin += i or 0
    tout += o or 0
    tcache += cr or 0

print()
print("=" * 78)
print(f"FRESH INPUT : {tin:,} ({tin/1e9:.2f}B)")
print(f"OUTPUT      : {tout:,} ({tout/1e6:.1f}M)")
print(f"CACHE READ  : {tcache:,} ({tcache/1e9:.2f}B)")
print()
print(f"GRAND TOTAL (in+out+cache): {tin+tout+tcache:,}")
print(f"  = {(tin+tout+tcache)/1e9:.2f} BILLION tokens")
print(f"BILLABLE-EQUIVALENT (in+out): {tin+tout:,}")
print("=" * 78)
