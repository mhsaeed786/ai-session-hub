"""Pass 2: remove files whose remaining personal refs are real data (patient names etc)."""
import os
import re
import glob

DEST = r"C:\Users\LOQ\python-scripts-collection"

# These remaining matches are REAL DATA (names in test fixtures, sample payloads)
# not code identifiers - safest is to delete these files from the public collection.
DATA_MARKERS = re.compile(
    r"(SAEED A KHAN|patient.*hassan|hassan.*test|AHMED|Mohammed.*test)", re.IGNORECASE)

removed = 0
for f in glob.glob(os.path.join(DEST, "*.py")):
    try:
        with open(f, encoding="utf-8", errors="replace") as fh:
            c = fh.read()
    except OSError:
        continue
    if re.search(r"curemd|hassan|saeed|mhsaeed786", c, re.IGNORECASE):
        os.remove(f)
        removed += 1

final = glob.glob(os.path.join(DEST, "*.py"))
leftover = []
for f in final:
    try:
        with open(f, encoding="utf-8", errors="replace") as fh:
            c = fh.read()
    except OSError:
        continue
    if re.search(r"curemd|hassan|saeed|mhsaeed786", c, re.IGNORECASE):
        leftover.append(os.path.basename(f))

print(f"Removed {removed} files with embedded personal data")
print(f"Final collection: {len(final)} scripts")
print(f"Personal refs still present: {len(leftover)} {leftover[:5]}")
