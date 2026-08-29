"""QA sweep round 2 - use each project's own venv."""
import subprocess
import os
import sys
import json

RESULTS = []
PY = sys.executable


def check(name, cmd, cwd=None, timeout=120):
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                           timeout=timeout, shell=True)
        ok = (r.returncode == 0)
        RESULTS.append({"app": name, "ok": ok, "rc": r.returncode,
                        "out": (r.stdout or "")[-300:], "err": (r.stderr or "")[-300:]})
        print(f"{'PASS' if ok else 'FAIL'} {name} (rc={r.returncode})")
        if not ok:
            tail = ((r.stderr or "") or (r.stdout or ""))[-250:]
            print("      ", tail.replace(chr(10), " | ")[:240])
    except Exception as e:
        RESULTS.append({"app": name, "ok": False, "rc": "?", "out": "", "err": str(e)})
        print(f"ERROR {name}: {e}")


def vpy(path):
    return os.path.join(path, "venv", "Scripts", "python.exe")


# 1. omnimedia
omni_py = vpy(r"C:\Users\LOQ\omnimedia-agency")
check("omnimedia-agency",
      f'"{omni_py}" -c "import main; print(\'OK\')"',
      cwd=r"C:\Users\LOQ\omnimedia-agency")

# 2. One-Agent
oneagent_py = vpy(r"C:\Users\LOQ\repo-audit\One-Agent")
check("One-Agent boot",
      f'"{oneagent_py}" -c "import main; print(\'OK\')"',
      cwd=r"C:\Users\LOQ\repo-audit\One-Agent")

# 3. ollama-evals server import
evals_py = vpy(r"C:\Users\LOQ\Documents\ollama-eval-system")
check("ollama-evals import",
      f'"{evals_py}" -c "from src import server; print(\'OK\')"',
      cwd=r"C:\Users\LOQ\Documents\ollama-eval-system")

# 4. teams-scraper cli
teams_py = vpy(r"C:\Users\LOQ\teams-task-scraper")
check("teams-scraper cli",
      f'"{teams_py}" -m teams_task_scraper.cli --help',
      cwd=r"C:\Users\LOQ\teams-task-scraper")

# 5. NovelForge exporter import
novel_py = vpy(r"C:\Users\LOQ\Documents\Migrated data\Initiatives\NovelForge")
check("NovelForge export module",
      f'"{novel_py}" -c "import sys; sys.path.insert(0,\'.\'); '
      f'from novel_forge.output import exporter; print(\'OK\')"',
      cwd=r"C:\Users\LOQ\Documents\Migrated data\Initiatives\NovelForge")

# 6. BA-QA suite (system python worked before)
check("BA-QA cli modules", f'"{PY}" cli.py modules', timeout=90,
      cwd=r"C:\Users\LOQ\Documents\Migrated data\AI-Evaluation-automation-system\legacy-curemd-ba-qa")

passed = sum(1 for r in RESULTS if r["ok"])
print()
print("=" * 50)
print(f"QA SWEEP ROUND 2: {passed}/{len(RESULTS)} passed")
with open(r"C:\Users\LOQ\session-audit-20260822\qa-sweep-round2.json", "w") as f:
    json.dump(RESULTS, f, indent=2)
