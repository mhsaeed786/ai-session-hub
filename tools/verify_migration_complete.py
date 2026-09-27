"""Final verification: what harness data remains anywhere on this PC?"""
import glob
import os
import sqlite3

HOME = r"C:\Users\LOQ"

CHECKS = [
    ("Goose live", r"AppData\Roaming\Block\goose\data\sessions"),
    ("Goose local", r"AppData\Local\goose\data\sessions"),
    ("Antigravity", r".gemini\antigravity"),
    ("Claude projects", r".claude\projects"),
    ("Claude history", r".claude\history.jsonl"),
    ("Codex sessions", r".codex\sessions"),
    ("opencode", r".local\share\opencode"),
    ("zcode", r".zcode\cli\db"),
    ("codeium", r".codeium\chat_state"),
    ("openclaw", r".openclaw\sessions"),
    ("Z.AI", r".zai"),
    ("mimocode", r".local\share\mimocode"),
    ("ai-extractor", r"ai-session-extractor\data"),
    ("Copilot", r".copilot"),
    ("Trae", r"AppData\Roaming\Trae"),
    # the ones we did NOT quarantine (not session stores):
    ("Hermes live (destination)", r"AppData\Local\hermes\state.db"),
    ("Gemini CLI tmp", r".gemini\tmp"),
    ("Cursor", r"AppData\Roaming\Cursor\User"),
    ("Continue", r".continue"),
]

print(f"{'STORE':30s} {'FILES':>7s} {'MB':>8s}  STATE")
print("-" * 66)
for label, rel in CHECKS:
    p = os.path.join(HOME, rel)
    if not os.path.exists(p):
        print(f"{label:30s} {'-':>7s} {'-':>8s}  gone/empty")
        continue
    if os.path.isfile(p):
        files = [p]
    else:
        files = [f for f in glob.glob(os.path.join(p, "**", "*"), recursive=True)
                 if os.path.isfile(f)]
    if not files:
        print(f"{label:30s} {'0':>7s} {'0':>8s}  gone/empty")
        continue
    size = sum(os.path.getsize(f) for f in files)
    # classify: is it session data?
    name = f"{len(files)}"
    print(f"{label:30s} {name:>7s} {size/1_048_576:>8.1f}  STILL PRESENT")
