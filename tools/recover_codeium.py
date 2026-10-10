"""Recover Codeium/Windsurf chat_state protobuf blobs.

No .proto available, so extract the readable UTF-8 payload: message text is
stored as plain strings inside the blob. One session per unique file.
"""
import glob
import json
import os
import re
import subprocess

HOME = r"C:\Users\LOQ"
BASE = os.path.join(HOME, "harness-migration")
OUT = os.path.join(BASE, "converted", "codeium")
os.makedirs(OUT, exist_ok=True)


def safe(s):
    return "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in str(s))[:56]


def extract(path):
    """Pull natural-language strings out of the protobuf blob."""
    raw = open(path, "rb").read()
    txt = raw.decode("utf-8", errors="ignore")
    # keep runs that look like prose: >=12 chars, has spaces, mostly printable
    out = []
    for m in re.finditer(r'[\x20-\x7e\u00a0-\uffff]{12,4000}', txt):
        s = m.group(0).strip()
        if len(s) < 12:
            continue
        printable = sum(1 for ch in s if ch.isprintable())
        if printable / max(len(s), 1) < 0.9:
            continue
        # drop obvious binary/noise and pure keys
        if re.fullmatch(r'[A-Za-z0-9_\-./:]{1,60}', s):
            continue
        if s.count(" ") < 2:
            continue
        out.append(s)
    # dedupe preserving order
    seen = set()
    uniq = []
    for s in out:
        k = s[:80]
        if k not in seen:
            seen.add(k)
            uniq.append(s)
    return uniq


files = []
for qd in sorted(glob.glob(os.path.join(BASE, "quarantine-*"))):
    p = os.path.join(qd, "codeium_state")
    if os.path.isdir(p):
        for root, _, names in os.walk(p):
            for n in names:
                if n.endswith(".pb"):
                    files.append(os.path.join(root, n))

print(f"codeium .pb files: {len(files)}")
# group by content hash so duplicates don't create repeated sessions
seen_hash = set()
imported = 0
for fp in files:
    data = open(fp, "rb").read()
    if len(data) < 500:
        continue                      # empty per-workspace stub
    h = hash(data)
    if h in seen_hash:
        continue
    seen_hash.add(h)
    lines = extract(fp)
    if not lines:
        continue
    name = "codeium_" + safe(os.path.basename(fp).replace(".pb", ""))
    out = os.path.join(OUT, f"{name}.jsonl")
    with open(out, "w", encoding="utf-8") as f:
        for s in lines:
            f.write(json.dumps({"type": "user", "message": {
                "role": "user", "content": s[:40000]}},
                ensure_ascii=False) + "\n")
    try:
        r = subprocess.run(["hermes", "sessions", "import", "--from", "claude",
                            out.replace("\\", "/")],
                           capture_output=True, text=True, timeout=180)
        ok = "Imported" in (r.stdout + r.stderr)
    except subprocess.TimeoutExpired:
        ok = False
    print(f"  {os.path.basename(fp)[:44]:46s} {len(lines):4d} lines -> "
          f"{'imported' if ok else 'FAILED'}")
    imported += 1 if ok else 0

print(f"\ncodeium sessions imported: {imported}")
