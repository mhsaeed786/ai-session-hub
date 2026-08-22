"""AI Session Hub — entry point.

Usage:
    python run.py --sync          # Run incremental sync
    python run.py --sync-all      # Force full re-sync
    python run.py --serve         # Start web server
    python run.py --sync --serve  # Sync then serve
    python run.py --categorize    # Re-categorize / re-title all sessions
    python run.py --master-prompts --out FILE   # Export master prompts
    python run.py --master-prompt SESSION_ID   # Print one master prompt
    python run.py --export --tool TARGET --session ID   # Export one session
"""

import argparse
import os
import sqlite3
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)


def init_db():
    """Create the database and apply schema + register tools."""
    from config import DB_PATH, SCHEMA_PATH, TOOL_CONFIGS
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    for name, cfg in TOOL_CONFIGS.items():
        conn.execute(
            """INSERT OR IGNORE INTO tools
               (name, display_name, adapter_class, data_path, enabled)
               VALUES (?, ?, ?, ?, ?)""",
            (name, cfg["display_name"], cfg["adapter_class"],
             cfg["data_path"], int(cfg["enabled"])))
    conn.commit()
    conn.close()
    print(f"[init] Database ready at {DB_PATH}")


def run_sync(force_full=False):
    from core.sync import SyncEngine
    engine = SyncEngine(force_full=force_full)
    results = engine.run_all()
    print("\n=== Sync Results ===")
    for tool, stats in results.items():
        status = stats.get("status", "unknown")
        found = stats.get("found", 0)
        new = stats.get("new", 0)
        updated = stats.get("updated", 0)
        print(f"  {tool}: {status} | found={found} new={new} updated={updated}")
    print("====================\n")
    return results


def run_categorize():
    from core.categorize import enrich_all_sessions
    summary = enrich_all_sessions(dry_run=False)
    print(f"[categorize] Updated {summary['updated']} sessions (category + title).")


def run_costs():
    from core.pricing import enrich_all_costs, get_cost_summary
    enrich_all_costs()
    s = get_cost_summary()
    print("\n=== Cost Summary ===")
    print(f"  Total sessions:    {s['total_sessions']}")
    print(f"  Sessions priced:   {s['priced_sessions']}")
    print(f"  Total cost:        ${s['total_cost_usd']}")
    print(f"  Total API calls:   {s['total_api_calls']}")
    print("\n  By tool:")
    for r in s['by_tool']:
        print(f"    {r['tool']}: ${r['cost']} ({r['api_calls']} calls)")
    print("\n  By model:")
    for r in s['by_model']:
        print(f"    {r['model']}: ${r['cost']} ({r['api_calls']} calls, {r['sessions']} sessions)")
    print("====================\n")


def run_deep_scan():
    from core.deepscan import scan_and_import_deep
    r = scan_and_import_deep()
    print(f"\nDeep scan found {r['folders_found']} folders, imported {r['sessions_imported']} sessions.")


def run_dedup():
    from core.dedup import find_duplicates
    d = find_duplicates()
    print(f"\nFound {d['total_dup_groups']} duplicate groups.")


def run_agents():
    import os
    from config import HOME
    agents = []
    known = {
        ".claude": "Claude Code", ".codex": "Codex CLI", ".openclaw": "OpenClaw",
        ".gemini": "Gemini", ".hermes": "Hermes", ".trae": "Trae",
        ".cursor": "Cursor", ".cline": "Cline", ".chatgpt": "ChatGPT",
        ".codeium": "Codeium/Windsurf", ".copilot": "GitHub Copilot",
        ".zai": "Z.AI", ".cherrystudio": "Cherry Studio", ".tabnine": "Tabnine",
        ".ollama": "Ollama", ".agents": "Agents", ".oneagent": "OneAgent",
        ".zcode": "ZCode", ".antigravity": "Antigravity",
    }
    for dotdir, name in known.items():
        path = os.path.join(HOME, dotdir)
        if os.path.isdir(path):
            agents.append({"name": name, "path": path})
    print(f"\nFound {len(agents)} AI agents installed:")
    for a in agents:
        print(f"  {a['name']}: {a['path']}")


def run_master_prompts(out_path):
    from core.master_prompt import build_master_prompt
    from core.sync import get_conn
    conn = get_conn()
    rows = conn.execute("SELECT id FROM sessions ORDER BY started_at DESC").fetchall()
    conn.close()
    blocks = []
    for row in rows:
        blocks.append(build_master_prompt(row["id"], mode="replicate"))
    text = "\n\n".join(blocks)
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"[master-prompts] Wrote {len(rows)} master prompts to {out_path}")
    else:
        print(text)


def run_server():
    from web.app import create_app
    from config import WEB_HOST, WEB_PORT
    app = create_app()
    print(f"[serve] AI Session Hub running at http://{WEB_HOST}:{WEB_PORT}")
    app.run(host=WEB_HOST, port=WEB_PORT, debug=False)


def main():
    parser = argparse.ArgumentParser(description="AI Session Hub")
    parser.add_argument("--sync", action="store_true", help="Run incremental sync")
    parser.add_argument("--sync-all", action="store_true", help="Force full re-sync")
    parser.add_argument("--serve", action="store_true", help="Start web server")
    parser.add_argument("--categorize", action="store_true",
                        help="Re-categorize / re-title all sessions")
    parser.add_argument("--master-prompts", action="store_true",
                        help="Export master prompts for all sessions")
    parser.add_argument("--master-prompt", type=str, default=None,
                        metavar="SESSION_ID", help="Print one session's master prompt")
    parser.add_argument("--out", type=str, default=None, metavar="FILE",
                        help="Output file for --master-prompts")
    parser.add_argument("--export", action="store_true",
                        help="Export a session to a tool's native cache")
    parser.add_argument("--tool", type=str, default=None, metavar="TARGET",
                        help="Target tool for --export")
    parser.add_argument("--session", type=str, default=None, metavar="SESSION_ID",
                        help="Session id for --export")
    parser.add_argument("--costs", action="store_true",
                        help="Compute and display costs")
    parser.add_argument("--deep-scan", action="store_true",
                        help="Deep scan PC for session folders")
    parser.add_argument("--dedup", action="store_true",
                        help="Find duplicate sessions")
    parser.add_argument("--agents", action="store_true",
                        help="Discover installed AI agents")
    parser.add_argument("--delete", type=str, default=None, metavar="SESSION_ID",
                        help="Delete a session")
    parser.add_argument("--delete-all", action="store_true",
                        help="Delete ALL sessions")
    args = parser.parse_args()

    any_action = (args.sync or args.sync_all or args.serve or args.categorize
                  or args.master_prompts or args.master_prompt or args.export
                  or args.costs or args.deep_scan or args.dedup or args.agents
                  or args.delete or args.delete_all)
    if not any_action:
        parser.print_help()
        sys.exit(1)

    init_db()

    if args.sync or args.sync_all:
        run_sync(force_full=args.sync_all)

    if args.categorize:
        run_categorize()

    if args.costs:
        run_costs()

    if args.deep_scan:
        run_deep_scan()

    if args.dedup:
        run_dedup()

    if args.agents:
        run_agents()

    if args.master_prompts:
        run_master_prompts(args.out)

    if args.master_prompt:
        from core.master_prompt import build_master_prompt
        print(build_master_prompt(args.master_prompt, mode="replicate"))

    if args.export:
        if not args.tool or not args.session:
            print("--export requires --tool TARGET and --session SESSION_ID")
            sys.exit(1)
        from core.export import export_session
        result = export_session(args.session, args.tool)
        print(result)

    if args.delete:
        from core.sync import get_conn
        conn = get_conn()
        conn.execute("DELETE FROM messages WHERE session_fk=?", (args.delete,))
        conn.execute("DELETE FROM sessions WHERE id=?", (args.delete,))
        conn.commit()
        conn.close()
        print(f"Deleted session: {args.delete}")

    if args.delete_all:
        from core.sync import get_conn
        conn = get_conn()
        conn.execute("DELETE FROM messages")
        conn.execute("DELETE FROM sessions")
        conn.commit()
        conn.close()
        print("Deleted ALL sessions.")

    if args.serve:
        run_server()


if __name__ == "__main__":
    main()
