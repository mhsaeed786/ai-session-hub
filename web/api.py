"""REST API endpoints for AI Session Hub."""

import sqlite3
from flask import Flask, jsonify, request

from config import DB_PATH, all_tool_names


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def register_routes(app: Flask):
    """Register all API routes on the Flask app."""

    # --- Tools ---
    @app.route("/api/tools")
    def api_tools():
        conn = get_db()
        tools = conn.execute(
            "SELECT name, display_name, data_path, enabled, last_sync_at, "
            "session_count, total_size_mb FROM tools ORDER BY display_name"
        ).fetchall()
        conn.close()
        return jsonify([dict(t) for t in tools])

    # --- Tool names available for export ---
    @app.route("/api/targets")
    def api_targets():
        return jsonify({"tools": all_tool_names()})

    # --- Stats ---
    @app.route("/api/stats")
    def api_stats():
        conn = get_db()
        total_sessions = conn.execute("SELECT COUNT(*) c FROM sessions").fetchone()["c"]
        total_messages = conn.execute("SELECT COUNT(*) c FROM messages").fetchone()["c"]
        total_size = conn.execute(
            "SELECT COALESCE(SUM(file_size_bytes),0) s FROM sessions").fetchone()["s"]
        tools_with_data = conn.execute(
            "SELECT COUNT(DISTINCT tool) c FROM sessions").fetchone()["c"]
        by_tool = conn.execute(
            "SELECT tool, COUNT(*) count FROM sessions GROUP BY tool ORDER BY count DESC"
        ).fetchall()
        by_category = conn.execute(
            "SELECT category, COUNT(*) count FROM sessions WHERE category IS NOT NULL "
            "GROUP BY category ORDER BY count DESC").fetchall()
        recent = conn.execute(
            "SELECT id, tool, title, category, started_at, message_count FROM sessions "
            "ORDER BY COALESCE(started_at, first_synced_at) DESC LIMIT 10").fetchall()
        last_sync = conn.execute(
            "SELECT MAX(sync_ended_at) t FROM sync_log WHERE status != 'running'"
        ).fetchone()["t"]
        conn.close()
        return jsonify({
            "total_sessions": total_sessions,
            "total_messages": total_messages,
            "total_size_mb": round(total_size / 1048576, 2),
            "tools_with_data": tools_with_data,
            "by_tool": [dict(r) for r in by_tool],
            "by_category": [dict(r) for r in by_category],
            "recent_sessions": [dict(r) for r in recent],
            "last_sync": last_sync,
        })

    # --- Sessions List ---
    @app.route("/api/sessions")
    def api_sessions():
        conn = get_db()
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 30, type=int)
        tool = request.args.get("tool", "")
        search = request.args.get("search", "")
        date_from = request.args.get("date_from", "")
        date_to = request.args.get("date_to", "")
        project = request.args.get("project", "")
        category = request.args.get("category", "")

        where = []
        params = []
        if tool:
            where.append("s.tool = ?"); params.append(tool)
        if category:
            where.append("s.category = ?"); params.append(category)
        if date_from:
            where.append("s.started_at >= ?"); params.append(date_from)
        if date_to:
            where.append("s.started_at <= ?"); params.append(date_to)
        if project:
            where.append("s.project_path LIKE ?"); params.append(f"%{project}%")
        if search:
            where.append("""s.id IN (
                SELECT m.session_fk FROM messages m
                JOIN messages_fts fts ON m.id = fts.rowid
                WHERE messages_fts MATCH ?)""")
            params.append(search)
        where_sql = (" WHERE " + " AND ".join(where)) if where else ""

        total = conn.execute(f"SELECT COUNT(*) c FROM sessions s{where_sql}", params).fetchone()["c"]
        offset = (page - 1) * per_page
        rows = conn.execute(f"""
            SELECT s.id, s.tool, s.session_id, s.title, s.project_path,
                   s.model, s.status, s.started_at, s.ended_at, s.category,
                   s.tags, s.message_count, s.file_size_bytes, s.master_prompt,
                   s.last_synced_at
            FROM sessions s {where_sql}
            ORDER BY COALESCE(s.started_at, s.first_synced_at) DESC
            LIMIT ? OFFSET ?""", params + [per_page, offset]).fetchall()
        conn.close()
        return jsonify({"sessions": [dict(r) for r in rows], "total": total,
                        "page": page, "per_page": per_page,
                        "total_pages": (total + per_page - 1) // per_page})

    # --- Session Detail ---
    @app.route("/api/sessions/<path:session_id>")
    def api_session_detail(session_id):
        conn = get_db()
        session = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
        if not session:
            conn.close()
            return jsonify({"error": "Session not found"}), 404
        messages = conn.execute(
            "SELECT id, message_id, role, content_text, content_type, model, "
            "timestamp, token_input, token_output, parent_id, seq "
            "FROM messages WHERE session_fk=? ORDER BY seq, id", (session_id,)).fetchall()
        conn.close()
        return jsonify({"session": dict(session), "messages": [dict(m) for m in messages]})

    # --- Update session (rename / re-categorize) ---
    @app.route("/api/sessions/<path:session_id>", methods=["PATCH"])
    def api_session_update(session_id):
        conn = get_db()
        data = request.get_json(force=True, silent=True) or {}
        fields = []
        params = []
        for key in ("title", "category", "tags", "project_path", "master_prompt"):
            if key in data:
                fields.append(f"{key}=?")
                params.append(data[key])
        if not fields:
            conn.close()
            return jsonify({"error": "No fields to update"}), 400
        params.append(session_id)
        conn.execute(f"UPDATE sessions SET {', '.join(fields)} WHERE id=?", params)
        conn.commit()
        conn.close()
        return jsonify({"status": "ok"})

    # --- Master Prompt ---
    @app.route("/api/sessions/<path:session_id>/master-prompt")
    def api_master_prompt(session_id):
        from core.master_prompt import build_master_prompt
        mode = request.args.get("mode", "replicate")
        return jsonify({"master_prompt": build_master_prompt(session_id, mode=mode)})

    # --- Categorize all ---
    @app.route("/api/categorize", methods=["POST"])
    def api_categorize():
        from core.categorize import enrich_all_sessions
        summary = enrich_all_sessions(dry_run=False)
        return jsonify({"status": "ok", **summary})

    # --- Export ---
    @app.route("/api/export", methods=["POST"])
    def api_export():
        from core.export import export_session
        data = request.get_json(force=True, silent=True) or {}
        sid = data.get("session_id")
        target = data.get("target_tool")
        dest = data.get("destination_dir") or None
        if not sid or not target:
            return jsonify({"error": "session_id and target_tool required"}), 400
        result = export_session(sid, target, dest)
        return jsonify(result)

    # --- Trigger Sync ---
    @app.route("/api/sync", methods=["POST"])
    def api_sync():
        from core.sync import SyncEngine
        from core.categorize import enrich_all_sessions
        try:
            engine = SyncEngine(force_full=False)
            results = engine.run_all()
            enrich_all_sessions(dry_run=False)
            return jsonify({"status": "ok", "results": results})
        except Exception as e:
            return jsonify({"status": "error", "error": str(e)}), 500

    # --- Projects ---
    @app.route("/api/projects")
    def api_projects():
        conn = get_db()
        projects = conn.execute(
            "SELECT project_path, COUNT(*) session_count FROM sessions "
            "WHERE project_path IS NOT NULL AND project_path != '' "
            "GROUP BY project_path ORDER BY session_count DESC").fetchall()
        conn.close()
        return jsonify([dict(p) for p in projects])

    # --- Search ---
    @app.route("/api/search")
    def api_search():
        conn = get_db()
        q = request.args.get("q", "")
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 30, type=int)
        if not q:
            conn.close()
            return jsonify({"results": [], "total": 0})
        try:
            offset = (page - 1) * per_page
            total = conn.execute(
                "SELECT COUNT(*) c FROM messages_fts WHERE messages_fts MATCH ?",
                (q,)).fetchone()["c"]
            results = conn.execute("""
                SELECT m.id, m.session_fk, m.role, m.content_text, m.content_type,
                       m.timestamp, m.seq, s.tool, s.title session_title
                FROM messages_fts fts
                JOIN messages m ON m.id = fts.rowid
                JOIN sessions s ON s.id = m.session_fk
                WHERE messages_fts MATCH ? ORDER BY rank LIMIT ? OFFSET ?
            """, (q, per_page, offset)).fetchall()
            conn.close()
            return jsonify({"results": [dict(r) for r in results], "total": total,
                            "page": page, "per_page": per_page})
        except Exception as e:
            conn.close()
            return jsonify({"results": [], "total": 0, "error": str(e)})

    # ======================== PRICING ========================

    @app.route("/api/pricing")
    def api_pricing():
        """Return pricing for all known models."""
        from core.pricing import get_pricing, DEFAULT_PRICING
        pricing = []
        for model, rates in DEFAULT_PRICING.items():
            pricing.append({"model": model, **rates})
        return jsonify({"pricing": pricing})

    @app.route("/api/pricing/scrape", methods=["POST"])
    def api_pricing_scrape():
        """Scrape current pricing from public sources via Playwright."""
        from tools.pricing_scraper import scrape_all
        results = scrape_all(headless=True)
        return jsonify({"status": "ok", "results": results})

    @app.route("/api/pricing/update", methods=["POST"])
    def api_pricing_update():
        """Update pricing with user-provided values."""
        from core.pricing import DEFAULT_PRICING
        from core.sync import get_conn
        data = request.get_json(force=True, silent=True) or {}
        model = data.get("model")
        rates = data.get("rates")
        if not model or not rates:
            return jsonify({"error": "model and rates required"}), 400
        DEFAULT_PRICING[model.lower()] = rates
        conn = get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO pricing_cache (model, provider, input_per_million, "
            "output_per_million, cache_read_per_million, cache_write_per_million, "
            "source_url, scraped_at, raw_text) VALUES (?,?,?,?,?,?,?,?,?)",
            (model.lower(), rates.get("source", "manual"), rates.get("input"),
             rates.get("output"), rates.get("cache_read"), rates.get("cache_write"),
             "manual", __import__("datetime").datetime.now(
                 __import__("datetime").timezone.utc).isoformat(), str(rates)))
        conn.commit()
        conn.close()
        return jsonify({"status": "ok", "model": model, "rates": rates})

    # ======================== COSTS ========================

    @app.route("/api/costs")
    def api_costs():
        """Return cost summary across all sessions."""
        from core.pricing import get_cost_summary
        return jsonify(get_cost_summary())

    @app.route("/api/costs/compute", methods=["POST"])
    def api_costs_compute():
        """Re-compute costs for all sessions."""
        from core.pricing import enrich_all_costs
        result = enrich_all_costs()
        return jsonify({"status": "ok", **result})

    @app.route("/api/sessions/<path:session_id>/cost")
    def api_session_cost(session_id):
        """Return cost breakdown for a single session."""
        from core.pricing import calculate_session_cost
        conn = get_db()
        row = conn.execute(
            "SELECT model, input_tokens, output_tokens, cache_read_tokens, "
            "cache_write_tokens, reasoning_tokens FROM sessions WHERE id=?",
            (session_id,)).fetchone()
        conn.close()
        if not row:
            return jsonify({"error": "Session not found"}), 404
        cost = calculate_session_cost(
            model=row["model"] or "",
            input_tokens=row["input_tokens"] or 0,
            output_tokens=row["output_tokens"] or 0,
            cache_read=row["cache_read_tokens"] or 0,
            cache_write=row["cache_write_tokens"] or 0,
            reasoning=row["reasoning_tokens"] or 0,
        )
        return jsonify(cost)

    # ======================== DEEP SCAN ========================

    @app.route("/api/deep-scan", methods=["POST"])
    def api_deep_scan():
        """Scan the whole PC for session folders."""
        from core.deepscan import scan_and_import_deep
        data = request.get_json(force=True, silent=True) or {}
        paths = data.get("paths", None)
        result = scan_and_import_deep(paths)
        return jsonify({"status": "ok", **result})

    @app.route("/api/deep-scan/preview", methods=["GET"])
    def api_deep_scan_preview():
        """Preview folders without importing."""
        from core.deepscan import deep_scan
        result = deep_scan()
        return jsonify(result)

    # ======================== DEDUP ========================

    @app.route("/api/duplicates")
    def api_duplicates():
        """Find duplicate sessions."""
        from core.dedup import find_duplicates
        return jsonify(find_duplicates())

    @app.route("/api/duplicates/merge", methods=["POST"])
    def api_duplicates_merge():
        """Merge duplicate sessions."""
        from core.dedup import merge_duplicates
        data = request.get_json(force=True, silent=True) or {}
        keep = data.get("keep")
        remove_ids = data.get("remove_ids", [])
        if not keep or not remove_ids:
            return jsonify({"error": "keep and remove_ids required"}), 400
        result = merge_duplicates(keep, remove_ids)
        return jsonify({"status": "ok", **result})

    # ======================== SAFE DELETE ========================

    @app.route("/api/sessions/<path:session_id>", methods=["DELETE"])
    def api_session_delete(session_id):
        """Delete a single session."""
        conn = get_db()
        conn.execute("DELETE FROM messages WHERE session_fk=?", (session_id,))
        conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))
        conn.commit()
        conn.close()
        return jsonify({"status": "ok", "deleted": session_id})

    @app.route("/api/sessions/batch-delete", methods=["POST"])
    def api_batch_delete():
        """Delete multiple sessions."""
        data = request.get_json(force=True, silent=True) or {}
        ids = data.get("ids", [])
        if not ids:
            return jsonify({"error": "ids required"}), 400
        conn = get_db()
        for sid in ids:
            conn.execute("DELETE FROM messages WHERE session_fk=?", (sid,))
            conn.execute("DELETE FROM sessions WHERE id=?", (sid,))
        conn.commit()
        conn.close()
        return jsonify({"status": "ok", "deleted": len(ids)})

    @app.route("/api/sessions/delete-all", methods=["POST"])
    def api_delete_all():
        """Delete ALL sessions (nuclear option)."""
        data = request.get_json(force=True, silent=True) or {}
        confirm = data.get("confirm")
        if confirm != "DELETE_ALL":
            return jsonify({"error": "Set confirm: 'DELETE_ALL' to proceed"}), 400
        conn = get_db()
        conn.execute("DELETE FROM messages")
        conn.execute("DELETE FROM sessions")
        conn.commit()
        conn.close()
        return jsonify({"status": "ok", "deleted": "all"})

    # ======================== EXHAUSTIVE AGENT SCAN ========================

    @app.route("/api/agents/discover", methods=["GET"])
    def api_agents_discover():
        """Discover all AI agents/tools installed on this PC."""
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
                agents.append({"name": name, "path": path, "found": True})
        return jsonify({"agents": agents, "total": len(agents)})
