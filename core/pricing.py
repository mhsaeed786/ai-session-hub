"""Pricing engine — tracks LLM pricing and calculates session costs.

Built-in pricing for common models (updated periodically). Costs are computed
from each session's token counts (input/output/cache) using the model's
current per-token rate.

Pricing sources scraped via Playwright from public model catalogs.
"""

import json
import os
import sqlite3
from datetime import datetime, timezone

from core.sync import get_conn

# Built-in pricing: model -> {input, output, cache_read, cache_write, reasoning, source}
# Prices are USD per 1M tokens. Updated by tools/pricing_scraper.py.
DEFAULT_PRICING = {
    # OpenAI
    "gpt-4o": {"input": 2.50, "output": 10.00, "cache_read": 1.25, "source": "openai"},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60, "cache_read": 0.075, "source": "openai"},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00, "cache_read": 2.50, "source": "openai"},
    "gpt-4": {"input": 30.00, "output": 60.00, "cache_read": 7.50, "source": "openai"},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50, "cache_read": 0.25, "source": "openai"},
    "o1": {"input": 15.00, "output": 60.00, "cache_read": 7.50, "source": "openai"},
    "o1-mini": {"input": 1.10, "output": 4.40, "cache_read": 0.55, "source": "openai"},
    "o3": {"input": 2.00, "output": 8.00, "cache_read": 0.50, "source": "openai"},
    "o3-mini": {"input": 1.10, "output": 4.40, "cache_read": 0.55, "source": "openai"},
    # Anthropic
    "claude-3-5-sonnet": {"input": 3.00, "output": 15.00, "cache_read": 0.30, "cache_write": 3.75, "source": "anthropic"},
    "claude-3-5-haiku": {"input": 0.80, "output": 4.00, "cache_read": 0.08, "cache_write": 1.00, "source": "anthropic"},
    "claude-3-opus": {"input": 15.00, "output": 75.00, "cache_read": 1.50, "cache_write": 18.75, "source": "anthropic"},
    "claude-3-sonnet": {"input": 3.00, "output": 15.00, "cache_read": 0.30, "cache_write": 3.75, "source": "anthropic"},
    "claude-3-haiku": {"input": 0.25, "output": 1.25, "cache_read": 0.03, "cache_write": 0.30, "source": "anthropic"},
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00, "cache_read": 0.30, "cache_write": 3.75, "source": "anthropic"},
    "claude-opus-4-20250514": {"input": 15.00, "output": 75.00, "cache_read": 1.50, "cache_write": 18.75, "source": "anthropic"},
    # Google
    "gemini-1.5-pro": {"input": 1.25, "output": 5.00, "cache_read": 0.31, "source": "google"},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30, "cache_read": 0.01875, "source": "google"},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40, "cache_read": 0.025, "source": "google"},
    "gemini-2.5-pro": {"input": 1.25, "output": 10.00, "cache_read": 0.31, "source": "google"},
    "gemini-2.5-flash": {"input": 0.15, "output": 0.60, "cache_read": 0.0375, "source": "google"},
    # DeepSeek
    "deepseek-chat": {"input": 0.27, "output": 1.10, "cache_read": 0.07, "source": "deepseek"},
    "deepseek-reasoner": {"input": 0.55, "output": 2.19, "cache_read": 0.14, "source": "deepseek"},
    "deepseek-v4-pro": {"input": 0.27, "output": 1.10, "cache_read": 0.07, "source": "deepseek"},
    # MiniMax
    "minimax-m2.7": {"input": 0.10, "output": 0.40, "cache_read": 0.025, "source": "minimax"},
    "minimax-m2.6": {"input": 0.10, "output": 0.40, "cache_read": 0.025, "source": "minimax"},
    "minimax-m3": {"input": 0.15, "output": 0.60, "cache_read": 0.0375, "source": "minimax"},
    # xAI
    "grok-2": {"input": 2.00, "output": 10.00, "cache_read": 0.50, "source": "xai"},
    "grok-3": {"input": 3.00, "output": 15.00, "cache_read": 0.75, "source": "xai"},
    # Mistral
    "mistral-large": {"input": 2.00, "output": 6.00, "cache_read": 0.50, "source": "mistral"},
    "mistral-small": {"input": 0.20, "output": 0.60, "cache_read": 0.05, "source": "mistral"},
    # Meta (via OpenRouter)
    "llama-3.1-405b": {"input": 2.70, "output": 2.70, "cache_read": 0.675, "source": "openrouter"},
    "llama-3.1-70b": {"input": 0.52, "output": 0.75, "cache_read": 0.13, "source": "openrouter"},
    "llama-3.1-8b": {"input": 0.06, "output": 0.06, "cache_read": 0.015, "source": "openrouter"},
}


def _normalize_model_name(name: str) -> str:
    """Normalize a model name to match our pricing keys."""
    if not name:
        return ""
    n = name.lower().strip()
    # Strip common prefixes
    for prefix in ("anthropic/", "openai/", "google/", "deepseek/", "minimax/",
                   "xai/", "mistral/", "meta-llama/", "amazon/", "qwen/"):
        if n.startswith(prefix):
            n = n[len(prefix):]
    # Strip version suffixes like -20240229, -20250514
    import re
    n = re.sub(r"-\d{8}$", "", n)
    # Common aliases
    aliases = {
        "claude-3-5-sonnet-20241022": "claude-3-5-sonnet",
        "claude-3-5-sonnet-latest": "claude-3-5-sonnet",
        "claude-3-5-haiku-20241022": "claude-3-5-haiku",
        "claude-3-opus-20240229": "claude-3-opus",
        "claude-3-sonnet-20240229": "claude-3-sonnet",
        "claude-3-haiku-20240307": "claude-3-haiku",
        "claude-sonnet-4-20250514": "claude-sonnet-4-20250514",
        "claude-opus-4-20250514": "claude-opus-4-20250514",
        "gemini-1.5-pro-002": "gemini-1.5-pro",
        "gemini-1.5-flash-002": "gemini-1.5-flash",
        "gemini-2.0-flash-001": "gemini-2.0-flash",
        "gpt-4o-2024-08-06": "gpt-4o",
        "gpt-4o-mini-2024-07-18": "gpt-4o-mini",
        "deepseek-chat-v3": "deepseek-chat",
        "deepseek-v3": "deepseek-chat",
        "minimax-m2.7": "minimax-m2.7",
        "minimax-m2.6": "minimax-m2.6",
        "minimax-m3": "minimax-m3",
    }
    return aliases.get(n, n)


def get_pricing(model_name: str) -> dict | None:
    """Get pricing for a model. Returns dict with per-1M-token rates or None."""
    normalized = _normalize_model_name(model_name)
    # Direct match
    if normalized in DEFAULT_PRICING:
        return DEFAULT_PRICING[normalized]
    # Fuzzy: find a key that is a substring of the model name or vice versa
    for key, pricing in DEFAULT_PRICING.items():
        if key in normalized or normalized in key:
            return pricing
    return None


def calculate_session_cost(model: str, input_tokens: int = 0, output_tokens: int = 0,
                           cache_read: int = 0, cache_write: int = 0,
                           reasoning: int = 0) -> dict:
    """Calculate the cost of a session given token counts.

    Returns {input_cost, output_cost, cache_read_cost, cache_write_cost,
             reasoning_cost, total_cost, model, pricing_found}.
    """
    pricing = get_pricing(model)
    if not pricing:
        return {
            "input_cost": 0, "output_cost": 0, "cache_read_cost": 0,
            "cache_write_cost": 0, "reasoning_cost": 0, "total_cost": 0,
            "model": model, "pricing_found": False,
        }

    def _cost(tokens, rate):
        return (tokens or 0) / 1_000_000 * rate if tokens and rate else 0

    input_cost = _cost(input_tokens, pricing.get("input"))
    output_cost = _cost(output_tokens, pricing.get("output"))
    cache_read_cost = _cost(cache_read, pricing.get("cache_read", pricing.get("input", 0) * 0.1))
    cache_write_cost = _cost(cache_write, pricing.get("cache_write", pricing.get("input", 0) * 1.25))
    reasoning_cost = _cost(reasoning, pricing.get("output", 0))  # reasoning usually billed as output
    total = input_cost + output_cost + cache_read_cost + cache_write_cost + reasoning_cost

    return {
        "input_cost": round(input_cost, 6),
        "output_cost": round(output_cost, 6),
        "cache_read_cost": round(cache_read_cost, 6),
        "cache_write_cost": round(cache_write_cost, 6),
        "reasoning_cost": round(reasoning_cost, 6),
        "total_cost": round(total, 6),
        "model": model,
        "pricing_found": True,
    }


def enrich_all_costs() -> dict:
    """Compute and store costs for every session that has token data."""
    conn = get_conn()
    # Ensure token + cost columns exist
    cols = {c[1] for c in conn.execute("PRAGMA table_info(sessions)")}
    for col, dtype in [("input_tokens", "INTEGER"), ("output_tokens", "INTEGER"),
                       ("cache_read_tokens", "INTEGER"), ("cache_write_tokens", "INTEGER"),
                       ("reasoning_tokens", "INTEGER"), ("computed_cost_usd", "REAL"),
                       ("api_calls", "INTEGER"), ("pricing_found", "INTEGER")]:
        if col not in cols:
            conn.execute(f"ALTER TABLE sessions ADD COLUMN {col} {dtype}")
    conn.commit()

    rows = conn.execute(
        "SELECT id, tool, model, input_tokens, output_tokens, cache_read_tokens, "
        "cache_write_tokens, reasoning_tokens, api_call_count FROM sessions "
        "WHERE model IS NOT NULL AND model != ''"
    ).fetchall()

    total_cost = 0.0
    total_api_calls = 0
    updated = 0
    by_provider = {}

    for row in rows:
        cost = calculate_session_cost(
            model=row["model"] or "",
            input_tokens=row["input_tokens"] or 0,
            output_tokens=row["output_tokens"] or 0,
            cache_read=row["cache_read_tokens"] or 0,
            cache_write=row["cache_write_tokens"] or 0,
            reasoning=row["reasoning_tokens"] or 0,
        )
        api_calls = row["api_call_count"] or 0
        conn.execute(
            "UPDATE sessions SET computed_cost_usd=?, api_calls=?, pricing_found=? WHERE id=?",
            (cost["total_cost"], api_calls, int(cost["pricing_found"]), row["id"]))
        total_cost += cost["total_cost"]
        total_api_calls += api_calls
        updated += 1
        if cost["pricing_found"]:
            provider = get_pricing(row["model"] or "").get("source", "unknown")
            by_provider[provider] = by_provider.get(provider, 0) + cost["total_cost"]

    conn.commit()
    conn.close()
    return {
        "sessions_updated": updated,
        "total_cost_usd": round(total_cost, 4),
        "total_api_calls": total_api_calls,
        "by_provider": {k: round(v, 4) for k, v in sorted(by_provider.items(), key=lambda x: -x[1])},
    }


def get_cost_summary() -> dict:
    """Get aggregate cost stats for the dashboard."""
    conn = get_conn()
    total_cost = conn.execute(
        "SELECT COALESCE(SUM(computed_cost_usd),0) FROM sessions").fetchone()[0]
    total_api = conn.execute(
        "SELECT COALESCE(SUM(api_calls),0) FROM sessions").fetchone()[0]
    total_sessions = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    priced_sessions = conn.execute(
        "SELECT COUNT(*) FROM sessions WHERE pricing_found=1").fetchone()[0]

    by_tool = conn.execute(
        "SELECT tool, COALESCE(SUM(computed_cost_usd),0) cost, COALESCE(SUM(api_calls),0) calls "
        "FROM sessions GROUP BY tool ORDER BY cost DESC LIMIT 10").fetchall()

    by_model = conn.execute(
        "SELECT model, COALESCE(SUM(computed_cost_usd),0) cost, COALESCE(SUM(api_calls),0) calls, "
        "COUNT(*) sessions FROM sessions WHERE model IS NOT NULL AND model != '' "
        "GROUP BY model ORDER BY cost DESC LIMIT 15").fetchall()

    conn.close()
    return {
        "total_cost_usd": round(total_cost, 4),
        "total_api_calls": total_api,
        "total_sessions": total_sessions,
        "priced_sessions": priced_sessions,
        "by_tool": [{"tool": r["tool"], "cost": round(r["cost"], 4), "api_calls": r["calls"]} for r in by_tool],
        "by_model": [{"model": r["model"], "cost": round(r["cost"], 4),
                      "api_calls": r["calls"], "sessions": r["sessions"]} for r in by_model],
    }
