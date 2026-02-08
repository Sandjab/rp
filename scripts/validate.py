#!/usr/bin/env python3
"""Validate pipeline JSON outputs between phases.

Usage:
    python3 scripts/validate.py .pipeline/01_candidates.json --phase candidates
    python3 scripts/validate.py .pipeline/02_editorial.json --phase editorial
"""

import json
import sys
from pathlib import Path


def validate_candidates(data):
    """Validate candidates JSON (Phase 1 output)."""
    errors = []

    if not isinstance(data, list):
        return ["Expected a JSON array of articles"]

    if len(data) < 5:
        errors.append(f"Too few articles: {len(data)} (minimum 5)")

    required_fields = ["title", "url", "source"]
    for i, article in enumerate(data):
        if not isinstance(article, dict):
            errors.append(f"Article {i}: not a JSON object")
            continue
        for field in required_fields:
            if not article.get(field):
                errors.append(f"Article {i}: missing or empty '{field}'")

    return errors


def validate_editorial(data):
    """Validate editorial JSON (Phase 2 output)."""
    errors = []

    if not isinstance(data, list):
        return ["Expected a JSON array of articles"]

    if len(data) < 2:
        return ["Expected at least 2 articles (1 synthesis + 1 article)"]

    # Check synthesis at position 0
    synth = data[0]
    if not synth.get("is_synthesis"):
        errors.append("Position 0 must be the synthesis (is_synthesis: true)")

    if not synth.get("editorial_title"):
        errors.append("Synthesis missing 'editorial_title'")
    if not synth.get("editorial_summary"):
        errors.append("Synthesis missing 'editorial_summary'")

    # Check all articles (skip synthesis at 0)
    for i, article in enumerate(data[1:], start=1):
        if not isinstance(article, dict):
            errors.append(f"Article {i}: not a JSON object")
            continue
        if not article.get("editorial_title"):
            errors.append(f"Article {i}: missing 'editorial_title'")
        if not article.get("editorial_summary"):
            errors.append(f"Article {i}: missing 'editorial_summary'")
        if not article.get("url"):
            errors.append(f"Article {i}: missing 'url'")

    return errors


def main():
    if len(sys.argv) < 3:
        print("Usage: validate.py <file.json> --phase <candidates|editorial>", file=sys.stderr)
        sys.exit(1)

    filepath = Path(sys.argv[1])
    phase = None
    for i, arg in enumerate(sys.argv):
        if arg == "--phase" and i + 1 < len(sys.argv):
            phase = sys.argv[i + 1]

    if phase not in ("candidates", "editorial"):
        print(f"Unknown phase: {phase}. Use 'candidates' or 'editorial'.", file=sys.stderr)
        sys.exit(1)

    if not filepath.exists():
        print(f"[ERROR] File not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(filepath) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"[ERROR] Invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    if phase == "candidates":
        errors = validate_candidates(data)
    else:
        errors = validate_editorial(data)

    if errors:
        print(f"[VALIDATION FAILED] {len(errors)} error(s) in {filepath}:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"[VALIDATION OK] {filepath} ({phase})", file=sys.stderr)


if __name__ == "__main__":
    main()
