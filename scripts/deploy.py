#!/usr/bin/env python3
"""Deploy latest edition to GitHub Pages (gh-pages branch)."""

import json
import re
import subprocess
import sys
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

def load_config():
    config_path = Path(__file__).parent.parent / "config" / "revue-presse.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)

def run(cmd, cwd=None, check=True):
    """Run a shell command."""
    print(f"[CMD] {' '.join(cmd)}", file=sys.stderr)
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"[ERROR] {result.stderr}", file=sys.stderr)
        raise RuntimeError(f"Command failed: {' '.join(cmd)}")
    return result

def build_deploy_archive_index(deploy_archives, manifest_path, config_title):
    """Generate archive index.html from manifest.json."""
    # Load manifest or build minimal fallback from filenames
    if manifest_path.exists():
        with open(manifest_path) as f:
            manifest = json.load(f)
    else:
        manifest = []

    # Build lookup from manifest
    by_date = {e["date"]: e for e in manifest}

    # Collect existing archive HTML files
    archive_files = sorted(deploy_archives.glob("????-??-??.html"), reverse=True)
    archive_files = [f for f in archive_files if f.name != "index.html"]

    if not archive_files:
        return

    # Build entries: only files that exist, enriched with manifest data
    entries = []
    for f in archive_files:
        date_str = f.stem  # YYYY-MM-DD
        info = by_date.get(date_str, {})
        entries.append({
            "date": date_str,
            "number": info.get("number", ""),
            "title": info.get("title", ""),
            "filename": f.name,
        })

    items_html = ""
    for e in entries:
        num_html = f'<span class="archive-num">N\u00b0{e["number"]}</span>' if e["number"] else ""
        title_html = f'<span class="archive-title">{e["title"]}</span>' if e["title"] else ""
        items_html += f'''
    <a href="{e['filename']}" class="archive-item">
      {num_html}
      {title_html}
      <span class="archive-date">{e['date']}</span>
    </a>'''

    archive_html = f'''<!DOCTYPE html>
<html lang="fr" data-theme="light">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Archives — {config_title}</title>
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
.archive-item{{display:flex;align-items:center;gap:1rem;padding:1rem 0;border-bottom:1px solid var(--border);
transition:color .2s}}
.archive-item:hover{{color:var(--accent)}}
.archive-num{{font-family:var(--font-m);font-size:0.8rem;color:var(--text-2);white-space:nowrap;min-width:3rem}}
.archive-title{{flex:1;font-family:var(--font-b);font-size:0.95rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.archive-date{{font-family:var(--font-m);font-size:0.85rem;color:var(--text-2);white-space:nowrap}}
</style>
</head>
<body>
<header class="masthead">
  <h1><a href="https://sandjab.github.io/rp/" style="color:inherit;text-decoration:none">Archives</a></h1>
  <a href="../../index.html" class="masthead-link"><svg viewBox="0 0 24 24"><path d="M4 22h16a2 2 0 002-2V4a2 2 0 00-2-2H8a2 2 0 00-2 2v16a2 2 0 01-2 2zm0 0a2 2 0 01-2-2v-9c0-1.1.9-2 2-2h2"/><path d="M18 14h-8M18 18h-8M18 10h-8"/></svg> edito</a>
</header>
<main class="archives">
{items_html}
</main>
</body>
</html>'''

    index_path = deploy_archives / "index.html"
    with open(index_path, "w") as f:
        f.write(archive_html)
    print(f"[INFO] Archive index generated: {index_path}", file=sys.stderr)


def main():
    config = load_config()
    repo = config["github"]["repo"]
    branch = config["github"]["branch"]

    project_dir = Path(__file__).parent.parent
    editions_dir = project_dir / "editions"

    # Find latest edition
    latest = editions_dir / "latest.html"
    if not latest.exists():
        print("[ERROR] No latest.html found. Run generate_edition.py first.", file=sys.stderr)
        sys.exit(1)

    tz = ZoneInfo(config["edition"]["timezone"])
    now = datetime.now(tz)
    date_str = now.strftime("%Y-%m-%d")
    timestamp_str = now.strftime("%Y-%m-%d.%H%M%S")
    edition_file = editions_dir / f"{date_str}.html"
    archives_dir = editions_dir / "archives"

    # Clone into temp dir
    tmp_dir = tempfile.mkdtemp(prefix="rp-deploy-")
    print(f"[INFO] Cloning into {tmp_dir}", file=sys.stderr)

    try:
        # Clone only gh-pages branch (shallow)
        run(["git", "clone", "--branch", branch, "--single-branch", "--depth", "1",
             f"https://github.com/{repo}.git", tmp_dir])

        # Copy latest as index.html
        shutil.copy2(str(latest), f"{tmp_dir}/index.html")

        # Create editions dir structure in deploy
        deploy_editions = Path(tmp_dir) / "editions"
        deploy_editions.mkdir(exist_ok=True)
        deploy_archives = deploy_editions / "archives"
        deploy_archives.mkdir(exist_ok=True)

        # Copy dated edition
        if edition_file.exists():
            shutil.copy2(str(edition_file), str(deploy_editions / edition_file.name))

        # Remove legacy timestamped archives (YYYY-MM-DD.HHMMSS.html)
        ts_pattern = re.compile(r"\d{4}-\d{2}-\d{2}\.\d{6}\.html$")
        for f in deploy_archives.glob("*.html"):
            if ts_pattern.match(f.name):
                f.unlink()
                print(f"[INFO] Removed legacy archive: {f.name}", file=sys.stderr)

        # Copy archives: keep only latest file per day
        if archives_dir.exists():
            by_date = {}
            for f in archives_dir.glob("*.html"):
                if f.name == "index.html":
                    continue
                date_part = f.name.split(".")[0]
                if date_part not in by_date or f.name > by_date[date_part].name:
                    by_date[date_part] = f
            for date_str, f in by_date.items():
                shutil.copy2(str(f), str(deploy_archives / f"{date_str}.html"))

        # Build manifest from timestamped snapshots matching selected archives
        manifest_dst = deploy_archives / "manifest.json"
        if archives_dir and archives_dir.exists():
            merged_manifest = []
            seen_dates = set()
            # For each selected archive, find its matching manifest snapshot
            for date_str, f in by_date.items():
                ts = f.stem  # e.g. "2026-02-10.001737"
                snapshot = archives_dir / f"manifest.{ts}.json"
                if snapshot.exists():
                    with open(snapshot) as sf:
                        snap_data = json.load(sf)
                    # Extract only the entry for this date
                    for entry in snap_data:
                        if entry.get("date") == date_str and date_str not in seen_dates:
                            merged_manifest.append(entry)
                            seen_dates.add(date_str)
                            break
            # Fill remaining dates from the generic manifest
            manifest_src = archives_dir / "manifest.json"
            if manifest_src.exists():
                with open(manifest_src) as mf:
                    generic = json.load(mf)
                for entry in generic:
                    if entry.get("date") not in seen_dates:
                        merged_manifest.append(entry)
                        seen_dates.add(entry["date"])
            merged_manifest.sort(key=lambda e: e.get("date", ""), reverse=True)
            with open(manifest_dst, "w") as mf:
                json.dump(merged_manifest, mf, ensure_ascii=False, indent=2)
        else:
            manifest_src = archives_dir / "manifest.json" if archives_dir.exists() else None
            if manifest_src and manifest_src.exists():
                shutil.copy2(str(manifest_src), str(manifest_dst))
        build_deploy_archive_index(deploy_archives, manifest_dst, config["edition"]["title"])

        # Rewrite nav links for archive context (relative paths differ from root)
        for html_file in deploy_archives.glob("????-??-??.html"):
            content = html_file.read_text()
            content = content.replace('href="editions/archives/index.html"', 'href="index.html"')
            content = content.replace('href="editions/archives/', 'href="')
            html_file.write_text(content)

        # Git add, commit, push
        run(["git", "add", "-A"], cwd=tmp_dir)

        # Check if there are changes
        status = run(["git", "status", "--porcelain"], cwd=tmp_dir)
        if not status.stdout.strip():
            print("[INFO] No changes to deploy.", file=sys.stderr)
            return

        run(["git", "commit", "-m", f"Edition {timestamp_str}"], cwd=tmp_dir)
        run(["git", "push", "origin", branch], cwd=tmp_dir)

        print(f"[INFO] Deployed to https://sandjab.github.io/rp/", file=sys.stderr)
        print(f"https://sandjab.github.io/rp/")

    finally:
        # Cleanup
        shutil.rmtree(tmp_dir, ignore_errors=True)
        print(f"[INFO] Cleaned up {tmp_dir}", file=sys.stderr)

if __name__ == "__main__":
    main()
