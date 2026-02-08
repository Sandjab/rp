#!/usr/bin/env python3
"""Phase 0: Collect articles via WebSearch using claude -p.

Reads queries from config/revue-presse.yaml, builds a prompt,
calls claude -p with WebSearch tool, extracts JSON results.
Writes .pipeline/00_websearch.json.

Tolerant: if the call fails, writes [] and logs a warning.
"""

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

PROJECT_DIR = Path(__file__).parent.parent
PIPELINE_DIR = PROJECT_DIR / ".pipeline"
PROMPT_PATH = PROJECT_DIR / "scripts" / "prompts" / "websearch.md"
OUTPUT_PATH = PIPELINE_DIR / "00_websearch.json"


def load_config():
    config_path = PROJECT_DIR / "config" / "revue-presse.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def build_queries_block(config):
    """Build the queries list from config topics."""
    lines = []
    for topic in config.get("topics", []):
        tag = topic["tag"]
        queries = topic.get("queries", [])
        for q in queries:
            lines.append(f"- [{tag}] {q}")
    return "\n".join(lines)


def extract_json(text):
    """Extract JSON array from claude response (handles markdown fences)."""
    # Try to find ```json ... ``` block
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        text = match.group(1)

    # Try to parse as JSON array
    text = text.strip()
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass

    # Try to find array in text
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass

    return None


def main():
    PIPELINE_DIR.mkdir(exist_ok=True)
    config = load_config()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Load and fill prompt template
    prompt_template = PROMPT_PATH.read_text()
    queries_block = build_queries_block(config)
    prompt = prompt_template.replace("{{QUERIES}}", queries_block).replace("{{DATE}}", today)

    print("[WEBSEARCH] Calling claude -p with WebSearch tool...", file=sys.stderr)

    try:
        result = subprocess.run(
            [
                "claude", "-p",
                "--model", "opus",
                "--allowedTools", "WebSearch",
                "--permission-mode", "default",
                "--output-format", "text",
                "--no-session-persistence",
            ],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=180,
        )

        if result.returncode != 0:
            print(f"[WARN] claude -p failed (exit {result.returncode}): {result.stderr[:500]}", file=sys.stderr)
            with open(OUTPUT_PATH, "w") as f:
                json.dump([], f)
            print(str(OUTPUT_PATH))
            return

        articles = extract_json(result.stdout)
        if articles is None:
            print("[WARN] Could not extract JSON from claude response", file=sys.stderr)
            # Save raw response for debugging
            raw_path = PIPELINE_DIR / "00_raw_websearch.txt"
            raw_path.write_text(result.stdout)
            print(f"[WARN] Raw response saved to {raw_path}", file=sys.stderr)
            articles = []

        # Basic validation: filter out items without url/title
        valid = [a for a in articles if isinstance(a, dict) and a.get("url") and a.get("title")]
        print(f"[WEBSEARCH] Got {len(valid)} valid articles from WebSearch", file=sys.stderr)

        with open(OUTPUT_PATH, "w") as f:
            json.dump(valid, f, ensure_ascii=False, indent=2)

    except subprocess.TimeoutExpired:
        print("[WARN] claude -p timed out (180s)", file=sys.stderr)
        with open(OUTPUT_PATH, "w") as f:
            json.dump([], f)

    except FileNotFoundError:
        print("[WARN] claude CLI not found in PATH", file=sys.stderr)
        with open(OUTPUT_PATH, "w") as f:
            json.dump([], f)

    except Exception as e:
        print(f"[WARN] WebSearch failed: {e}", file=sys.stderr)
        with open(OUTPUT_PATH, "w") as f:
            json.dump([], f)

    print(str(OUTPUT_PATH))


if __name__ == "__main__":
    main()
