#!/usr/bin/env python3
"""Orchestrate RSS collection, optional WebSearch merge, dedup, and ranking.

Usage:
    python3 scripts/collect.py

Reads WebSearch results from .pipeline/00_websearch.json if present.
Produces .pipeline/01_candidates.json with top N candidates (default 20).
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

SCRIPTS_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPTS_DIR.parent
PIPELINE_DIR = PROJECT_DIR / ".pipeline"
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
        print(f"[WARN] AI filter too aggressive ({len(kept)}/{len(articles)}), disabled", file=sys.stderr)
        return articles

    print(f"[COLLECT] AI filter: {len(articles)} -> {len(kept)} articles", file=sys.stderr)
    return kept


def run_script(script_name, input_data=None, env_extra=None):
    """Run a sibling script, passing JSON via stdin, returning parsed JSON."""
    script_path = SCRIPTS_DIR / script_name
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    result = subprocess.run(
        [sys.executable, str(script_path)],
        input=input_data,
        capture_output=True,
        text=True,
        env=env,
    )
    # Forward stderr (log lines) to our stderr
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode != 0:
        print(f"[ERROR] {script_name} exited with code {result.returncode}", file=sys.stderr)
        sys.exit(1)
    return json.loads(result.stdout)


def main():
    # Ensure pipeline directory exists
    PIPELINE_DIR.mkdir(exist_ok=True)

    # 1. Collect RSS
    print("[COLLECT] Phase 1: RSS feeds...", file=sys.stderr)
    rss_articles = run_script("parse_rss.py")

    # 2. Merge with WebSearch JSON if present
    all_articles = list(rss_articles)
    if WEBSEARCH_PATH.exists():
        try:
            with open(WEBSEARCH_PATH) as f:
                ws_articles = json.load(f)
            if ws_articles:
                all_articles.extend(ws_articles)
                print(f"[COLLECT] +{len(ws_articles)} WebSearch articles", file=sys.stderr)
        except (json.JSONDecodeError, Exception) as e:
            print(f"[WARN] Could not read WebSearch file: {e}", file=sys.stderr)
    else:
        print("[COLLECT] No WebSearch file found, continuing with RSS only", file=sys.stderr)

    print(f"[COLLECT] Total before dedup: {len(all_articles)}", file=sys.stderr)

    # 3. Deduplicate
    print("[COLLECT] Phase 2: Deduplication...", file=sys.stderr)
    merged_json = json.dumps(all_articles, ensure_ascii=False)
    deduped = run_script("deduplicate.py", input_data=merged_json)

    # 3b. AI relevance filter
    deduped = filter_ai_relevant(deduped)

    # 4. Rank — propagate RP_MAX_CANDIDATES (default 20 for pipeline)
    print("[COLLECT] Phase 3: Ranking...", file=sys.stderr)
    max_candidates = os.environ.get("RP_MAX_CANDIDATES", "20")
    deduped_json = json.dumps(deduped, ensure_ascii=False)
    ranked = run_script(
        "rank_articles.py",
        input_data=deduped_json,
        env_extra={"RP_MAX_CANDIDATES": max_candidates},
    )

    # 5. Write output
    with open(OUTPUT_PATH, "w") as f:
        json.dump(ranked, f, ensure_ascii=False, indent=2)

    print(f"[COLLECT] Done: {len(ranked)} articles -> {OUTPUT_PATH}", file=sys.stderr)
    # Output path on stdout for pipeline chaining
    print(str(OUTPUT_PATH))


if __name__ == "__main__":
    main()
