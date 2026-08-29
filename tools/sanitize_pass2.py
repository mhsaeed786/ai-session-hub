"""Second-pass sanitizer: catches remaining company mentions."""
import os

BASE = r"C:\Users\LOQ\Documents\Migrated data\_staging"
PROJECTS = [
    "FHIR-Mappings-builder",
    "FHIR-server-scope-based-security-testing",
    "Xellex-Campaign-Tools",
    "Python-Utilities-for-Testing",
    "Github-Data-Backup-Tools",
]

# Pass 2 replacements (case-insensitive where sensible)
PATTERNS = [
    ("username = os.getenv('MSSQL_USER', 'curemd')", "username = os.getenv('MSSQL_USER', 'fhir_user')"),
    ("The CureMD Impacted Fields sheet", "The Impacted Fields sheet"),
    ("CureMD's OAuth client configuration", "the OAuth provider's client configuration"),
    ("CureMD OAuth", "OAuth provider"),
    ("CureMD FHIR OAuth Demo", "FHIR OAuth Demo"),
    ("CureMD", "the organization"),  # generic fallback
]

SKIP_DIRS = {".git", "node_modules", "__pycache__"}
CODE_EXTS = {".py", ".js", ".ts", ".json", ".yml", ".yaml", ".md", ".txt",
             ".cfg", ".toml", ".html"}


def main():
    changed = 0
    for proj in PROJECTS:
        root = os.path.join(BASE, proj)
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fn in filenames:
                if os.path.splitext(fn)[1].lower() not in CODE_EXTS:
                    continue
                fp = os.path.join(dirpath, fn)
                try:
                    with open(fp, encoding="utf-8") as f:
                        content = f.read()
                except (OSError, UnicodeDecodeError):
                    continue
                original = content
                for old, new in PATTERNS:
                    content = content.replace(old, new)
                    # case-insensitive leftover sweep
                    if old.lower() in content.lower():
                        content = re.sub(re.escape(old), new, content, flags=re.IGNORECASE) if (re := __import__("re")) else content
                if content != original:
                    with open(fp, "w", encoding="utf-8", newline="") as f:
                        f.write(content)
                    changed += 1
                    print(f"  pass2: {os.path.relpath(fp, root)}")
    print(f"\nPass2 total: {changed} files")


if __name__ == "__main__":
    main()
