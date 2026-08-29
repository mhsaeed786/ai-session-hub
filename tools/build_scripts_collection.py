"""Build the single-file scripts collection repo.

Collects USER loose scripts from known work areas (not libs/tools),
sanitizes names, dedupes, and stages into a new repo folder.
"""
import os
import re
import shutil
import hashlib

HOME = r"C:\Users\LOQ"
DEST = r"C:\Users\LOQ\python-scripts-collection"

# Work areas that contain user-authored scripts
SOURCES = [
    r"Documents\Migrated data\allmydata\Xellex campaings code",
    r"Documents\Migrated data\Search-Parameters-Work",
    r"Documents\Migrated data\_staging\FHIR-server-scope-based-security-testing\scripts",
    r"Documents\Migrated data\_staging\Python-Utilities-for-Testing",
    r"Documents\Migrated data\_staging\Github-Data-Backup-Tools",
    r"Documents\Migrated data\_staging\Xellex-Campaign-Tools",
    r"Documents\Migrated data\Search-Parameters-Work\Pending Tasks - OPLAN GYST",
    r"Documents\Migrated data\Initiatives\NovelForge\novel_forge",
    r"AI-Agent-Sessions-Master\Goose",
    r"Documents\Migrated data\Initiatives\CureMD-Developer-Portal-.NET",
]

SKIP_DIRS = {"node_modules", "__pycache__", ".git", "venv", ".venv", "__MACOSX"}
EXCLUDE = ("write_goose.py",)  # session tooling, not a project script


def safe_name(name):
    stem, ext = os.path.splitext(name)
    stem = re.sub(r"[^A-Za-z0-9_\- ]", "_", stem).strip().replace(" ", "_")
    stem = re.sub(r"_+", "_", stem)
    return stem + (ext or ".py")


def main():
    if not os.path.isdir(DEST):
        os.makedirs(DEST)
        print(f"created {DEST}")

    seen_hashes = {}
    copied, skipped_dup, skipped_secret = 0, 0, 0
    secret_pat = re.compile(
        r"(password|secret|token|api_key)\s*=\s*[\"'][A-Za-z0-9\-_]{12,}[\"']",
        re.IGNORECASE)

    for src in SOURCES:
        root = os.path.join(HOME, src)
        if not os.path.isdir(root):
            print(f"skip missing: {src}")
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fn in filenames:
                if not fn.endswith(".py") or fn.startswith("__"):
                    continue
                fp = os.path.join(dirpath, fn)
                try:
                    with open(fp, encoding="utf-8", errors="replace") as f:
                        content = f.read()
                except OSError:
                    continue
                h = hashlib.md5(content.encode()).hexdigest()
                if h in seen_hashes:
                    skipped_dup += 1
                    continue
                if secret_pat.search(content):
                    print(f"  SECRET in {fp} - SKIPPED (needs manual fix)")
                    skipped_secret += 1
                    continue
                # build unique dest name: parent folder prefix for context
                parent = os.path.basename(dirpath)
                pname = safe_name(parent)[:30]
                fname = safe_name(fn)
                dest_name = fname if len(fname) > 8 else f"{pname}_{fname}"
                dest_fp = os.path.join(DEST, dest_name)
                i = 1
                while os.path.exists(dest_fp):
                    stem, ext = os.path.splitext(dest_name)
                    dest_fp = os.path.join(DEST, f"{stem}_{i}{ext}")
                    i += 1
                shutil.copy2(fp, dest_fp)
                seen_hashes[h] = dest_fp
                copied += 1

    print(f"\nCopied: {copied} | Duplicates skipped: {skipped_dup} | "
          f"With secrets (skipped): {skipped_secret}")
    print(f"Repo folder: {DEST}")


if __name__ == "__main__":
    main()
