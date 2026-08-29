"""Fix variable names broken by the sanitizer: 'the organization_col' -> 'db_col'."""
import glob

files = glob.glob(r"C:\Users\LOQ\Documents\Migrated data\_staging\FHIR-Mappings-builder\**\*.py",
                  recursive=True)
fixed = 0
for fp in files:
    try:
        with open(fp, encoding="utf-8") as f:
            content = f.read()
    except (OSError, UnicodeDecodeError):
        continue
    if "the organization_col" in content or "the organization tables" in content \
            or "'the organization'" in content:
        original = content
        content = content.replace("the organization_col", "db_col")
        content = content.replace("Common the organization tables", "Common DB tables")
        # 'the organization' inside string literals that mean the DB column header
        content = content.replace('"FHIR Path" or "FHIR Path" and "Table/Field" or "the organization"',
                                  '"FHIR path" and "Table/Field" or "DB"')
        content = content.replace("or 'the organization', 'table/field'", "or 'db', 'table/field'")
        content = content.replace("('the organization' in val", "('db' in val")
        if content != original:
            with open(fp, "w", encoding="utf-8", newline="") as f:
                f.write(content)
            fixed += 1
            print(f"fixed: {fp}")
print(f"\n{fixed} files repaired")
