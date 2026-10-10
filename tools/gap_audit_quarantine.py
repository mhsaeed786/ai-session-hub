"""Honest gap audit: what session data exists in quarantine/backups that is NOT
represented in Hermes?

For each quarantined tool store, count the session-bearing files and check
whether Hermes holds matching sessions.
"""
import glob
import os
import sqlite3

HOME = r"C:\Users\LOQ"
BASE = os.path.join(HOME, "harness-migration")
HERMES = os.path.join(HOME, r"AppData\Local\hermes\state.db")

c = sqlite3.connect(f"file:{HERMES}?mode=ro", uri=True)
h_ids = [r[0] for r in c.execute("SELECT id FROM sessions")]
h_titles = [str(r[0]).lower() for r in
            c.execute("SELECT title FROM sessions WHERE title IS NOT NULL")]
c.close()

h_ids_l = " ".join(h_ids).lower()
h_titles_s = " | ".join(h_titles)


def in_hermes(token):
    t = str(token).lower()
    return t in h_ids_l or t in h_titles_s


print("=" * 78)
print("QUARANTINED STORES vs HERMES COVERAGE")
print("=" * 78)

# every quarantine-* dir
qdirs = sorted(glob.glob(os.path.join(BASE, "quarantine-*")))
tool_files = {}
for qd in qdirs:
    for tool in os.listdir(qd):
        p = os.path.join(qd, tool)
        n = 0
        exts = {}
        for root, _, names in os.walk(p):
            for nm in names:
                n += 1
                e = os.path.splitext(nm)[1].lower() or "(none)"
                exts[e] = exts.get(e, 0) + 1
        prev = tool_files.get(tool, [0, {}])
        tool_files[tool] = [prev[0] + n, {**prev[1],
                                          **{k: prev[1].get(k, 0) + v
                                             for k, v in exts.items()}}]

print(f"{'TOOL STORE':22s} {'FILES':>7s}  {'EXTENSIONS':38s} IN HERMES?")
print("-" * 78)
for tool in sorted(tool_files, key=lambda t: -tool_files[t][0]):
    n, exts = tool_files[tool]
    ext_s = ", ".join(f"{k}x{v}" for k, v in
                      sorted(exts.items(), key=lambda x: -x[1])[:3])
    # rough coverage check by tool name
    hit = in_hermes(tool) or in_hermes(tool.replace("_", " "))
    print(f"{tool:22s} {n:>7d}  {ext_s[:38]:38s} "
          f"{'yes' if hit else '*** UNVERIFIED ***'}")

print()
print("=" * 78)
print("FORMATS HERMES CANNOT READ NATIVELY (need a converter)")
print("=" * 78)
for tool in sorted(tool_files, key=lambda t: -tool_files[t][0]):
    n, exts = tool_files[tool]
    risky = {k: v for k, v in exts.items()
             if k in (".pb", ".pbtxt", ".db", ".sqlite", ".log", "(none)",
                      ".vscdb", ".wal", ".shm")}
    if risky:
        print(f"  {tool:20s} {n:>6d} files -> {risky}")
