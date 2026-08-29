"""Final sanitize + remove broken scripts from the collection."""
import os
import re
import glob
import py_compile

DEST = r"C:\Users\LOQ\python-scripts-collection"

# 1) Remove scripts with syntax errors (broken/incomplete - not worth pushing)
removed = 0
for f in glob.glob(os.path.join(DEST, "*.py")):
    try:
        py_compile.compile(f, doraise=True)
    except Exception:
        os.remove(f)
        removed += 1
print(f"Removed {removed} broken scripts")

# 2) Scrub personal references in remaining files
pat_pairs = [
    (r"mhsaeed786", "your-org"),
    (r"curemd\.com", "example.com"),
    (r"CureMD", "Org"),
    (r"curemd", "org"),
    (r"Hassan Saeed", "Author"),
    (r"[Hh]assan", "author"),
    (r"[Ss]aeed", "author"),
]
scrubbed = 0
for f in glob.glob(os.path.join(DEST, "*.py")):
    try:
        with open(f, encoding="utf-8") as fh:
            content = fh.read()
    except (OSError, UnicodeDecodeError):
        continue
    original = content
    for pat, repl in pat_pairs:
        content = re.sub(pat, repl, content)
    if content != original:
        # re-verify it still compiles after scrub
        try:
            compile(content, f, "exec")
        except SyntaxError:
            continue  # skip if scrubbing broke it; leave original
        with open(f, "w", encoding="utf-8", newline="") as fh:
            fh.write(content)
        scrubbed += 1
print(f"Scrubbed {scrubbed} files")

# 3) final counts
final = glob.glob(os.path.join(DEST, "*.py"))
leftover = []
for f in final:
    with open(f, encoding="utf-8", errors="replace") as fh:
        c = fh.read()
    if re.search(r"curemd|hassan|saeed|mhsaeed786", c, re.IGNORECASE):
        leftover.append(os.path.basename(f))
print(f"Final: {len(final)} scripts | personal refs remaining: {len(leftover)}")
if leftover:
    print("  in:", leftover[:5])
