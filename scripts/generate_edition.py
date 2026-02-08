#!/usr/bin/env python3
"""Generate HTML edition from template and article data."""

import json
import sys
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

def load_config():
    config_path = Path(__file__).parent.parent / "config" / "revue-presse.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)

def load_template():
    tpl_path = Path(__file__).parent.parent / "templates" / "edition.html"
    with open(tpl_path) as f:
        return f.read()

def get_edition_number(archives_dir):
    """Count existing editions + 1."""
    if not archives_dir.exists():
        return 1
    existing = list(archives_dir.glob("*.html"))
    existing = [f for f in existing if f.name != "index.html"]
    return len(existing) + 1

def time_ago(published_str, now):
    """Human-readable relative time in French."""
    if not published_str:
        return ""
    try:
        pub = datetime.fromisoformat(published_str)
        if pub.tzinfo is None:
            pub = pub.replace(tzinfo=ZoneInfo("UTC"))
        diff = now - pub
        hours = diff.total_seconds() / 3600
        if hours < 1:
            mins = int(diff.total_seconds() / 60)
            return f"il y a {mins} min"
        elif hours < 24:
            return f"il y a {int(hours)}h"
        else:
            days = int(hours / 24)
            return f"il y a {days}j"
    except Exception:
        return ""

def build_card_html(article, index, config, now):
    """Build a single card HTML block."""
    topics_config = {t["tag"]: t for t in config.get("topics", [])}
    tags_html = ""
    for tag in article.get("matched_topics", article.get("topics", []))[:3]:
        tc = topics_config.get(tag, {})
        color = tc.get("color", "#666")
        tags_html += f'<span class="tag-pill" style="background:{color}20;color:{color};opacity:0.85">{tag}</span>'

    title = article.get("editorial_title", article.get("title", ""))
    source = article.get("source", "")
    ago = time_ago(article.get("published"), now)
    source_line = f"{source}"
    if ago:
        source_line += f" — {ago}"

    summary = article.get("editorial_summary", article.get("summary", ""))
    context = article.get("research_context", "")
    url = article.get("url", "#")

    context_html = ""
    if context:
        context_html = f'''
    <button class="context-toggle" onclick="toggleContext(this)">
      <span class="arrow">&#9656;</span> <span class="ctx-label">Contexte approfondi</span>
    </button>
    <div class="card-context">
      <div class="card-context-inner">{context}</div>
    </div>'''

    return f'''
    <article class="card" data-index="{index}">
      <div class="card-tags">{tags_html}</div>
      <h2 class="card-title">{title}</h2>
      <div class="card-source">{source_line}</div>
      <p class="card-summary">{summary}</p>
      {context_html}
      <a class="card-link" href="{url}" target="_blank" rel="noopener">Lire l'article <span>&rarr;</span></a>
    </article>'''

def build_grid_card_html(article, index, config, now):
    """Build a grid card HTML block."""
    topics_config = {t["tag"]: t for t in config.get("topics", [])}
    tags_html = ""
    for tag in article.get("matched_topics", article.get("topics", []))[:3]:
        tc = topics_config.get(tag, {})
        color = tc.get("color", "#666")
        tags_html += f'<span class="tag-pill" style="background:{color}20;color:{color};opacity:0.85">{tag}</span>'

    title = article.get("editorial_title", article.get("title", ""))
    source = article.get("source", "")
    ago = time_ago(article.get("published"), now)
    summary = article.get("editorial_summary", article.get("summary", ""))
    url = article.get("url", "#")

    return f'''
    <article class="grid-card" data-index="{index}">
      <div class="card-tags">{tags_html}</div>
      <h2 class="card-title"><a href="{url}" target="_blank" rel="noopener">{title}</a></h2>
      <div class="card-source">{source} — {ago}</div>
      <p class="card-summary">{summary}</p>
    </article>'''

def build_filter_pills(config):
    """Build filter pill buttons from topics config."""
    pills = ""
    for topic in config.get("topics", []):
        pills += f'<button class="filter-pill" data-filter="{topic["tag"]}">{topic["tag"]}</button>\n  '
    return pills

def build_archive_page(archives_dir, config):
    """Generate archive index page."""
    editions = sorted(archives_dir.glob("????-??-??.??????.html"), reverse=True)
    if not editions:
        # Also try legacy format
        editions = sorted(archives_dir.glob("????-??-??.html"), reverse=True)
    if not editions:
        return

    items_html = ""
    for ed in editions:
        # Filename format: YYYY-MM-DD.hhmmss.html
        name = ed.stem  # YYYY-MM-DD.hhmmss
        parts = name.split(".")
        date_part = parts[0]
        time_part = parts[1] if len(parts) > 1 else ""
        display = date_part
        if time_part and len(time_part) == 6:
            display += f" {time_part[:2]}:{time_part[2:4]}:{time_part[4:6]}"
        items_html += f'''
    <a href="{ed.name}" class="archive-item">
      <span class="archive-date">{display}</span>
    </a>'''

    archive_html = f'''<!DOCTYPE html>
<html lang="fr" data-theme="light">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Archives — {config["edition"]["title"]}</title>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{{margin:0;padding:0;box-sizing:border-box}}
:root{{--bg:#FAFAF8;--card:#FFFFFF;--text:#1A1A1A;--text-2:#6B6B6B;--accent:#E63946;--border:#E5E5E3;
--font-h:'Instrument Serif',serif;--font-b:'Inter',sans-serif;--font-m:'JetBrains Mono',monospace}}
[data-theme="dark"]{{--bg:#0F0F0F;--card:#1A1A1A;--text:#EDEDEB;--text-2:#999;--accent:#FF6B6B;--border:#2A2A2A}}
body{{font-family:var(--font-b);color:var(--text);background:var(--bg);min-height:100vh}}
a{{color:inherit;text-decoration:none}}
.masthead{{padding:clamp(1.5rem,4vw,3rem) clamp(1rem,5vw,4rem);border-bottom:2px solid var(--text);
display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:1rem}}
.masthead h1{{font-family:var(--font-h);font-size:clamp(2rem,5vw,3.5rem);font-weight:400;letter-spacing:-0.02em}}
.masthead a{{font-family:var(--font-m);font-size:0.8rem;color:var(--accent)}}
.archives{{max-width:720px;margin:2rem auto;padding:0 clamp(1rem,5vw,4rem)}}
.archive-item{{display:block;padding:1rem 0;border-bottom:1px solid var(--border);
font-family:var(--font-m);font-size:0.9rem;transition:color .2s}}
.archive-item:hover{{color:var(--accent)}}
</style>
</head>
<body>
<header class="masthead">
  <h1>Archives</h1>
  <a href="../index.html">&larr; Derniere edition</a>
</header>
<main class="archives">
{items_html}
</main>
</body>
</html>'''

    archive_path = archives_dir / "index.html"
    with open(archive_path, "w") as f:
        f.write(archive_html)
    print(f"[INFO] Archive page updated: {archive_path}", file=sys.stderr)

def main():
    config = load_config()
    template = load_template()

    # Read articles from stdin or file argument
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            articles = json.load(f)
    else:
        articles = json.load(sys.stdin)

    tz = ZoneInfo(config["edition"]["timezone"])
    now = datetime.now(tz)
    date_str = now.strftime("%Y-%m-%d")
    timestamp_str = now.strftime("%Y-%m-%d.%H%M%S")
    date_display = now.strftime("%A %d %B %Y").capitalize()

    editions_dir = Path(__file__).parent.parent / "editions"
    editions_dir.mkdir(exist_ok=True)
    archives_dir = editions_dir / "archives"
    archives_dir.mkdir(exist_ok=True)
    edition_number = get_edition_number(archives_dir)

    # Build HTML blocks
    cards_html = ""
    grid_cards_html = ""
    for i, article in enumerate(articles):
        cards_html += build_card_html(article, i, config, now)
        grid_cards_html += build_grid_card_html(article, i, config, now)

    filter_pills = build_filter_pills(config)

    # Footer nav
    footer_nav = f'<a href="editions/archives/index.html">Archives</a>'

    # Replace placeholders
    html = template
    html = html.replace("{{EDITION_TITLE}}", config["edition"]["title"])
    html = html.replace("{{EDITION_DATE}}", date_str)
    html = html.replace("{{EDITION_DATE_DISPLAY}}", date_display)
    html = html.replace("{{EDITION_NUMBER}}", str(edition_number))
    html = html.replace("{{FILTER_PILLS}}", filter_pills)
    html = html.replace("{{CARDS}}", cards_html)
    html = html.replace("{{GRID_CARDS}}", grid_cards_html)
    html = html.replace("{{ARTICLES_JSON}}", json.dumps(articles, ensure_ascii=False))
    html = html.replace("{{GENERATION_TIME}}", now.strftime("%H:%M %Z"))
    html = html.replace("{{FOOTER_NAV}}", footer_nav)

    # Write edition file in editions/
    output_path = editions_dir / f"{date_str}.html"
    with open(output_path, "w") as f:
        f.write(html)

    print(f"[INFO] Edition generated: {output_path}", file=sys.stderr)

    # Archive with timestamp
    archive_path = archives_dir / f"{timestamp_str}.html"
    with open(archive_path, "w") as f:
        f.write(html)

    print(f"[INFO] Archived: {archive_path}", file=sys.stderr)

    # Also write latest.html for deploy script
    latest_path = editions_dir / "latest.html"
    with open(latest_path, "w") as f:
        f.write(html)

    # Update archive index
    build_archive_page(archives_dir, config)

    # Output path to stdout
    print(str(output_path))

if __name__ == "__main__":
    main()
