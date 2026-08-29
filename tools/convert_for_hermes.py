"""Convert Goose + OpenClaw sessions into Claude-Code-style JSONL so
`hermes sessions import --from claude` can ingest them, then import.

No source files are modified - we write converted copies to a temp dir.
"""
import json
import os
import glob
import subprocess
import sys

Q = r"C:\Users\LOQ\session-migration-backup-20260822\quarantine"
OUT = r"C:\Users\LOQ\session-migration-backup-20260822\converted-for-hermes"
os.makedirs(OUT, exist_ok=True)

converted = []

# ---- Goose: {name, working_dir, created_at, conversation:[{role, content:[{type:text}]}]}
for fp in glob.glob(os.path.join(Q, "goose", "*.json")):
    try:
        with open(fp, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        continue
    conv = data.get("conversation") or []
    if not conv:
        continue
    name = (data.get("name") or os.path.basename(fp)).replace(".json", "")
    out_name = "".join(c if c.isalnum() else "_" for c in name)[:40]
    out_path = os.path.join(OUT, f"goose_{out_name}.jsonl")
    with open(out_path, "w", encoding="utf-8") as f:
        for item in conv:
            role = item.get("role", "user")
            blocks = item.get("content") or []
            texts = []
            if isinstance(blocks, str):
                texts = [blocks]
            else:
                for b in blocks:
                    if isinstance(b, dict) and b.get("type") == "text":
                        texts.append(b.get("text", ""))
            text = "\n".join(t for t in texts if t).strip()
            if not text:
                continue
            f.write(json.dumps({
                "type": role if role in ("user", "assistant") else "user",
                "message": {"role": role, "content": text},
                "timestamp": None,
            }, ensure_ascii=False) + "\n")
    converted.append(("goose", name, out_path))

# ---- OpenClaw: jsonl with type:user/assistant lines
for fp in glob.glob(os.path.join(Q, "openclaw", "*.jsonl")):
    out_path = os.path.join(OUT, "openclaw_" +
                            os.path.basename(fp).replace(".jsonl", ".jsonl"))
    count = 0
    with open(out_path, "w", encoding="utf-8") as out:
        with open(fp, encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                t = d.get("type")
                if t not in ("user", "assistant", "system"):
                    continue
                content = d.get("message") or d.get("content") or ""
                if isinstance(content, (dict, list)):
                    content = json.dumps(content, ensure_ascii=False)
                if not str(content).strip():
                    continue
                out.write(json.dumps({
                    "type": t,
                    "message": {"role": t, "content": str(content)},
                }, ensure_ascii=False) + "\n")
                count += 1
    if count:
        converted.append(("openclaw", os.path.basename(fp), out_path))
    else:
        os.remove(out_path)

print(f"Converted {len(converted)} sessions:")
for tool, name, path in converted:
    size = os.path.getsize(path)
    print(f"  [{tool}] {name[:50]} -> {os.path.basename(path)} ({size}b)")

# save manifest for import step
with open(os.path.join(OUT, "_manifest.txt"), "w") as f:
    for tool, name, path in converted:
        f.write(f"{path}\n")
