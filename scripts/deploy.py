#!/usr/bin/env python3
"""Deploy latest edition to GitHub Pages (gh-pages branch)."""

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
    edition_file = editions_dir / f"{date_str}.html"
    archive_index = editions_dir / "index.html"

    # Clone into temp dir
    tmp_dir = tempfile.mkdtemp(prefix="rp-deploy-")
    print(f"[INFO] Cloning into {tmp_dir}", file=sys.stderr)

    try:
        # Clone only gh-pages branch (shallow)
        run(["git", "clone", "--branch", branch, "--single-branch", "--depth", "1",
             f"https://github.com/{repo}.git", tmp_dir])

        # Copy latest as index.html
        shutil.copy2(str(latest), f"{tmp_dir}/index.html")

        # Create editions dir in deploy
        deploy_editions = Path(tmp_dir) / "editions"
        deploy_editions.mkdir(exist_ok=True)

        # Copy dated edition
        if edition_file.exists():
            shutil.copy2(str(edition_file), str(deploy_editions / edition_file.name))

        # Copy archive index
        if archive_index.exists():
            shutil.copy2(str(archive_index), str(deploy_editions / "index.html"))

        # Git add, commit, push
        run(["git", "add", "-A"], cwd=tmp_dir)

        # Check if there are changes
        status = run(["git", "status", "--porcelain"], cwd=tmp_dir)
        if not status.stdout.strip():
            print("[INFO] No changes to deploy.", file=sys.stderr)
            return

        run(["git", "commit", "-m", f"Edition {date_str}"], cwd=tmp_dir)
        run(["git", "push", "origin", branch], cwd=tmp_dir)

        print(f"[INFO] Deployed to https://sandjab.github.io/rp/", file=sys.stderr)
        print(f"https://sandjab.github.io/rp/")

    finally:
        # Cleanup
        shutil.rmtree(tmp_dir, ignore_errors=True)
        print(f"[INFO] Cleaned up {tmp_dir}", file=sys.stderr)

if __name__ == "__main__":
    main()
