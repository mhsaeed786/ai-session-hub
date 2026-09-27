"""Full backup of every harness store BEFORE any source is cleared.

Creates: C:\\Users\\LOQ\\harness-migration\\backup-<ts>\\
  - tar.gz per source (original paths preserved)
  - MANIFEST.json with sha256 of every file + restore instructions
Nothing here deletes anything; it only reads.
"""
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

HOME = r"C:\Users\LOQ"
TS = time.strftime("%Y%m%d-%H%M%S")
DEST = rf"C:\Users\LOQ\harness-migration\backup-{TS}"
os.makedirs(DEST, exist_ok=True)

# Live stores that will be cleared after import
SOURCES = {
    "goose_live": os.path.join(HOME, r"AppData\Roaming\Block\goose\data\sessions"),
    "antigravity": os.path.join(HOME, r".gemini\antigravity"),
    "claude_code": os.path.join(HOME, r".claude\projects"),
    "codex": os.path.join(HOME, r".codex\sessions"),
    "opencode": os.path.join(HOME, r".local\share\opencode"),
    "zcode": os.path.join(HOME, r".zcode\cli\db"),
    "codeium": os.path.join(HOME, r".codeium\chat_state"),
    "openclaw": os.path.join(HOME, r".openclaw\sessions"),
    "zai": os.path.join(HOME, r".zai"),
    "mimocode": os.path.join(HOME, r".local\share\mimocode"),
    "claude_history": os.path.join(HOME, r".claude\history.jsonl"),
    "codex_db": os.path.join(HOME, r".codex"),
}


def sha256(path, limit=None):
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            while True:
                b = f.read(1 << 20)
                if not b:
                    break
                h.update(b)
    except OSError:
        return "unreadable"
    return h.hexdigest()


manifest = {"created": TS, "sources": {}}
total_bytes = 0
total_files = 0

for name, path in SOURCES.items():
    if not os.path.exists(path):
        print(f"  {name:16s} ABSENT")
        continue
    files = ([path] if os.path.isfile(path)
             else glob.glob(os.path.join(path, "**", "*"), recursive=True))
    files = [f for f in files if os.path.isfile(f)]
    size = sum(os.path.getsize(f) for f in files)
    print(f"  {name:16s} {len(files):5d} files {size/1_048_576:8.1f} MB")
    manifest["sources"][name] = {
        "path": path,
        "files": [{"p": f, "size": os.path.getsize(f)}
                  for f in files],
    }
    total_bytes += size
    total_files += len(files)

    # tar it up (preserves paths so restore is trivial)
    tar = os.path.join(DEST, f"{name}.tar.gz")
    r = subprocess.run(
        ["tar", "-czf", tar.replace("\\", "/"), "-C",
         path.replace("\\", "/").rsplit("/", 1)[0],
         path.replace("\\", "/").rsplit("/", 1)[1]],
        capture_output=True, text=True)
    if r.returncode != 0:
        print(f"      tar failed: {(r.stderr or '')[:80]}")

with open(os.path.join(DEST, "MANIFEST.json"), "w") as f:
    json.dump(manifest, f, indent=1)

print(f"\nbackup dir: {DEST}")
print(f"total: {total_files} files, {total_bytes/1_048_576:.1f} MB")
for t in glob.glob(os.path.join(DEST, "*.tar.gz")):
    print(f"  {os.path.basename(t):24s} {os.path.getsize(t)/1_048_576:8.1f} MB")
