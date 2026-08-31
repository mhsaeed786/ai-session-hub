"""Final purity check: scan vault files for remaining third-person leaks."""
import re
import glob
import os

bad = re.compile(
    r"^\d+\. (A |An |The |Created|Successfully|Listed|Screenshots|Saved|"
    r"Found|Fixed|Added |Updated |Running |Now let)")

for fp in sorted(glob.glob(str(__import__("pathlib").Path.home() / "prompt-vault" / "*.md"))):
    if "_INDEX" in fp:
        continue
    with open(fp, encoding="utf-8") as f:
        lines = [l for l in f if re.match(r"^\d+\. ", l)]
    leaked = [l for l in lines if bad.match(l)]
    name = os.path.basename(fp)
    print(f"{name[:36]:36s} {len(lines):4d} prompts, {len(leaked):3d} suspicious")
    for l in leaked[:2]:
        print(f"     LEAK: {l[:100]}")
