#!/usr/bin/env python3
"""Orchestrate RSS collection, optional WebSearch merge, dedup, and ranking.

Usage:
    python3 scripts/collect.py

Reads WebSearch results from .pipeline/00_websearch.json if present.
Produces .pipeline/01_candidates.json with top N candidates (default 25).
"""

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlparse

import yaml

from log_utils import setup_logging, PROJECT_DIR, PIPELINE_DIR

logger = setup_logging("collect")

SCRIPTS_DIR = Path(__file__).parent
WEBSEARCH_PATH = PIPELINE_DIR / "00_websearch.json"
OUTPUT_PATH = PIPELINE_DIR / "01_candidates.json"

AI_WORD_BOUNDARY = re.compile(r'\bAI\b')


def load_ai_keywords():
    """Charge tous les keywords IA depuis revue-presse.yaml."""
    config_path = PROJECT_DIR / "config" / "revue-presse.yaml"
    with open(config_path) as f:
        config = yaml.safe_load(f)
    keywords = set()
    for topic in config.get("topics", []):
        for kw in topic.get("keywords", []):
            keywords.add(kw.lower())
    # Termes generiques de filet de securite
    keywords.update(["artificial intelligence", "machine learning", "ml", "a.i."])
    return keywords


def filter_ai_relevant(articles):
    """Filtre binaire : garde les articles mentionnant au moins un terme IA."""
    keywords = load_ai_keywords()
    # Separer les keywords courts (need word boundary) des longs
    short_kw = {kw for kw in keywords if len(kw) <= 2}
    long_kw = keywords - short_kw

    kept = []
    for article in articles:
        # Toujours garder les articles WebSearch enrichis
        if article.get("research_context"):
            kept.append(article)
            continue
        text = f"{article.get('title', '')} {article.get('summary', '')}".lower()
        # Test keywords longs (substring match suffit)
        if any(kw in text for kw in long_kw):
            kept.append(article)
            continue
        # Test keywords courts (word boundary sur texte original)
        raw_text = f"{article.get('title', '')} {article.get('summary', '')}"
        if AI_WORD_BOUNDARY.search(raw_text):
            kept.append(article)
            continue

    # Garde-fou : si filtre trop agressif, desactiver
    if len(articles) > 0 and len(kept) / len(articles) < 0.2:
        logger.warning(f"[WARN] AI filter too aggressive ({len(kept)}/{len(articles)}), disabled")
        return articles

    logger.info(f"[COLLECT] AI filter: {len(articles)} -> {len(kept)} articles")
    return kept


def normalize_url(url):
    """Normalize URL for comparison (same logic as deduplicate.py)."""
    parsed = urlparse(url)
    host = parsed.netloc.lower().replace("www.", "")
    path = parsed.path.rstrip("/")
    return f"{host}{path}"


def filter_already_published(articles):
    """Remove articles already published in recent editions (cross-edition dedup).

    Reads manifest.json for URLs/titles from the last N days (configurable via
    history_days in config). Excludes today's date to allow intra-day re-runs.
    Graceful degradation: returns articles unchanged if manifest is missing/unreadable.
    """
    config_path = PROJECT_DIR / "config" / "revue-presse.yaml"
    with open(config_path) as f:
        config = yaml.safe_load(f)
    history_days = config.get("edition", {}).get("history_days", 3)

    manifest_path = PROJECT_DIR / "editions" / "archives" / "manifest.json"
    if not manifest_path.exists():
        logger.info(f"[COLLECT] No manifest found, skipping history dedup")
        return articles

    try:
        with open(manifest_path) as f:
            manifest = json.load(f)
    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"[WARN] Could not read manifest: {e}")
        return articles

    today_str = os.environ.get("RP_EDITION_DATE") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cutoff = (datetime.now(timezone.utc) - timedelta(days=history_days)).strftime("%Y-%m-%d")

    # Collect published URLs and titles from recent editions (excluding today)
    published_urls = set()
    published_titles = []
    for entry in manifest:
        entry_date = entry.get("date", "")
        if entry_date == today_str:
            continue  # Exclude today to allow re-runs
        if entry_date < cutoff:
            continue  # Too old
        for url in entry.get("urls", []):
            published_urls.add(normalize_url(url))
        published_titles.extend(entry.get("titles", []))

    if not published_urls and not published_titles:
        return articles

    kept = []
    for article in articles:
        url = article.get("url", "")
        title = article.get("title", "")

        # Check exact URL match
        if url and normalize_url(url) in published_urls:
            continue

        # Check title similarity (cross-domain: same news, different source)
        if title and any(
            SequenceMatcher(None, title.lower(), pt.lower()).ratio() >= 0.85
            for pt in published_titles
        ):
            continue

        kept.append(article)

    removed = len(articles) - len(kept)
    logger.info(f"[COLLECT] History dedup ({history_days}d): {len(articles)} -> {len(kept)} articles ({removed} removed)")
    return kept


def run_script(script_name, input_data=None, env_extra=None):
    """Run a sibling script, passing JSON via stdin, returning parsed JSON."""
    script_path = SCRIPTS_DIR / script_name
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    logger.debug(f"Running: {sys.executable} {script_path}")
    t0 = time.time()
    result = subprocess.run(
        [sys.executable, str(script_path)],
        input=input_data,
        capture_output=True,
        text=True,
        env=env,
    )
    elapsed = time.time() - t0
    logger.debug(f"{script_name} finished in {elapsed:.1f}s (rc={result.returncode}, stdout={len(result.stdout)}B, stderr={len(result.stderr)}B)")
    # Forward stderr (log lines) to our stderr
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode != 0:
        logger.error(f"[ERROR] {script_name} exited with code {result.returncode}")
        sys.exit(1)
    return json.loads(result.stdout)


def main():
    # Ensure pipeline directory exists
    PIPELINE_DIR.mkdir(exist_ok=True)

    # 1. Collect RSS
    logger.info("[COLLECT] Phase 1: RSS feeds...")
    rss_articles = run_script("parse_rss.py")

    # 2. Merge with WebSearch JSON if present
    all_articles = list(rss_articles)
    if WEBSEARCH_PATH.exists():
        try:
            with open(WEBSEARCH_PATH) as f:
                ws_articles = json.load(f)
            if ws_articles:
                all_articles.extend(ws_articles)
                logger.info(f"[COLLECT] +{len(ws_articles)} WebSearch articles")
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"[WARN] Could not read WebSearch file: {e}")
    else:
        logger.info("[COLLECT] No WebSearch file found, continuing with RSS only")

    logger.info(f"[COLLECT] Total before dedup: {len(all_articles)}")

    # 3. Deduplicate
    logger.info("[COLLECT] Phase 2: Deduplication...")
    merged_json = json.dumps(all_articles, ensure_ascii=False)
    deduped = run_script("deduplicate.py", input_data=merged_json)

    # 3b. AI relevance filter
    deduped = filter_ai_relevant(deduped)

    # 3c. Cross-edition dedup (filter articles published in recent editions)
    deduped = filter_already_published(deduped)

    # 4. Rank — propagate RP_MAX_CANDIDATES (default 20 for pipeline)
    logger.info("[COLLECT] Phase 3: Ranking...")
    max_candidates = os.environ.get("RP_MAX_CANDIDATES", "25")
    deduped_json = json.dumps(deduped, ensure_ascii=False)
    ranked = run_script(
        "rank_articles.py",
        input_data=deduped_json,
        env_extra={"RP_MAX_CANDIDATES": max_candidates},
    )

    # 5. Write output
    with open(OUTPUT_PATH, "w") as f:
        json.dump(ranked, f, ensure_ascii=False, indent=2)

    logger.info(f"[COLLECT] Done: {len(ranked)} articles -> {OUTPUT_PATH}")
    # Output path on stdout for pipeline chaining
    print(str(OUTPUT_PATH))


if __name__ == "__main__":
    main()
