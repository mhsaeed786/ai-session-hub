"""Check codex rollout token events + claude jsonl in old-PC quarantine."""
import os, glob, json

HOME = os.path.expanduser("~")
QB = os.path.join(HOME, "session-migration-backup-20260822", "quarantine")
Q27 = os.path.join(HOME, "harness-migration", "quarantine-20260927-070220")

print("### files in old-PC quarantine")
for f in sorted(os.listdir(QB)):
    p = os.path.join(QB, f)
    if os.path.isfile(p):
        kind = "codex-rollout" if f.startswith("rollout") else (
               "claude-uuid" if f.endswith(".jsonl") else "other")
        print(f"   {kind:14} {f}  {os.path.getsize(p)/1e3:.0f}KB")
    else:
        print(f"   DIR            {f}/")

print("\n### codex rollout token events (recorded usage?)")
for fp in glob.glob(os.path.join(QB, "rollout-*.jsonl")):
    tot = None; nev = 0; keys = set()
    with open(fp, encoding="utf-8", errors="replace") as f:
        for line in f:
            if "token" not in line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            payload = d.get("payload") or d
            info = payload.get("info") or payload
            tu = info.get("total_token_usage") or info.get("token_count") or payload.get("total_token_usage")
            if isinstance(tu, dict):
                nev += 1
                keys |= set(tu.keys())
                tot = tu  # last = cumulative
    print(f"   {os.path.basename(fp)[:44]:46} events={nev} keys={sorted(keys)} last={tot}")

print("\n### codex sessions in harness quarantine")
for fp in glob.glob(os.path.join(Q27, "codex_sessions", "**", "*.jsonl"), recursive=True)[:20]:
    has = False
    with open(fp, encoding="utf-8", errors="replace") as f:
        s = f.read()
    has = "total_token_usage" in s or '"token_count"' in s
    print(f"   {os.path.basename(fp)[:50]:52} {os.path.getsize(fp)/1e3:.0f}KB tokens_recorded={has}")

print("\n### claude uuid jsonl usage sample")
for fp in glob.glob(os.path.join(QB, "*.jsonl"))[:4]:
    if os.path.basename(fp).startswith("rollout"):
        continue
    n = 0
    with open(fp, encoding="utf-8", errors="replace") as f:
        for line in f:
            if '"usage"' in line:
                n += 1
    print(f"   {os.path.basename(fp)[:40]} usage-lines={n}")

print("\n### goose JSON exports in old-PC quarantine")
for fp in glob.glob(os.path.join(QB, "goose", "*.json")):
    d = json.load(open(fp, encoding="utf-8", errors="replace"))
    print("   ", os.path.basename(fp)[:40], "keys:", [k for k in d.keys()][:12])
    break
print("   goose dir files:", len(glob.glob(os.path.join(QB, "goose", "*.json"))))
