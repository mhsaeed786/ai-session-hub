"""Fix the 4 scripts with hardcoded secrets: route them through central_secrets."""
import os
import re

FILES = [
    (r"C:\Users\LOQ\Documents\Migrated data\Search-Parameters-Work\Pending Tasks - OPLAN GYST\FHIR Deletion Bundle - CMDGD\01_Build_Scripts\extract_fhir_ids_identifiers.py",
     "FHIR_CLIENT_SECRET"),
    (r"C:\Users\LOQ\Documents\Migrated data\Search-Parameters-Work\Pending Tasks - OPLAN GYST\FHIR Deletion Bundle - CMDGD\03_Verification_Scripts\test_provenance_query.py",
     "FHIR_CLIENT_SECRET"),
    (r"C:\Users\LOQ\Documents\Migrated data\Search-Parameters-Work\Pending Tasks - OPLAN GYST\OPLAN-GYST-Orchestrator\config.py",
     "FHIR_CLIENT_SECRET"),
    (r"C:\Users\LOQ\Documents\Migrated data\Search-Parameters-Work\Pending Tasks - OPLAN GYST\T63-FHIR-Duplicate-Identifier-Deletion-Bundle\reference-scripts\Deduplicate_Provenance.py",
     "FHIR_CLIENT_SECRET"),
]

secret_pat = re.compile(
    r"(?P<var>\w*(?:SECRET|TOKEN|PASSWORD|API_KEY)\w*)\s*=\s*[\"'](?P<val>[A-Za-z0-9\-_]{8,})[\"']",
    re.IGNORECASE)

HOOK = (
    "\nimport os as _os, sys as _sys\n"
    "_sys.path.insert(0, _os.environ.get('CENTRAL_SECRETS_DIR', r'C:\\Users\\LOQ\\secrets'))\n"
    "from central_secrets import get_secret as _get_secret\n"
)

for fp, key in FILES:
    try:
        with open(fp, encoding="utf-8") as f:
            content = f.read()
    except OSError:
        print(f"missing: {fp}")
        continue
    original = content
    matches = list(secret_pat.finditer(content))
    for m in matches:
        var, val = m.group("var"), m.group("val")
        # stash value in central env file
        env_fp = r"C:\Users\LOQ\secrets\.env.central"
        with open(env_fp, encoding="utf-8") as f:
            existing = f.read()
        if f"{var}=" not in existing:
            with open(env_fp, "a", encoding="utf-8") as f:
                f.write(f"{var}={val}\n")
        # replace in code
        content = secret_pat.sub(f"{var} = _get_secret(\"{var}\")", content, count=1)
    if content != original and "_get_secret" not in original.split("\n\n")[0]:
        lines = content.split("\n")
        # insert hook after last import near top
        insert_at = 0
        for i, ln in enumerate(lines[:30]):
            if ln.startswith(("import ", "from ")):
                insert_at = i + 1
        lines.insert(insert_at, HOOK.rstrip())
        content = "\n".join(lines)
        with open(fp, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        print(f"fixed: {fp}")
