"""Rename the 21 newly imported Goose sessions to meaningful titles."""
import subprocess

RENAMES = {
    "20260829_051628_64ff5e": "Goose - Unified AI Frontend MCP Server",
    "20260829_051627_0fa4c8": "Goose - Udemy Autonomous Learning System",
    "20260829_051626_9cceb8": "Goose - Sync code folders",
    "20260829_051625_ea5fdf": "Goose - Reorganize folders and commit",
    "20260829_051624_903b1a": "Goose - OpenClaw CLI installation troubleshooting",
    "20260829_051624_14ef06": "Goose - Multi-language programming tutorial",
    "20260829_051623_781db4": "Goose - Refusal test conversation",
    "20260829_051622_fb3740": "Goose - Healthcare IT Career Transformation",
    "20260829_051621_70629b": "Goose - Goose task automation",
    "20260829_051620_b5fd45": "Goose - Goose MCP extensions",
    "20260829_051619_ebbb91": "Goose - Goose distributed chat apps",
    "20260829_051618_e5c194": "Goose - GitHub sync all code",
    "20260829_051617_efe9cf": "Goose - FHIR developer portal creation",
    "20260829_051616_785415": "Goose - Create AI Super app",
    "20260829_051615_9941aa": "Goose - Continuing goose chats",
    "20260829_051615_e8dd6b": "Goose - Application bat file audit",
    "20260829_051614_8024b1": "Goose - AI Super-Agent System",
    "20260829_051613_f4a6fd": "Goose - AI Social Super App",
    "20260829_051612_5992cb": "Goose - AI Novel Generator",
}

# the first two imported (alphabetically first) need their ids
import subprocess
r = subprocess.run(["hermes", "sessions", "list", "--limit", "40"],
                   capture_output=True, text=True)
found = {}
for line in r.stdout.splitlines():
    for sid in RENAMES:
        if sid in line:
            found[sid] = True

for sid, title in RENAMES.items():
    r = subprocess.run(["hermes", "sessions", "rename", sid, title],
                       capture_output=True, text=True)
    status = "OK" if r.returncode == 0 else (r.stderr or r.stdout).strip()[:60]
    print(f"{sid}: {status} -> {title}")
