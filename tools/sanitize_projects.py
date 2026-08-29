"""Sanitize projects before pushing: remove company identifiers and personal names.

Replacements are conservative - only obvious identifiers are changed.
Secrets were already moved to central_secrets (separate step).
"""
import os
import re

BASE = r"C:\Users\LOQ\Documents\Migrated data\_staging"

PROJECTS = [
    "FHIR-Mappings-builder",
    "FHIR-server-scope-based-security-testing",
    "Xellex-Campaign-Tools",
    "Python-Utilities-for-Testing",
    "Github-Data-Backup-Tools",
]

# Ordered replacements (case-sensitive pairs applied in order)
REPLACEMENTS = [
    # URLs / system identifiers
    ("fhir.curemd.com:4335", "fhir.example.com"),
    ("https://www.curemd.com/system-identifier/CMDGO", "https://example.com/fhir-system-identifier"),
    ("http://www.curemd.com", "https://example.com"),
    ("https://curemd.com", "https://example.com"),
    ("www.curemd.com", "example.com"),
    ("curemd.com", "example.com"),
    # DB / realm / app names
    ("FHIR_CUREMD", "FHIR_DB"),
    ("FHIRDB_CUREMD", "FHIR_DB"),
    ("hapi-fhir-testing", "fhir-testing"),
    ("MSSQL_USER=curemd", "MSSQL_USER=fhir_user"),
    # Personal names in comments/READMEs
    ("Hassan Saeed", "Author"),
    ("Hassan-Saeed", "author"),
    ("hassan.saeed", "author"),
    ("Hassan", "Author"),
    ("hassansaeed", "author"),
    ("hassan", "author"),  # lowercase leftovers (usernames, paths)
]

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv"}
CODE_EXTS = {".py", ".js", ".ts", ".json", ".yml", ".yaml", ".md", ".txt",
             ".cfg", ".toml", ".env.example", ".html", ".css", ".sh", ".bat"}


def sanitize_file(path):
    rel = None
    try:
        with open(path, encoding="utf-8") as f:
            content = f.read()
    except (OSError, UnicodeDecodeError):
        return False
    original = content
    for old, new in REPLACEMENTS:
        content = content.replace(old, new)
        content = content.replace(old.upper(), new.upper())
        content = content.replace(old.capitalize(), new.capitalize())
    if content != original:
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        return True
    return False


def main():
    total_changed = 0
    for proj in PROJECTS:
        root = os.path.join(BASE, proj)
        if not os.path.isdir(root):
            print(f"skip (missing): {proj}")
            continue
        changed = 0
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            # rename dirs containing 'curemd' or personal names later; files first
            for fn in filenames:
                ext = os.path.splitext(fn)[1].lower()
                fp = os.path.join(dirpath, fn)
                if ext in CODE_EXTS or fn == ".env.example":
                    if sanitize_file(fp):
                        changed += 1
                        print(f"  sanitized: {os.path.relpath(fp, root)}")
                # rename file itself if it contains a name
                new_fn = fn
                for old, new in [("curemd", "org"), ("CureMD", "Org"),
                                 ("hassan", "author"), ("Hassan", "Author"),
                                 ("saeed", "author"), ("Saeed", "Author")]:
                    new_fn = new_fn.replace(old, new)
                if new_fn != fn:
                    os.rename(fp, os.path.join(dirpath, new_fn))
                    print(f"  renamed file: {fn} -> {new_fn}")
        total_changed += changed
        print(f"{proj}: {changed} files sanitized")
    print(f"\nTotal: {total_changed} files sanitized")


if __name__ == "__main__":
    main()
