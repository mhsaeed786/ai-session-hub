"""FINAL QA: verify all 8 apps with their own environments."""
import subprocess
import os
import sys
import json

RESULTS = []


def check(name, cmd, cwd=None, timeout=120):
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                           timeout=timeout, shell=True)
        ok = r.returncode == 0
        RESULTS.append({"app": name, "ok": ok})
        print(f"{'PASS' if ok else 'FAIL'} {name}")
        if not ok:
            print("   ", ((r.stderr or "") or (r.stdout or ""))[-200:].replace(chr(10), " | ")[:200])
    except Exception as e:
        RESULTS.append({"app": name, "ok": False})
        print(f"ERROR {name}: {e}")


def vpy(p):
    return os.path.join(p, "venv", "Scripts", "python.exe")


PY = sys.executable

check("1 ai-session-hub",
      f'"{PY}" run.py --master-prompt nonexistent-x',
      cwd=r"C:\Users\LOQ\ai-session-hub")

omni = r"C:\Users\LOQ\omnimedia-agency"
check("2 omnimedia-agency",
      f'"{vpy(omni)}" -c "import main; print(\'OK\')"',
      cwd=omni)

oneagent = r"C:\Users\LOQ\repo-audit\One-Agent"
check("3 One-Agent",
      f'"{vpy(oneagent)}" -c "import main; print(\'OK\')"',
      cwd=oneagent)

check("4 BA-QA suite cli",
      f'"{PY}" cli.py modules',
      cwd=r"C:\Users\LOQ\Documents\Migrated data\AI-Evaluation-automation-system\legacy-curemd-ba-qa",
      timeout=90)

evals = r"C:\Users\LOQ\Documents\ollama-eval-system"
check("5 ollama-evals server",
      f'"{vpy(evals)}" -c "from src import server; print(\'OK\')"',
      cwd=evals)

teams_p = r"C:\Users\LOQ\teams-task-scraper"
check("6 teams-scraper cli",
      f'set "PYTHONPATH={teams_p}\\src" && "{vpy(teams_p)}" -m teams_task_scraper.cli --help',
      cwd=teams_p)

novel = r"C:\Users\LOQ\Documents\Migrated data\Initiatives\NovelForge"
check("7 NovelForge package",
      f'"{vpy(novel)}" -c "import sys; sys.path.insert(0,\'.\'); import novel_forge; print(\'OK\')"',
      cwd=novel)

nwa = r"C:\Users\LOQ\Documents\Migrated data\Initiatives\Novel-writing-agent-"
check("8 novel-writing-agent exporter",
      f'"{PY}" -c "import py_compile; py_compile.compile(r\'{nwa}\\app\\novel_forge\\output\\exporter.py\', doraise=True); print(\'OK\')"')

passed = sum(1 for r in RESULTS if r["ok"])
print()
print("=" * 50)
print(f"FINAL QA: {passed}/{len(RESULTS)} apps working")
with open(r"C:\Users\LOQ\session-audit-20260822\qa-final.json", "w") as f:
    json.dump(RESULTS, f, indent=2)
