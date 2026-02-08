#!/usr/bin/env python3
"""Fetch and parse RSS feeds, output JSON articles."""

import json
import sys
import time
import socket
from datetime import datetime, timezone, timedelta
from pathlib import Path

import feedparser
import yaml

HOURS_CUTOFF = 48
TIMEOUT = 10

def load_feeds():
    config_path = Path(__file__).parent.parent / "config" / "rss-feeds.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)["feeds"]

def load_authority():
    config_path = Path(__file__).parent.parent / "config" / "revue-presse.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f).get("source_authority", {})

def parse_date(entry):
    """Extract publication date from feed entry."""
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except Exception:
                continue
    return None

def clean_summary(entry):
    """Extract a plain text summary."""
    summary = entry.get("summary", "") or ""
    # Strip HTML tags roughly
    import re
    summary = re.sub(r"<[^>]+>", " ", summary)
    summary = re.sub(r"\s+", " ", summary).strip()
    # Limit length
    if len(summary) > 500:
        summary = summary[:497] + "..."
    return summary

def parse_hn_entry(entry):
    """Extract the real article URL and clean summary from a Hacker News entry.
    HN RSS summaries contain 'Article URL: ... Comments URL: ... Points: N # Comments: N'.
    Returns (article_url, clean_summary).
    """
    import re
    summary = entry.get("summary", "") or ""
    summary = re.sub(r"<[^>]+>", " ", summary)
    summary = re.sub(r"\s+", " ", summary).strip()

    article_url = None
    m = re.search(r"Article URL:\s*(https?://\S+)", summary)
    if m:
        article_url = m.group(1)

    # Remove the metadata lines, keep only real content if any
    cleaned = re.sub(r"Article URL:\s*\S+", "", summary)
    cleaned = re.sub(r"Comments URL:\s*\S+", "", cleaned)
    cleaned = re.sub(r"Points:\s*\d+", "", cleaned)
    cleaned = re.sub(r"#\s*Comments:\s*\d+", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return article_url, cleaned

def fetch_feed(feed_config, cutoff, authority):
    """Parse a single RSS feed and return articles."""
    articles = []
    name = feed_config["name"]
    url = feed_config["url"]
    topics = feed_config.get("topics", [])

    old_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(TIMEOUT)
    try:
        d = feedparser.parse(url)
    except Exception as e:
        print(f"[WARN] Failed to fetch {name}: {e}", file=sys.stderr)
        return articles
    finally:
        socket.setdefaulttimeout(old_timeout)

    if d.bozo and not d.entries:
        print(f"[WARN] Feed error for {name}: {d.bozo_exception}", file=sys.stderr)
        return articles

    is_hn = "hacker news" in name.lower() or "hnrss" in url.lower()

    for entry in d.entries:
        pub_date = parse_date(entry)
        if pub_date and pub_date < cutoff:
            continue

        link = entry.get("link", "")
        title = entry.get("title", "").strip()
        if not title or not link:
            continue

        if is_hn:
            article_url, summary = parse_hn_entry(entry)
            # Prefer the actual article URL over the HN comments link
            if article_url:
                link = article_url
        else:
            summary = clean_summary(entry)

        articles.append({
            "title": title,
            "url": link,
            "source": name,
            "topics": topics,
            "summary": summary,
            "published": pub_date.isoformat() if pub_date else None,
            "authority": authority.get(name, authority.get("default", 10)),
        })

    return articles

def main():
    feeds = load_feeds()
    authority = load_authority()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=HOURS_CUTOFF)

    all_articles = []
    for feed in feeds:
        articles = fetch_feed(feed, cutoff, authority)
        all_articles.extend(articles)
        print(f"[INFO] {feed['name']}: {len(articles)} articles", file=sys.stderr)

    print(f"[INFO] Total: {len(all_articles)} articles from RSS", file=sys.stderr)

    # Output JSON to stdout
    json.dump(all_articles, sys.stdout, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
