"""Pricing scraper — uses Playwright to scrape current LLM pricing from public model catalogs.

Updates the local pricing table so costs reflect current market rates.
"""

import json
import os
import sqlite3
from datetime import datetime, timezone

from core.sync import get_conn

# Public pricing pages (free, no login required)
PRICING_SOURCES = {
    "openai": "https://openai.com/api/pricing/",
    "anthropic": "https://www.anthropic.com/pricing",
    "google": "https://ai.google.dev/gemini-api/docs/pricing",
    "deepseek": "https://api-docs.deepseek.com/quick_start/pricing",
    "minimax": "https://www.minimax.io/document/price",
    "xai": "https://x.ai/pricing",
}


def _init_pricing_table():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pricing_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model TEXT NOT NULL,
            provider TEXT,
            input_per_million REAL,
            output_per_million REAL,
            cache_read_per_million REAL,
            cache_write_per_million REAL,
            scraped_at TEXT NOT NULL DEFAULT (datetime('now')),
            source_url TEXT,
            raw_text TEXT,
            UNIQUE(model, source_url)
        )
    """)
    conn.commit()
    conn.close()


def scrape_all(headless: bool = True) -> dict:
    """Scrape pricing from all public sources using Playwright.

    Returns {source: {models_scraped, status, error?}}.
    """
    _init_pricing_table()
    from playwright.sync_api import sync_playwright

    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        for name, url in PRICING_SOURCES.items():
            try:
                ctx = browser.new_context(user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                                                      "Chrome/130.0.0.0 Safari/537.36"))
                page = ctx.new_page()
                page.goto(url, timeout=30000, wait_until="domcontentloaded")
                page.wait_for_timeout(2000)
                text = page.inner_text("body")
                models = _parse_pricing_page(name, text, url)
                ctx.close()
                results[name] = {"models_scraped": len(models), "status": "ok", "url": url}
            except Exception as e:
                results[name] = {"models_scraped": 0, "status": "error", "error": str(e)[:200]}
        browser.close()
    return results


def _parse_pricing_page(source: str, text: str, url: str) -> list:
    """Parse a pricing page's text into model pricing dicts.

    This is a best-effort parser — each site has a different format.
    Returns list of {model, provider, input_per_million, output_per_million, ...}.
    """
    conn = get_conn()
    scraped = []

    if source == "openai":
        scraped = _parse_openai_pricing(text, url, conn)
    elif source == "anthropic":
        scraped = _parse_anthropic_pricing(text, url, conn)
    elif source == "google":
        scraped = _parse_google_pricing(text, url, conn)
    elif source == "deepseek":
        scraped = _parse_deepseek_pricing(text, url, conn)
    else:
        # Generic: just store raw text for manual review
        conn.execute(
            "INSERT OR REPLACE INTO pricing_cache (model, provider, source_url, scraped_at, raw_text) "
            "VALUES (?,?,?,?,?)",
            (f"{source}_raw", source, url, datetime.now(timezone.utc).isoformat(), text[:5000]))
        scraped = [{"model": f"{source}_raw", "source": source}]

    conn.commit()
    conn.close()
    return scraped


def _parse_openai_pricing(text: str, url: str, conn) -> list:
    """Parse OpenAI pricing page."""
    import re
    models = []
    # Pattern: "Model name $X.XX / 1M tokens $Y.YY / 1M tokens"
    lines = text.split("\n")
    for i, line in enumerate(lines):
        line_lower = line.lower()
        # Look for model names followed by pricing
        for model_key in ["gpt-4o", "gpt-4o mini", "gpt-4 turbo", "gpt-4", "gpt-3.5 turbo",
                          "o1", "o1-mini", "o3", "o3-mini", "o4-mini"]:
            if model_key in line_lower:
                # Search nearby lines for pricing numbers
                context = " ".join(lines[max(0, i-2):i+5])
                prices = re.findall(r'\$([0-9]+\.?[0-9]*)\s*/?\s*1M', context, re.IGNORECASE)
                if len(prices) >= 2:
                    conn.execute(
                        "INSERT OR REPLACE INTO pricing_cache "
                        "(model, provider, input_per_million, output_per_million, "
                        "source_url, scraped_at, raw_text) VALUES (?,?,?,?,?,?,?)",
                        (model_key, "openai", float(prices[0]), float(prices[1]),
                         url, datetime.now(timezone.utc).isoformat(), line[:500]))
                    models.append({"model": model_key, "provider": "openai"})
    return models


def _parse_anthropic_pricing(text: str, url: str, conn) -> list:
    """Parse Anthropic pricing page."""
    import re
    models = []
    lines = text.split("\n")
    for i, line in enumerate(lines):
        line_lower = line.lower()
        for model_key in ["claude opus 4", "claude sonnet 4", "claude haiku 4",
                          "claude 3.5 sonnet", "claude 3.5 haiku", "claude 3 opus",
                          "claude 3 sonnet", "claude 3 haiku"]:
            if model_key in line_lower:
                context = " ".join(lines[max(0, i-2):i+5])
                prices = re.findall(r'\$([0-9]+\.?[0-9]*)\s*/?\s*1M', context, re.IGNORECASE)
                if len(prices) >= 2:
                    conn.execute(
                        "INSERT OR REPLACE INTO pricing_cache "
                        "(model, provider, input_per_million, output_per_million, "
                        "source_url, scraped_at, raw_text) VALUES (?,?,?,?,?,?,?)",
                        (model_key, "anthropic", float(prices[0]), float(prices[1]),
                         url, datetime.now(timezone.utc).isoformat(), line[:500]))
                    models.append({"model": model_key, "provider": "anthropic"})
    return models


def _parse_google_pricing(text: str, url: str, conn) -> list:
    """Parse Google pricing page."""
    import re
    models = []
    lines = text.split("\n")
    for i, line in enumerate(lines):
        line_lower = line.lower()
        for model_key in ["gemini 2.5 pro", "gemini 2.5 flash", "gemini 2.0 flash",
                          "gemini 1.5 pro", "gemini 1.5 flash"]:
            if model_key in line_lower:
                context = " ".join(lines[max(0, i-2):i+5])
                prices = re.findall(r'\$([0-9]+\.?[0-9]*)\s*/?\s*1M', context, re.IGNORECASE)
                if len(prices) >= 2:
                    conn.execute(
                        "INSERT OR REPLACE INTO pricing_cache "
                        "(model, provider, input_per_million, output_per_million, "
                        "source_url, scraped_at, raw_text) VALUES (?,?,?,?,?,?,?)",
                        (model_key, "google", float(prices[0]), float(prices[1]),
                         url, datetime.now(timezone.utc).isoformat(), line[:500]))
                    models.append({"model": model_key, "provider": "google"})
    return models


def _parse_deepseek_pricing(text: str, url: str, conn) -> list:
    """Parse DeepSeek pricing page."""
    import re
    models = []
    lines = text.split("\n")
    for i, line in enumerate(lines):
        line_lower = line.lower()
        for model_key in ["deepseek-chat", "deepseek-reasoner"]:
            if model_key in line_lower:
                context = " ".join(lines[max(0, i-2):i+5])
                prices = re.findall(r'¥([0-9]+\.?[0-9]*)', context)
                # DeepSeek prices in RMB — approximate conversion ~7.25
                if len(prices) >= 2:
                    rate = 7.25
                    conn.execute(
                        "INSERT OR REPLACE INTO pricing_cache "
                        "(model, provider, input_per_million, output_per_million, "
                        "source_url, scraped_at, raw_text) VALUES (?,?,?,?,?,?,?)",
                        (model_key, "deepseek", round(float(prices[0]) / rate, 4),
                         round(float(prices[1]) / rate, 4),
                         url, datetime.now(timezone.utc).isoformat(), line[:500]))
                    models.append({"model": model_key, "provider": "deepseek"})
    return models


def get_latest_pricing() -> list:
    """Return all scraped pricing records."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM pricing_cache ORDER BY provider, model").fetchall()
    conn.close()
    return [dict(r) for r in rows]
