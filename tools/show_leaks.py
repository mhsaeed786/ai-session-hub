"""Show remaining suspicious lines from worst files to see what pattern remains."""
import re

for fp in [str(__import__("pathlib").Path.home() / "prompt-vault" / "AI_Super_App.md"),
           str(__import__("pathlib").Path.home() / "prompt-vault" / "AI_Researcher.md")]:
    print(f"=== {fp.split(chr(92))[-1]} ===")
    with open(fp, encoding="utf-8") as f:
        lines = [l for l in f if re.match(r"^\d+\. (A |An |The |Created|Successfully|Listed|Screenshots|Saved|Found|Fixed|Added |Updated |Running |Now let)", l)]
    for l in lines[:10]:
        print("  ", l[:110])
    print()
