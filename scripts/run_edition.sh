#!/usr/bin/env bash
# run_edition.sh — Orchestrate the full RevuePresse pipeline.
#
# Usage:
#   bash scripts/run_edition.sh              # Full pipeline with deploy
#   bash scripts/run_edition.sh --no-deploy  # Skip deploy step
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PIPELINE_DIR="$PROJECT_DIR/.pipeline"

# Parse args
DEPLOY=true
LINKEDIN=true
EDITO_STYLE=""
EDITION_DATE=""
PROMPT_VERSION=""
for arg in "$@"; do
  case "$arg" in
    --no-deploy) DEPLOY=false ;;
    --no-linkedin) LINKEDIN=false ;;
    --edito-style=*) EDITO_STYLE="${arg#*=}" ;;
    --prompt-version=*) PROMPT_VERSION="${arg#*=}" ;;
    --tomorrow) EDITION_DATE=$(date -v+1d '+%Y-%m-%d') ;;
    --date=*) EDITION_DATE="${arg#*=}" ;;
    *) echo "[ERROR] Unknown argument: $arg" >&2; exit 1 ;;
  esac
done

# Export edition date override if set
if [ -n "$EDITION_DATE" ]; then
  export RP_EDITION_DATE="$EDITION_DATE"
fi

echo "=========================================="
echo " RevuePresse — Pipeline Edition"
echo " $(date '+%Y-%m-%d %H:%M:%S')"
if [ -n "$EDITION_DATE" ]; then
  echo " Edition date: $EDITION_DATE"
fi
if [ -n "$PROMPT_VERSION" ]; then
  echo " Prompt version: $PROMPT_VERSION"
fi
echo "=========================================="

# Clean pipeline directory
rm -rf "$PIPELINE_DIR"
mkdir -p "$PIPELINE_DIR"

# ── Phase 0: WebSearch collect (tolerant) ──
echo ""
echo "── Phase 0: WebSearch ──"
if python3 "$SCRIPT_DIR/websearch_collect.py"; then
  echo "[OK] Phase 0 complete"
else
  echo "[WARN] Phase 0 failed, continuing with RSS only"
fi

# ── Phase 1: RSS + merge + dedup + rank ──
echo ""
echo "── Phase 1: Collect (RSS + dedup + rank) ──"
python3 "$SCRIPT_DIR/collect.py"
python3 "$SCRIPT_DIR/validate.py" "$PIPELINE_DIR/01_candidates.json" --phase candidates
echo "[OK] Phase 1 complete"

# ── Phase 2: Editorial (LLM) ──
echo ""
echo "── Phase 2: Editorial (claude -p) ──"
if [ -n "$EDITO_STYLE" ] || [ -n "$PROMPT_VERSION" ]; then
  EDITO_STYLE="${EDITO_STYLE}" PROMPT_VERSION="${PROMPT_VERSION}" python3 "$SCRIPT_DIR/write_editorial.py"
else
  python3 "$SCRIPT_DIR/write_editorial.py"
fi
python3 "$SCRIPT_DIR/validate.py" "$PIPELINE_DIR/02_editorial.json" --phase editorial
echo "[OK] Phase 2 complete"

# ── Phase 3: Generate HTML ──
echo ""
echo "── Phase 3: Generate HTML ──"
python3 "$SCRIPT_DIR/generate_edition.py" "$PIPELINE_DIR/02_editorial.json"
echo "[OK] Phase 3 complete"

# ── Phase 3b: LinkedIn post (tolerant) ──
if [ "$LINKEDIN" = true ]; then
  echo ""
  echo "── Phase 3b: LinkedIn post ──"
  if python3 "$SCRIPT_DIR/linkedin_post.py"; then
    echo "[OK] Phase 3b complete"
  else
    echo "[WARN] Phase 3b failed (LinkedIn), continuing"
  fi
else
  echo ""
  echo "── Phase 3b: LinkedIn (skipped: --no-linkedin) ──"
fi

# ── Phase 4: Deploy ──
if [ "$DEPLOY" = true ]; then
  echo ""
  echo "── Phase 4: Deploy ──"
  python3 "$SCRIPT_DIR/deploy.py"
  echo "[OK] Phase 4 complete"
else
  echo ""
  echo "── Phase 4: Deploy (skipped: --no-deploy) ──"
fi

echo ""
echo "=========================================="
echo " Pipeline termine avec succes"
echo "=========================================="
