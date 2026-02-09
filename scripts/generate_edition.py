#!/usr/bin/env python3
"""Generate HTML edition from template and article data."""

import json
import re
import sys
import os
from datetime import datetime
from html import escape as h
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
    """Count unique days in archives + 1."""
    if not archives_dir.exists():
        return 1
    existing = list(archives_dir.glob("????-??-??.*.html"))
    # Extraire les dates uniques (partie avant le premier '.')
    unique_days = set()
    for f in existing:
        date_part = f.name.split(".")[0]  # "YYYY-MM-DD"
        unique_days.add(date_part)
    # +1 seulement si aujourd'hui n'est pas deja dans les archives
    today = datetime.now().strftime("%Y-%m-%d")
    if today in unique_days:
        return len(unique_days)
    return len(unique_days) + 1

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

def build_synthesis_card_html(article, index, articles, config, now):
    """Build the synthesis card HTML block with clickable article refs."""
    topics_config = {t["tag"]: t for t in config.get("topics", [])}
    tags_html = ""
    for tag in article.get("matched_topics", article.get("topics", []))[:3]:
        tc = topics_config.get(tag, {})
        color = tc.get("color", "#666")
        tags_html += f'<span class="tag-pill" style="background:{h(color)}20;color:{h(color)};opacity:0.85">{h(tag)}</span>'

    title = h(article.get("editorial_title", article.get("title", "")))
    summary = h(article.get("editorial_summary", article.get("summary", ""))).replace("\n", "<br>")

    signature = config.get("edition", {}).get("signature", "")
    if signature:
        summary = re.sub(r'\s*—\s*' + re.escape(h(signature)) + r'\s*$', '', summary)
    signature_html = f'\n      <span class="edito-signature">— {h(signature)}</span>' if signature else ""
    author_short = h(signature.split()[0]) if signature else "l'auteur"

    return f'''
    <article class="card synthesis-card" data-index="{index}">
      <span class="synth-tag">L'edito de {author_short}</span>
      <div class="card-tags">{tags_html}</div>
      <h2 class="card-title">{title}</h2>
      <p class="card-summary">{summary}</p>{signature_html}
    </article>'''


def build_synthesis_grid_card_html(article, index, articles, config, now):
    """Build the synthesis grid card HTML block."""
    topics_config = {t["tag"]: t for t in config.get("topics", [])}
    tags_html = ""
    for tag in article.get("matched_topics", article.get("topics", []))[:3]:
        tc = topics_config.get(tag, {})
        color = tc.get("color", "#666")
        tags_html += f'<span class="tag-pill" style="background:{h(color)}20;color:{h(color)};opacity:0.85">{h(tag)}</span>'

    title = h(article.get("editorial_title", article.get("title", "")))
    summary = h(article.get("editorial_summary", article.get("summary", ""))).replace("\n", "<br>")

    signature = config.get("edition", {}).get("signature", "")
    if signature:
        summary = re.sub(r'\s*—\s*' + re.escape(h(signature)) + r'\s*$', '', summary)
    signature_html = f'\n      <span class="edito-signature">— {h(signature)}</span>' if signature else ""
    author_short = h(signature.split()[0]) if signature else "l'auteur"

    return f'''
    <article class="grid-card synthesis-grid" data-index="{index}">
      <span class="synth-tag">L'edito de {author_short}</span>
      <div class="card-tags">{tags_html}</div>
      <h2 class="card-title">{title}</h2>
      <p class="card-summary">{summary}</p>{signature_html}
    </article>'''


def build_not_serious_card_html(article, index, config, now):
    """Build the 'not serious' card HTML block."""
    ns_config = config.get("not_serious", {})
    ns_tag = h(ns_config.get("tag", "C'est pas serieux"))
    ns_color = h(ns_config.get("color", "#F59E0B"))
    ns_subtitle = h(ns_config.get("subtitle", "votre temps de lecture ne sera pas rembourse"))

    tags_html = f'<span class="tag-pill" style="background:{ns_color}20;color:{ns_color};opacity:0.85">{ns_tag}</span>'

    title = h(article.get("editorial_title", article.get("title", "")))
    source = h(article.get("source", ""))
    ago = time_ago(article.get("published"), now)
    source_line = f"{source}"
    if ago:
        source_line += f" — {ago}"

    summary = h(article.get("editorial_summary", article.get("summary", ""))).replace("\n", "<br>")
    url = h(article.get("url", "#"))

    return f'''
    <article class="card not-serious-card" data-index="{index}">
      <div class="card-tags">{tags_html}</div>
      <h2 class="card-title">{title}</h2>
      <div class="not-serious-subtitle">{ns_subtitle}</div>
      <div class="card-source">{source_line}</div>
      <p class="card-summary">{summary}</p>
      <a class="card-link" href="{url}" target="_blank" rel="noopener">Lire (a vos risques et perils) <span>&rarr;</span></a>
    </article>'''


def build_not_serious_grid_card_html(article, index, config, now):
    """Build the 'not serious' grid card HTML block."""
    ns_config = config.get("not_serious", {})
    ns_tag = h(ns_config.get("tag", "C'est pas serieux"))
    ns_color = h(ns_config.get("color", "#F59E0B"))
    ns_subtitle = h(ns_config.get("subtitle", "votre temps de lecture ne sera pas rembourse"))

    tags_html = f'<span class="tag-pill" style="background:{ns_color}20;color:{ns_color};opacity:0.85">{ns_tag}</span>'

    title = h(article.get("editorial_title", article.get("title", "")))
    source = h(article.get("source", ""))
    ago = time_ago(article.get("published"), now)
    summary = h(article.get("editorial_summary", article.get("summary", ""))).replace("\n", "<br>")
    url = h(article.get("url", "#"))

    return f'''
    <article class="grid-card not-serious-grid" data-index="{index}" onclick="toggleGridCard(this)">
      <div class="card-tags">{tags_html}</div>
      <h2 class="card-title"><a href="{url}" target="_blank" rel="noopener" onclick="event.stopPropagation()">{title}</a></h2>
      <div class="not-serious-subtitle">{ns_subtitle}</div>
      <div class="card-source">{source} — {ago}</div>
      <p class="card-summary">{summary}</p>
      <div class="grid-card-extra">
        <a class="card-link" href="{url}" target="_blank" rel="noopener" onclick="event.stopPropagation()">Lire (a vos risques et perils) <span>&rarr;</span></a>
      </div>
    </article>'''


def build_card_html(article, index, config, now):
    """Build a single card HTML block."""
    topics_config = {t["tag"]: t for t in config.get("topics", [])}
    tags_html = ""
    for tag in article.get("matched_topics", article.get("topics", []))[:3]:
        tc = topics_config.get(tag, {})
        color = tc.get("color", "#666")
        tags_html += f'<span class="tag-pill" style="background:{h(color)}20;color:{h(color)};opacity:0.85">{h(tag)}</span>'

    title = h(article.get("editorial_title", article.get("title", "")))
    source = h(article.get("source", ""))
    ago = time_ago(article.get("published"), now)
    source_line = f"{source}"
    if ago:
        source_line += f" — {ago}"

    summary = h(article.get("editorial_summary", article.get("summary", ""))).replace("\n", "<br>")
    context = h(article.get("research_context", ""))
    url = h(article.get("url", "#"))

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
      <a class="card-link" href="{url}" target="_blank" rel="noopener">{"Voir le post" if "x.com/" in url or "twitter.com/" in url else "Lire l&#x27;article"} <span>&rarr;</span></a>
    </article>'''

def build_grid_card_html(article, index, config, now):
    """Build a grid card HTML block."""
    topics_config = {t["tag"]: t for t in config.get("topics", [])}
    tags_html = ""
    for tag in article.get("matched_topics", article.get("topics", []))[:3]:
        tc = topics_config.get(tag, {})
        color = tc.get("color", "#666")
        tags_html += f'<span class="tag-pill" style="background:{h(color)}20;color:{h(color)};opacity:0.85">{h(tag)}</span>'

    title = h(article.get("editorial_title", article.get("title", "")))
    source = h(article.get("source", ""))
    ago = time_ago(article.get("published"), now)
    summary = h(article.get("editorial_summary", article.get("summary", ""))).replace("\n", "<br>")
    url = h(article.get("url", "#"))
    context = h(article.get("research_context", ""))

    context_html = ""
    if context:
        context_html = f'''
      <button class="context-toggle" onclick="event.stopPropagation();toggleContext(this)">
        <span class="arrow">&#9656;</span> <span class="ctx-label">Contexte approfondi</span>
      </button>
      <div class="card-context">
        <div class="card-context-inner">{context}</div>
      </div>'''

    return f'''
    <article class="grid-card" data-index="{index}" onclick="toggleGridCard(this)">
      <div class="card-tags">{tags_html}</div>
      <h2 class="card-title"><a href="{url}" target="_blank" rel="noopener" onclick="event.stopPropagation()">{title}</a></h2>
      <div class="card-source">{source} — {ago}</div>
      <p class="card-summary">{summary}</p>
      <div class="grid-card-extra">
        {context_html}
        <a class="card-link" href="{url}" target="_blank" rel="noopener" onclick="event.stopPropagation()">{"Voir le post" if "x.com/" in url or "twitter.com/" in url else "Lire l&#x27;article"} <span>&rarr;</span></a>
      </div>
    </article>'''

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
.masthead-link{{
  font-family:var(--font-m);font-size:0.8rem;
  color:var(--text-2);display:inline-flex;align-items:center;gap:0.3rem;
  transition:color .2s;border:none;background:none;cursor:pointer;text-decoration:none;
}}
.masthead-link:hover{{color:var(--text)}}
.masthead-link svg{{width:14px;height:14px;stroke:currentColor;fill:none;stroke-width:1.5;stroke-linecap:round;stroke-linejoin:round}}
.archives{{max-width:720px;margin:2rem auto;padding:0 clamp(1rem,5vw,4rem)}}
.archive-item{{display:block;padding:1rem 0;border-bottom:1px solid var(--border);
font-family:var(--font-m);font-size:0.9rem;transition:color .2s}}
.archive-item:hover{{color:var(--accent)}}
</style>
</head>
<body>
<header class="masthead">
  <h1><a href="https://sandjab.github.io/rp/" style="color:inherit;text-decoration:none">Archives</a></h1>
  <a href="../index.html" class="masthead-link"><svg viewBox="0 0 24 24"><path d="M4 22h16a2 2 0 002-2V4a2 2 0 00-2-2H8a2 2 0 00-2 2v16a2 2 0 01-2 2zm0 0a2 2 0 01-2-2v-9c0-1.1.9-2 2-2h2"/><path d="M18 14h-8M18 18h-8M18 10h-8"/></svg> edito</a>
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

    # Warn about missing editorial content
    missing_editorial = [a for a in articles if not a.get("editorial_title") or not a.get("editorial_summary")]
    if missing_editorial:
        print(f"[WARN] {len(missing_editorial)}/{len(articles)} articles missing editorial_title or editorial_summary.", file=sys.stderr)
        print(f"[WARN] Run the skill Phase 4 (editorial rewriting) to add French titles and summaries.", file=sys.stderr)

    tz = ZoneInfo(config["edition"]["timezone"])
    now = datetime.now(tz)
    date_str = now.strftime("%Y-%m-%d")
    timestamp_str = now.strftime("%Y-%m-%d.%H%M%S")
    JOURS = {"Monday":"Lundi","Tuesday":"Mardi","Wednesday":"Mercredi",
             "Thursday":"Jeudi","Friday":"Vendredi","Saturday":"Samedi","Sunday":"Dimanche"}
    MOIS = {"January":"janvier","February":"février","March":"mars","April":"avril",
            "May":"mai","June":"juin","July":"juillet","August":"août",
            "September":"septembre","October":"octobre","November":"novembre","December":"décembre"}
    day_en = now.strftime("%A")
    month_en = now.strftime("%B")
    date_display = f"{JOURS[day_en]} {now.day} {MOIS[month_en]} {now.year}"

    editions_dir = Path(__file__).parent.parent / "editions"
    editions_dir.mkdir(exist_ok=True)
    archives_dir = editions_dir / "archives"
    archives_dir.mkdir(exist_ok=True)
    edition_number = get_edition_number(archives_dir)

    # Build HTML blocks
    cards_html = ""
    grid_cards_html = ""
    for i, article in enumerate(articles):
        if article.get("is_synthesis"):
            cards_html += build_synthesis_card_html(article, i, articles, config, now)
            grid_cards_html += build_synthesis_grid_card_html(article, i, articles, config, now)
        elif article.get("is_not_serious"):
            cards_html += build_not_serious_card_html(article, i, config, now)
            grid_cards_html += build_not_serious_grid_card_html(article, i, config, now)
        else:
            cards_html += build_card_html(article, i, config, now)
            grid_cards_html += build_grid_card_html(article, i, config, now)

    # Masthead nav — edition page shows archives link only
    masthead_nav = '<a href="editions/archives/index.html" class="masthead-btn" aria-label="Archives"><svg viewBox="0 0 24 24"><path d="M21 8v13H3V8"/><path d="M1 3h22v5H1z"/><path d="M10 12h4"/></svg></a>'

    # Footer nav
    footer_nav = f'<a href="editions/archives/index.html">Archives</a>'

    # Replace placeholders
    html = template
    html = html.replace("{{EDITION_TITLE}}", config["edition"]["title"])
    html = html.replace("{{EDITION_DATE}}", date_str)
    html = html.replace("{{EDITION_DATE_DISPLAY}}", date_display)
    html = html.replace("{{EDITION_NUMBER}}", str(edition_number))
    html = html.replace("{{MASTHEAD_NAV}}", masthead_nav)
    html = html.replace("{{CARDS}}", cards_html)
    html = html.replace("{{GRID_CARDS}}", grid_cards_html)
    articles_json = json.dumps(articles, ensure_ascii=False).replace("</", "<\\/")
    html = html.replace("{{ARTICLES_JSON}}", articles_json)
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

    # Update manifest.json with edition metadata
    manifest_path = archives_dir / "manifest.json"
    if manifest_path.exists():
        with open(manifest_path) as f:
            manifest = json.load(f)
    else:
        manifest = []

    synth = next((a for a in articles if a.get("is_synthesis")), None)
    editorial_title = synth.get("editorial_title", synth.get("title", "")) if synth else ""

    real_articles = [a for a in articles if not a.get("is_synthesis")]
    published_urls = [a["url"] for a in real_articles if a.get("url") and a["url"] != "#"]
    published_titles = [a.get("title", "") for a in real_articles if a.get("title")]

    entry = {
        "date": date_str,
        "number": edition_number,
        "title": editorial_title,
        "urls": published_urls,
        "titles": published_titles,
    }
    manifest = [e for e in manifest if e.get("date") != date_str]
    manifest.append(entry)
    manifest.sort(key=lambda e: e.get("date", ""), reverse=True)

    with open(manifest_path, "w") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"[INFO] Manifest updated: {manifest_path}", file=sys.stderr)

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
