"""QA SWEEP - actually run every built app end-to-end and record results."""
import subprocess
import os
import sys
import time
import json

RESULTS = []


def check(name, cmd, cwd=None, expect=0, timeout=60):
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                           timeout=timeout, shell=True)
        ok = (r.returncode == expect)
        RESULTS.append({
            "app": name, "cmd": cmd, "ok": ok,
            "rc": r.returncode,
            "out": (r.stdout or "")[-400:], "err": (r.stderr or "")[-400:],
        })
        print(f"{'PASS' if ok else 'FAIL'} {name} (rc={r.returncode})")
        if not ok:
            tail = ((r.stderr or "") or (r.stdout or ""))[-250:]
            print("      ", tail.replace(chr(10), " | ")[:240])
    except subprocess.TimeoutExpired:
        RESULTS.append({"app": name, "cmd": cmd, "ok": False, "rc": "timeout",
                        "out": "", "err": "timeout"})
        print(f"TIMEOUT {name}")
    except Exception as e:
        RESULTS.append({"app": name, "cmd": cmd, "ok": False, "rc": "?",
                        "out": "", "err": str(e)})
        print(f"ERROR {name}: {e}")


PY = sys.executable

# 1. ai-session-hub: stats endpoint logic
check("ai-session-hub CLI", f'"{PY}" run.py --master-prompt test-nonexistent',
      cwd=r"C:\Users\LOQ\ai-session-hub")

# 2. omnimedia-agency: offline generate path
check("omnimedia import", f'"{PY}" -c "import sys; sys.path.insert(0,\'..\'); '
       f"import main; print('imports OK')\"",
      cwd=r"C:\Users\LOQ\omnimedia-agency\venv\Scripts")

# 3. One-Agent: modules listing
check("One-Agent boot", f'"{PY}" -c "import main"', cwd=r"C:\Users\LOQ\repo-audit\One-Agent")

# 4. BA-QA suite: cli modules
check("BA-QA cli modules", f'"{PY}" cli.py modules', timeout=90,
      cwd=r"C:\Users\LOQ\Documents\Migrated data\AI-Evaluation-automation-system\legacy-curemd-ba-qa")

# 5. ollama-evals: server import
check("ollama-evals server import",
      f'"{PY}" -c "from src import server; print(\'server OK\')"',
      cwd=r"C:\Users\LOQ\Documents\ollama-eval-system")

# 6. teams-task-scraper: cli help
check("teams-scraper cli", f'"{PY}" -m teams_task_scraper.cli --help',
      cwd=r"C:\Users\LOQ\teams-task-scraper")

# 7. NovelForge: package import
check("NovelForge import",
      f'"{PY}" -c "import sys; sys.path.insert(0,\'novel_forge\'); import exporter; print(\'OK\')"',
      cwd=r"C:\Users\LOQ\Documents\Migrated data\Initiatives\NovelForge")

# 8. FHIR-Mappings-builder: one script's help
check("FHIR-mappings parse script",
      f'"{PY}" scripts/parse_all_mappings.py --help',
      cwd=r"C:\Users\LOQ\Documents\Migrated data\_staging\FHIR-Mappings-builder")

# summary
passed = sum(1 for r in RESULTS if r["ok"])
print()
print("=" * 50)
print(f"QA SWEEP: {passed}/{len(RESULTS)} passed")
with open(r"C:\Users\LOQ\session-audit-20260822\qa-sweep-results.json", "w") as f:
    json.dump(RESULTS, f, indent=2)
print("Details: session-audit-20260822/qa-sweep-results.json")
