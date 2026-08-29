"""Fix QA failures: create venvs + install deps for each project, then re-verify."""
import os
import subprocess
import sys

PROJECTS = [
    # (name, path, requirements file, test command)
    ("omnimedia-agency", r"C:\Users\LOQ\omnimedia-agency",
     "requirements.txt",
     f"{chr(92)}venv{chr(92)}Scripts{chr(92)}python.exe -c \"import main; print('omnimedia OK')\""),
    ("One-Agent", r"C:\Users\LOQ\repo-audit\One-Agent",
     None,
     f"{chr(92)}venv{chr(92)}Scripts{chr(92)}python.exe -c \"import main; print('oneagent OK')\""),
    ("ollama-evals", r"C:\Users\LOQ\Documents\ollama-eval-system",
     "requirements.txt",
     f"{chr(92)}venv{chr(92)}Scripts{chr(92)}python.exe -c \"from src import server; print('evals OK')\""),
    ("teams-scraper", r"C:\Users\LOQ\teams-task-scraper",
     "pyproject.toml",
     f"{chr(92)}venv{chr(92)}Scripts{chr(92)}python.exe -m teams_task_scraper.cli --help"),
    ("NovelForge", r"C:\Users\LOQ\Documents\Migrated data\Initiatives\NovelForge",
     None,
     f"{chr(92)}venv{chr(92)}Scripts{chr(92)}python.exe -c \"import sys; sys.path.insert(0,'.'); from novel_forge.output import exporter; print('novel OK')\""),
    ("FHIR-mappings", r"C:\Users\LOQ\Documents\Migrated data\_staging\FHIR-Mappings-builder",
     None,
     f"{chr(92)}venv{chr(92)}Scripts{chr(92)}pip.exe install -q openpyxl && "
     f"{chr(92)}venv{chr(92)}Scripts{chr(92)}python.exe -c \"import openpyxl; print('fhir OK')\""),
]

# deps discovered missing during sweep
EXTRA_DEPS = {
    "One-Agent": ["rich"],
    "ollama-evals": ["pyyaml", "flask"],
    "NovelForge": [],
    "FHIR-mappings": ["openpyxl"],
}


def run(cmd, cwd=None, timeout=600):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                          timeout=timeout, shell=True)


def main():
    only = sys.argv[1:] or [p[0] for p in PROJECTS]
    for name, path, reqfile, _test in PROJECTS:
        if name not in only:
            continue
        print(f"=== {name} ===")
        venv_dir = os.path.join(path, "venv")
        py = os.path.join(venv_dir, "Scripts", "python.exe")
        if not os.path.exists(py):
            print("  creating venv...")
            run(f'"{sys.executable}" -m venv venv', cwd=path)
        if not os.path.exists(py):
            print("  FAILED to create venv")
            continue

        req = os.path.join(path, reqfile) if reqfile else None
        if req and os.path.exists(req):
            print(f"  installing {reqfile}...")
            r = run(f'"{py}" -m pip install -q -r "{req}"', cwd=path, timeout=900)
            if r.returncode != 0:
                print("   ", (r.stderr or "")[-200:].replace(chr(10), " | "))
        for dep in EXTRA_DEPS.get(name, []):
            print(f"  installing extra: {dep}")
            run(f'"{py}" -m pip install -q {dep}', timeout=300)
        print("  done")


if __name__ == "__main__":
    main()
