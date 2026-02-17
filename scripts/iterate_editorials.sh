#!/usr/bin/env bash
# iterate_editorials.sh — Generate multiple editorial variants from the same candidates.
#
# Usage:
#   bash scripts/iterate_editorials.sh                          # Collect + 3 variants
#   bash scripts/iterate_editorials.sh --skip-collect --styles=deep
#   bash scripts/iterate_editorials.sh --tomorrow --styles=deep,angle
#   bash scripts/iterate_editorials.sh --tomorrow --no-deploy --no-linkedin
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PIPELINE_DIR="$PROJECT_DIR/.pipeline"
VARIANTS_DIR="$PIPELINE_DIR/variants"

# ── Defaults ──
STYLES="deep,angle,focused"
SKIP_COLLECT=false
EDITION_DATE=""
PROMPT_VERSION=""
LINKEDIN=true
DEPLOY=true

# ── Parse args ──
for arg in "$@"; do
  case "$arg" in
    --styles=*)        STYLES="${arg#*=}" ;;
    --skip-collect)    SKIP_COLLECT=true ;;
    --tomorrow)        EDITION_DATE=$(date -v+1d '+%Y-%m-%d') ;;
    --date=*)          EDITION_DATE="${arg#*=}" ;;
    --prompt-version=*) PROMPT_VERSION="${arg#*=}" ;;
    --no-linkedin)     LINKEDIN=false ;;
    --no-deploy)       DEPLOY=false ;;
    *) echo "[ERROR] Unknown argument: $arg" >&2; exit 1 ;;
  esac
done

# Export edition date if set
if [ -n "$EDITION_DATE" ]; then
  export RP_EDITION_DATE="$EDITION_DATE"
fi

echo "=========================================="
echo " RevuePresse — Iterate Editorials"
echo " $(date '+%Y-%m-%d %H:%M:%S')"
if [ -n "$EDITION_DATE" ]; then
  echo " Edition date: $EDITION_DATE"
fi
echo " Styles: $STYLES"
if [ -n "$PROMPT_VERSION" ]; then
  echo " Prompt version: $PROMPT_VERSION"
fi
echo "=========================================="

# ── Phase 0+1: Collect candidates (unless --skip-collect) ──
if [ "$SKIP_COLLECT" = true ]; then
  echo ""
  echo "── Phases 0+1: Skipped (--skip-collect) ──"
  if [ ! -f "$PIPELINE_DIR/01_candidates.json" ]; then
    echo "[ERROR] $PIPELINE_DIR/01_candidates.json not found. Run without --skip-collect first." >&2
    exit 1
  fi
  echo "[OK] Using existing 01_candidates.json"
else
  rm -rf "$PIPELINE_DIR"
  mkdir -p "$PIPELINE_DIR"

  echo ""
  echo "── Phase 0: WebSearch ──"
  if python3 "$SCRIPT_DIR/websearch_collect.py"; then
    echo "[OK] Phase 0 complete"
  else
    echo "[WARN] Phase 0 failed, continuing with RSS only"
  fi

  echo ""
  echo "── Phase 1: Collect (RSS + dedup + rank) ──"
  python3 "$SCRIPT_DIR/collect.py"
  python3 "$SCRIPT_DIR/validate.py" "$PIPELINE_DIR/01_candidates.json" --phase candidates
  echo "[OK] Phase 1 complete"
fi

# ── Generate editorial variants ──
mkdir -p "$VARIANTS_DIR"

IFS=',' read -ra STYLE_LIST <<< "$STYLES"
GENERATED=()

for style in "${STYLE_LIST[@]}"; do
  echo ""
  echo "── Phase 2: Editorial variant [$style] ──"
  if EDITO_STYLE="$style" PROMPT_VERSION="${PROMPT_VERSION}" python3 "$SCRIPT_DIR/write_editorial.py"; then
    python3 "$SCRIPT_DIR/validate.py" "$PIPELINE_DIR/02_editorial.json" --phase editorial
    cp "$PIPELINE_DIR/02_editorial.json" "$VARIANTS_DIR/editorial_${style}.json"
    GENERATED+=("$style")
    echo "[OK] Variant '$style' saved"
  else
    echo "[WARN] Variant '$style' failed, skipping"
  fi
done

if [ ${#GENERATED[@]} -eq 0 ]; then
  echo ""
  echo "[ERROR] No variants were generated successfully." >&2
  exit 1
fi

# ── Display summary ──
echo ""
echo "=========================================="
echo " Résumé des variantes"
echo "=========================================="

for style in "${GENERATED[@]}"; do
  echo ""
  echo "── [$style] ──"
  python3 -c "
import json, sys
with open('$VARIANTS_DIR/editorial_${style}.json') as f:
    data = json.load(f)
synth = data[0]
print(f\"  Titre : {synth.get('editorial_title', '(sans titre)')}\")
summary = synth.get('editorial_summary', '')
if len(summary) > 200:
    summary = summary[:200] + '...'
print(f\"  Extrait : {summary}\")
print(f\"  Articles ({len(data)-1}) :\")
for a in data[1:]:
    print(f\"    - {a.get('editorial_title', a.get('title', '?'))}\")
"
done

# ── Interactive choice ──
echo ""
echo "=========================================="
echo " Variantes disponibles : ${GENERATED[*]}"
echo "=========================================="

if [ ${#GENERATED[@]} -eq 1 ]; then
  CHOICE="${GENERATED[0]}"
  echo "Une seule variante generee, selection automatique : $CHOICE"
else
  while true; do
    read -rp "Choisis une variante (${GENERATED[*]}) : " CHOICE
    for g in "${GENERATED[@]}"; do
      if [ "$CHOICE" = "$g" ]; then
        break 2
      fi
    done
    echo "[ERROR] Choix invalide. Options : ${GENERATED[*]}"
  done
fi

# ── Generate HTML from chosen variant ──
echo ""
echo "── Phase 3: Generate HTML (variant: $CHOICE) ──"
cp "$VARIANTS_DIR/editorial_${CHOICE}.json" "$PIPELINE_DIR/02_editorial.json"
python3 "$SCRIPT_DIR/generate_edition.py" "$PIPELINE_DIR/02_editorial.json"
echo "[OK] Phase 3 complete"

# ── Phase 3b: LinkedIn post ──
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
echo " Pipeline termine avec succes (style: $CHOICE)"
echo "=========================================="
