# AI Session Hub

A local **desktop app** that finds every AI chat / agent / CLI / IDE session on your computer,
imports them into one searchable library, renames and categorizes them by project and intent,
generates a **master prompt** for any conversation (a one-shot recap you can paste into any tool),
and **exports** any session back into the native cache format of any supported AI tool — so
migrating between tools is seamless.

> 🧲 **One hub. Any tool. Move sessions anywhere.**

---

## ✨ What it does

- **Discovers** session data from 15+ AI tools, agents, IDEs, CLIs, and desktop apps in one scan.
- **Imports** everything into a single neutral, searchable SQLite library (full-text search built in).
- **Renames & categorizes** sessions by the project they belong to and the instructions in them.
- **Generates a Master Prompt** for any session — a compact "re-run this" / "quick recap" prompt
  you can paste into any tool to resume or replicate the work.
- **Exports bidirectionally** — any imported session can be written back into the native cache of
  any supported tool, so moving between tools never loses context.
- Runs **100% locally** — your chats never leave your machine.

---

## 🛠 Supported tools (import + export)

| Tool / Agent | Discover & Import | Export to native cache |
|--------------|:---:|:---:|
| Hermes | ✅ SQLite (`state.db`) | ✅ |
| Claude Code | ✅ JSONL | ✅ |
| Codex CLI | ✅ JSONL rollouts | ✅ |
| Gemini Antigravity | ✅ `.pb` / pbtxt | ⚠️ metadata |
| Gemini CLI | ✅ `history.jsonl` | ✅ |
| Codeium / Windsurf | ✅ `.pb` chat state | ⚠️ |
| OpenClaw | ✅ JSONL sessions | ✅ |
| Goose | ✅ JSON chat exports | ✅ |
| ChatGPT desktop | ✅ config / exports | ⚠️ |
| Trae | ✅ config + worktrees | ✅ |
| Cursor | ✅ agent transcripts | ✅ |
| Cline | ✅ task history | ✅ |
| Copilot | ✅ IDE logs | ⚠️ |
| ZAI / CherryStudio / Tabnine | ✅ logs / config | ⚠️ |
| Generic (Markdown / JSON / TXT) | ✅ any folder | ✅ |

> ⚠️ = file is stored server-side or in an opaque binary format; the tool is indexed (discovered,
> renamed, categorized, master-prompted, and exportable to other tools) but its *native* cache
> cannot be rewritten in-place. You can still export these sessions to **any** other tool.

---

## 📦 Quick start

Requires **Python 3.9+** and `pip`.

```bash
git clone https://github.com/mhsaeed786/ai-session-hub.git
cd ai-session-hub

# Windows
setup.bat

# macOS / Linux
./setup.sh
```

Or manually:

```bash
python -m venv venv
venv\Scripts\activate        # Windows  (or: source venv/bin/activate on Mac/Linux)
pip install -r requirements.txt
```

Then start the app:

```bash
python run.py --sync --serve
```

Open **http://127.0.0.1:5100** — the dashboard shows every session it found, auto-named and
categorized.

### Common commands

| Command | What it does |
|---------|--------------|
| `python run.py --sync` | Incrementally scan all tools and import new/changed sessions |
| `python run.py --sync-all` | Force a full re-scan of every tool |
| `python run.py --serve` | Start the web dashboard only |
| `python run.py --sync --serve` | Sync, then open the dashboard |
| `python run.py --master-prompts --out prompts.txt` | Export a master-prompt file for all sessions |
| `python run.py --export --tool claude --session <id>` | Export one session into a tool's native cache |

---

## 🖥 The dashboard

- **Dashboard** — totals, sessions per tool, recent sessions.
- **Browse** — filter by tool, project, date; full-text search across every message.
- **Session detail** — full readable transcript with role/mode coloring.
- **Categorize** — sessions are auto-tagged by project and intent; you can rename and re-tag any
  session.
- **Master Prompt** — one click generates a paste-ready recap prompt for a session.
- **Export** — pick a destination tool and push any session into that tool's native format.

---

## 🧠 How categorization works

Every session is analyzed to determine:

- **Project** — the working directory / repo it ran in (from metadata), or the project most
  frequently mentioned in its messages.
- **Intent / category** — e.g. `FHIR`, `web-app`, `data`, `automation`, `research`, `music`,
  `docs`, `devops`, `learning`, `other`. Based on the instructions inside the chat.

Categorization uses lightweight keyword heuristics so it works offline with zero cost, and every
result can be manually overridden in the UI.

---

## 🔁 Bidirectional export

The hub uses a **neutral session format** internally. Each tool has two adapter halves:

- an **importer** (tool native → neutral)
- an **exporter** (neutral → tool native)

So a Claude Code session can be exported to Codex, a Goose chat to Hermes, an OpenClaw session to
Claude Code, and so on. This is what makes migration between tools seamless.

---

## 🧾 Master prompt

For any session the hub generates a **master prompt**:

```
[SESSION] Project Dashboard — Claude Code
[OBJECTIVE] "Build a React dashboard with Tailwind UI ..."
[KEY DECISIONS] <top themes from the conversation>
[RESUME INSTRUCTIONS] <condensed, paste-ready prompt>
```

Paste it into any tool to resume the work or get a fast recap without digging through the raw chat.

---

## 🗂 Project structure

```
ai-session-hub/
├── run.py                # CLI entry point
├── config.py             # tool paths + settings
├── setup.bat / setup.sh  # one-click install
├── requirements.txt
├── db/
│   ├── schema.sql        # neutral session library schema (SQLite + FTS5)
│   └── session_hub.db    # generated library (not committed)
├── adapters/             # one importer+exporter pair per tool
│   ├── base.py           # ParsedSession / ParsedMessage / BaseAdapter
│   ├── claude_code.py, codex.py, goose.py, hermes.py,
│   ├── openclaw.py, gemini_cli.py, gemini_antigravity.py,
│   ├── codeium.py, chatgpt.py, cursor.py, cline.py, trae.py,
│   ├── copilot.py, zai.py, cherrystudio.py, generic.py, stub.py
│   └── __init__.py       # adapter registry
├── core/
│   ├── sync.py           # discovery + import engine
│   ├── categorize.py     # project + intent tagging
│   ├── master_prompt.py  # master-prompt generator
│   └── export.py         # neutral → tool-native exporter
├── web/
│   ├── app.py            # Flask app
│   ├── api.py            # REST endpoints
│   └── static/           # dashboard (HTML/CSS/JS)
└── tools/
    └── extract_master_prompts.py
```

---

## 🔒 Privacy & safety

- Everything runs locally. No cloud, no telemetry, no API keys required.
- The importer **only reads** source files — it never modifies or overwrites your tools' data.
- The exporter writes to a **new** location per tool; it backs up any existing destination file
  as `.hub.bak` before writing, so nothing is ever lost.
- Credentials / `auth.json` / `.env` files are **never** read or migrated.

---

## 🧪 Testing

```bash
python -m pytest tests/ -q        # adapter + engine unit tests
python run.py --sync --serve      # manual smoke test
```

---

## 📄 License

MIT — free to use, modify, and share.

---

Built with ❤️ to end the "sessions are trapped in this one tool" problem.
