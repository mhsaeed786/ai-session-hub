"""Wire OpenRouter into central secrets + baqa settings for the SuperApp."""
import os
import re

# 1. extract key from known files (without printing it)
key = None
for path in [r"C:\Users\LOQ\Downloads\API keys to be used.txt",
             r"C:\Users\LOQ\AppData\Local\hermes\.env"]:
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            content = f.read(200000)
    except OSError:
        continue
    m = re.search(r"OPENROUTER_API_KEY\s*[=:]\s*['\"]?(sk-or-[A-Za-z0-9_\-]+)",
                  content) or re.search(r"(sk-or-[A-Za-z0-9_\-]{30,})", content)
    if m:
        key = m.group(1)
        print(f"key found in {os.path.basename(path)} ({key[:9]}...{key[-4:]})")
        break

if not key:
    print("no OpenRouter key found")
    raise SystemExit(1)

# 2. add to central secrets .env if not present
env_path = r"C:\Users\LOQ\secrets\.env.central"
with open(env_path, encoding="utf-8") as f:
    existing = f.read()
if "OPENROUTER_API_KEY=" not in existing:
    with open(env_path, "a", encoding="utf-8") as f:
        if not existing.endswith("\n"):
            f.write("\n")
        f.write(f"OPENROUTER_API_KEY={key}\n")
        # baqa settings read these env names too
        f.write(f"OPENAI_API_KEY={key}\n")
        f.write("OPENAI_BASE_URL=https://openrouter.ai/api/v1\n")
    print("added OPENROUTER_API_KEY + OPENAI_* aliases to central secrets")
else:
    print("already in central secrets")

# 3. create a loader snippet for superapp that injects env vars at startup
loader = r"C:\Users\LOQ\secrets\load_env.py"
with open(loader, "w", encoding="utf-8", newline="") as f:
    f.write('''"""Load central secrets into process env - import before anything else."""
import os
from pathlib import Path

_ENV = Path(__file__).parent / ".env.central"

if _ENV.exists():
    with open(_ENV, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip()
            v = v.strip()
            if k and v and k not in os.environ:
                os.environ[k] = v
''')
print("wrote load_env.py helper")

# 4. patch superapp.py to call load_env first
sp = r"C:\Users\LOQ\super-app\superapp.py"
with open(sp, encoding="utf-8") as f:
    spc = f.read()
if "load_env" not in spc:
    spc = spc.replace(
        'ROOT = Path(__file__).parent',
        'sys.path.insert(0, r"C:\\Users\\LOQ\\secrets")\n'
        'import load_env  # noqa: F401 - injects API keys into env\n'
        '\n'
        'ROOT = Path(__file__).parent')
    with open(sp, "w", encoding="utf-8", newline="") as f:
        f.write(spc)
    print("patched superapp.py to load env")
