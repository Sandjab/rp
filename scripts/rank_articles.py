#!/usr/bin/env python3
"""Score and rank articles, output top N as JSON."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import os

import yaml

BREAKING_KEYWORDS = [
    "breaking", "urgent", "just in", "exclusive", "major",
    "announces", "launches", "acquires", "shuts down", "breach",
    "zero-day", "critical vulnerability", "recall",
]

def load_config():
    config_path = Path(__file__).parent.parent / "config" / "revue-presse.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)

def recency_score(published_str):
    """Score 0-30 based on article age."""
    if not published_str:
        return 10  # Unknown date gets medium score
    try:
        pub = datetime.fromisoformat(published_str)
        if pub.tzinfo is None:
            pub = pub.replace(tzinfo=timezone.utc)
        age_hours = (datetime.now(timezone.utc) - pub).total_seconds() / 3600
    except Exception:
        return 10

    if age_hours < 3:
        return 30
    elif age_hours < 6:
        return 25
    elif age_hours < 12:
        return 20
    elif age_hours < 24:
        return 15
    elif age_hours < 48:
        return 8
    return 3

def authority_score(article):
    """Score 0-25 from source authority."""
    return min(article.get("authority", 10), 25)

def topic_relevance_score(article, topics_config):
    """Score 0-20 based on keyword density in title + summary."""
    text = f"{article.get('title', '')} {article.get('summary', '')}".lower()
    max_score = 0
    for topic in topics_config:
        matches = sum(1 for kw in topic["keywords"] if kw.lower() in text)
        density = min(matches / max(len(topic["keywords"]), 1), 1.0)
        score = int(density * 20)
        if score > max_score:
            max_score = score
            # Tag the article with matching topics
            if "matched_topics" not in article:
                article["matched_topics"] = []
            if topic["tag"] not in article["matched_topics"] and matches > 0:
                article["matched_topics"].append(topic["tag"])
    return max_score

def depth_score(article):
    """Score 0-15 bonus for research-enriched articles."""
    if article.get("research_context"):
        return 15
    if article.get("summary") and len(article["summary"]) > 200:
        return 5
    return 0

def breaking_score(article):
    """Score 0-10 heuristic for breaking news."""
    text = f"{article.get('title', '')}".lower()
    hits = sum(1 for kw in BREAKING_KEYWORDS if kw in text)
    score = min(hits * 5, 10)
    if score >= 5:
        article["is_breaking"] = True
    return score

def assign_topics(article, topics_config):
    """Ensure article has topic tags from config matching."""
    if article.get("matched_topics"):
        return
    text = f"{article.get('title', '')} {article.get('summary', '')}".lower()
    article["matched_topics"] = []
    for topic in topics_config:
        if any(kw.lower() in text for kw in topic["keywords"]):
            article["matched_topics"].append(topic["tag"])
    # Fallback: use original topics from RSS feed
    if not article["matched_topics"] and article.get("topics"):
        article["matched_topics"] = article["topics"][:2]

def rank(articles, config):
    """Score all articles and return top N sorted by score.

    Scoring: recency(0-30) + authority(0-25) + depth(0-15) + breaking(0-10) = max 80.
    topic_relevance_score is NOT included — topic matching is too naive
    (keyword-based) and lets irrelevant articles rank high. The LLM
    editorial phase handles intelligent selection instead.
    """
    topics_config = config.get("topics", [])
    max_candidates = int(os.environ.get(
        "RP_MAX_CANDIDATES",
        config.get("edition", {}).get("max_articles", 15),
    ))

    for article in articles:
        s1 = recency_score(article.get("published"))
        s2 = authority_score(article)
        s4 = depth_score(article)
        s5 = breaking_score(article)
        article["score"] = s1 + s2 + s4 + s5
        assign_topics(article, topics_config)

    articles.sort(key=lambda a: a["score"], reverse=True)
    return articles[:max_candidates]

def main():
    config = load_config()
    articles = json.load(sys.stdin)
    ranked = rank(articles, config)
    print(f"[INFO] Ranked: top {len(ranked)} articles selected", file=sys.stderr)
    json.dump(ranked, sys.stdout, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
