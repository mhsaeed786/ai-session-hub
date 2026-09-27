"""Back up + quarantine every harness session store.

Order per source: tar.gz backup -> move files to quarantine.
Nothing is deleted; RESTORE.md documents how to put it all back.
Hermes' own live DB is never touched (it is the destination).
"""
import glob
import json
import os
import shutil
import time

HOME = r"C:\Users\LOQ"
TS = time.strftime("%Y%m%d-%H%M%S")
BASE = os.path.join(HOME, "harness-migration")
BACKUP = os.path.join(BASE, f"backup-{TS}")
QUAR = os.path.join(BASE, f"quarantine-{TS}")
os.makedirs(BACKUP, exist_ok=True)
os.makedirs(QUAR, exist_ok=True)

# (name, root, pattern, recursive)
SOURCES = [
    ("goose_live", os.path.join(HOME, r"AppData\Roaming\Block\goose\data\sessions"), "**/*", True),
    ("goose_local", os.path.join(HOME, r"AppData\Local\goose\data\sessions"), "**/*", True),
    ("antigravity", os.path.join(HOME, r".gemini\antigravity"), "**/*", True),
    ("gemini_tmp", os.path.join(HOME, r".gemini\tmp"), "**/*", True),
    ("claude_projects", os.path.join(HOME, r".claude\projects"), "**/*.jsonl", True),
    ("claude_history", os.path.join(HOME, r".claude\history.jsonl"), "", False),
    ("codex_sessions", os.path.join(HOME, r".codex\sessions"), "**/*", True),
    ("codex_state", os.path.join(HOME, r".codex\state_5.sqlite"), "", False),
    ("opencode_storage", os.path.join(HOME, r".local\share\opencode\storage"), "**/*", True),
    ("opencode_db", os.path.join(HOME, r".local\share\opencode\opencode.db"), "", False),
    ("zcode_db", os.path.join(HOME, r".zcode\cli\db"), "**/*", True),
    ("codeium_state", os.path.join(HOME, r".codeium\chat_state"), "**/*", True),
    ("openclaw", os.path.join(HOME, r".openclaw\sessions"), "**/*", True),
    ("zai_logs", os.path.join(HOME, r".zai"), "**/*.log", True),
    ("mimocode", os.path.join(HOME, r".local\share\mimocode"), "**/*", True),
    ("ai_extractor", os.path.join(HOME, r"ai-session-extractor\data"), "**/*", True),
    ("copilot_state", os.path.join(HOME, r".copilot\history-session-state"), "**/*", True),
    ("trae_ws", os.path.join(HOME, r"AppData\Roaming\Trae\User\workspaceStorage"), "**/*", True),
]

manifest = {"timestamp": TS, "backup": BACKUP, "quarantine": QUAR, "sources": []}
print(f"backup     -> {BACKUP}")
print(f"quarantine -> {QUAR}\n")

for name, root, pattern, recursive in SOURCES:
    if not os.path.exists(root):
        print(f"  {name:18s} ABSENT")
        continue
    if os.path.isfile(root):
        files = [root]
        scan_root = os.path.dirname(root)
        tar_base = root
    else:
        files = [f for f in glob.glob(os.path.join(root, pattern), recursive=recursive)
                 if os.path.isfile(f)]
        scan_root = root
        tar_base = root
    if not files:
        print(f"  {name:18s} no files")
        continue

    # ---- backup (must succeed or we do not touch the source) ----
    try:
        if os.path.isdir(tar_base):
            shutil.make_archive(os.path.join(BACKUP, name), "gztar", tar_base)
        else:
            d = os.path.join(BACKUP, name)
            os.makedirs(d, exist_ok=True)
            shutil.copy2(tar_base, os.path.join(d, os.path.basename(tar_base)))
            shutil.make_archive(os.path.join(BACKUP, name), "gztar", d)
    except OSError as e:
        print(f"  {name:18s} BACKUP FAILED: {e} -- skipping quarantine")
        continue

    # ---- quarantine ----
    moved = 0
    for f in files:
        rel = os.path.relpath(f, scan_root)
        dest = os.path.join(QUAR, name, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        try:
            shutil.move(f, dest)
            moved += 1
        except OSError as e:
            print(f"       move failed {os.path.basename(f)}: {e}")

    print(f"  {name:18s} {moved:6d} / {len(files)} files quarantined")
    manifest["sources"].append({"name": name, "root": root, "files": moved})

    # drop now-empty dirs so the harness shows nothing
    if os.path.isdir(root):
        for d, _, _ in os.walk(root, topdown=False):
            try:
                os.rmdir(d)
            except OSError:
                pass

with open(os.path.join(BASE, f"quarantine_manifest_{TS}.json"), "w") as f:
    json.dump(manifest, f, indent=1)

lines = ["# Restore instructions", "",
         f"Backups:    `{BACKUP}`", f"Quarantine: `{QUAR}`", "",
         "Every `backup-<ts>/<name>.tar.gz` unpacks to the original store.", ""]
for s in manifest["sources"]:
    lines.append(f"- **{s['name']}** ({s['files']} files) <- original: `{s['root']}`")
lines += ["", "## Restore from backup",
          "```bash",
          "cd <original parent dir>",
          "tar -xzf <backup>/<name>.tar.gz",
          "```", "", "## Restore from quarantine",
          "```bash",
          "cp -r <quarantine>/<name>/* <original root>/",
          "```"]
with open(os.path.join(BASE, "RESTORE.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

total = sum(s["files"] for s in manifest["sources"])
print(f"\nsources processed: {len(manifest['sources'])}   files quarantined: {total}")
print(f"restore doc: {os.path.join(BASE, 'RESTORE.md')}")
