#!/usr/bin/env python3
"""Phase 0: Collect articles via WebSearch using claude -p.

Reads queries from config/revue-presse.yaml, builds a prompt,
calls claude -p with WebSearch tool, extracts JSON results.
Writes .pipeline/00_websearch.json.

Tolerant: if the call fails, writes [] and logs a warning.
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from log_utils import setup_logging, load_config, PROJECT_DIR, PIPELINE_DIR

logger = setup_logging("websearch")

PROMPT_PATH = PROJECT_DIR / "scripts" / "prompts" / "websearch.md"
OUTPUT_PATH = PIPELINE_DIR / "00_websearch.json"


def build_queries_block(config):
    """Build the queries list from config topics."""
    lines = []
    for topic in config.get("topics", []):
        tag = topic["tag"]
        queries = topic.get("queries", [])
        for q in queries:
            lines.append(f"- [{tag}] {q}")
    # Fun/not-serious queries
    ns = config.get("not_serious", {})
    for q in ns.get("queries", []):
        lines.append(f"- [Fun] {q}")
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
    today = os.environ.get("RP_EDITION_DATE") or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Load and fill prompt template
    prompt_template = PROMPT_PATH.read_text()
    queries_block = build_queries_block(config)
    prompt = prompt_template.replace("{{QUERIES}}", queries_block).replace("{{DATE}}", today)

    timeout = config.get("edition", {}).get("timeouts", {}).get("websearch", 300)
    logger.info("[WEBSEARCH] Calling claude -p with WebSearch tool...")
    logger.debug(f"Prompt length: {len(prompt)} chars, date={today}, timeout={timeout}s")

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
            timeout=timeout,
        )

        logger.debug(f"claude -p returned: rc={result.returncode}, stdout={len(result.stdout)}B, stderr={len(result.stderr)}B")

        if result.returncode != 0:
            logger.warning(f"[WARN] claude -p failed (exit {result.returncode}): {result.stderr[:500]}")
            with open(OUTPUT_PATH, "w") as f:
                json.dump([], f)
            print(str(OUTPUT_PATH))
            return

        articles = extract_json(result.stdout)
        if articles is None:
            logger.warning("[WARN] Could not extract JSON from claude response")
            # Save raw response for debugging
            raw_path = PIPELINE_DIR / "00_raw_websearch.txt"
            raw_path.write_text(result.stdout)
            logger.warning(f"[WARN] Raw response saved to {raw_path}")
            articles = []

        # Basic validation: filter out items without url/title
        valid = [a for a in articles if isinstance(a, dict) and a.get("url") and a.get("title")]
        logger.info(f"[WEBSEARCH] Got {len(valid)} valid articles from WebSearch")

        with open(OUTPUT_PATH, "w") as f:
            json.dump(valid, f, ensure_ascii=False, indent=2)

    except subprocess.TimeoutExpired:
        logger.warning(f"[WARN] claude -p timed out ({timeout}s)")
        with open(OUTPUT_PATH, "w") as f:
            json.dump([], f)

    except FileNotFoundError:
        logger.warning("[WARN] claude CLI not found in PATH")
        with open(OUTPUT_PATH, "w") as f:
            json.dump([], f)

    except Exception as e:
        logger.warning(f"[WARN] WebSearch failed: {e}")
        with open(OUTPUT_PATH, "w") as f:
            json.dump([], f)

    print(str(OUTPUT_PATH))


if __name__ == "__main__":
    main()
