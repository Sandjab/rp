#!/usr/bin/env python3
"""Deduplicate articles by URL and title similarity."""

import json
import sys
from difflib import SequenceMatcher
from urllib.parse import urlparse

# Thresholds
SAME_DOMAIN_THRESHOLD = 0.75
CROSS_DOMAIN_THRESHOLD = 0.85

def normalize_url(url):
    """Normalize URL for comparison."""
    parsed = urlparse(url)
    # Remove www prefix, trailing slashes, query params
    host = parsed.netloc.lower().replace("www.", "")
    path = parsed.path.rstrip("/")
    return f"{host}{path}"

def title_similarity(a, b):
    """Compute title similarity ratio."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def same_domain(url_a, url_b):
    """Check if two URLs share the same domain."""
    domain_a = urlparse(url_a).netloc.lower().replace("www.", "")
    domain_b = urlparse(url_b).netloc.lower().replace("www.", "")
    return domain_a == domain_b

def deduplicate(articles):
    """Remove duplicate articles, keeping highest-authority version."""
    if not articles:
        return []

    # Sort by authority descending so we keep the best source
    articles.sort(key=lambda a: a.get("authority", 0), reverse=True)

    seen_urls = {}
    result = []

    for article in articles:
        norm_url = normalize_url(article["url"])

        # Exact URL match
        if norm_url in seen_urls:
            continue

        # Title similarity check
        is_dup = False
        for kept in result:
            threshold = SAME_DOMAIN_THRESHOLD if same_domain(article["url"], kept["url"]) else CROSS_DOMAIN_THRESHOLD
            if title_similarity(article["title"], kept["title"]) >= threshold:
                is_dup = True
                break

        if not is_dup:
            seen_urls[norm_url] = True
            result.append(article)

    return result

def main():
    data = json.load(sys.stdin)
    deduped = deduplicate(data)
    print(f"[INFO] Deduplication: {len(data)} -> {len(deduped)} articles", file=sys.stderr)
    json.dump(deduped, sys.stdout, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
