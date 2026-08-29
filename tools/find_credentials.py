"""Find local files containing usable LLM API credentials (names only, no values printed)."""
import os
import re

HOME = r"C:\Users\LOQ"
CANDIDATES = [
    r"C:\Users\LOQ\Downloads\API keys to be used.txt",
    r"C:\Users\LOQ\.claude\settings.json",
    r"C:\Users\LOQ\.claude\settings.local.json",
    r"C:\Users\LOQ\AppData\Local\hermes\.env",
    r"C:\Users\LOQ\secrets\.env.central",
    r"C:\Users\LOQ\.codex\auth.json",
    r"C:\Users\LOQ\.gemini\antigravity-cli\antigravity-oauth-token",
]

PATTERNS = [
    ("OPENAI_API_KEY", r"OPENAI_API_KEY\s*[=:]\s*['\"]?([A-Za-z0-9_\-]{20,})"),
    ("sk- key", r"(sk-[A-Za-z0-9_\-]{20,})"),
    ("GROQ_API_KEY", r"GROQ_API_KEY\s*[=:]\s*['\"]?([A-Za-z0-9_\-]{20,})"),
    ("DEEPSEEK_API_KEY", r"DEEPSEEK_API_KEY\s*[=:]\s*['\"]?([A-Za-z0-9_\-]{20,})"),
    ("ANTHROPIC_API_KEY", r"ANTHROPIC_API_KEY\s*[=:]\s*['\"]?([A-Za-z0-9_\-]{20,})"),
    ("GEMINI_API_KEY", r"(?:GEMINI|GOOGLE)_API_KEY\s*[=:]\s*['\"]?([A-Za-z0-9_\-]{20,})"),
    ("OPENROUTER_API_KEY", r"OPENROUTER_API_KEY\s*[=:]\s*['\"]?([A-Za-z0-9_\-]{20,})"),
]

print("Scanning for credential files (values masked)...")
for path in CANDIDATES:
    if not os.path.isfile(path):
        continue
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            content = f.read(200000)
    except OSError:
        continue
    found = []
    for label, pat in PATTERNS:
        m = re.search(pat, content)
        if m:
            val = m.group(1)
            masked = val[:6] + "..." + val[-4:] if len(val) > 14 else "***"
            found.append(f"{label}={masked}")
    if found:
        print(f"\n{path}")
        for x in found:
            print("   ", x)

# also scan Downloads dir for key files
dl = os.path.join(HOME, "Downloads")
if os.path.isdir(dl):
    for fn in os.listdir(dl):
        low = fn.lower()
        if ("key" in low or "token" in low or "api" in low) and \
                fn.endswith((".txt", ".json", ".env")):
            fp = os.path.join(dl, fn)
            try:
                with open(fp, encoding="utf-8", errors="replace") as f:
                    content = f.read(50000)
            except OSError:
                continue
            hits = []
            for label, pat in PATTERNS:
                if re.search(pat, content):
                    hits.append(label)
            print(f"\nDownloads/{fn}: {hits or '(exists, no known patterns)'}")
