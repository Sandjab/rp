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

# ── Help ──
usage() {
  cat <<'HELP'
Usage: bash scripts/iterate_editorials.sh [OPTIONS]

Collecte les candidats une fois, genere plusieurs variantes editoriales
(styles differents), affiche un resume comparatif, puis genere le HTML
a partir de la variante choisie interactivement.

Options:
  --styles=s1,s2,...     Styles a generer, separes par des virgules
                         (default: deep,angle,focused)
                         Styles disponibles : deep, angle, focused
  --skip-collect         Reutiliser .pipeline/01_candidates.json existant
                         (saute les Phases 0+1)
  --tomorrow             Date d'edition = demain (propage RP_EDITION_DATE)
  --date=YYYY-MM-DD      Force la date d'edition (propage RP_EDITION_DATE)
  --prompt-version=v     Version du prompt : v1 ou v2 (default: config)
  --no-linkedin          Saute la Phase 3b (post LinkedIn)
  --no-deploy            Saute la Phase 4 (deploy gh-pages)
  -h, --help             Affiche cette aide et quitte

Exemples:
  # Collecter + 3 variantes + LinkedIn + deploy
  bash scripts/iterate_editorials.sh --tomorrow

  # Iteration locale sans publier
  bash scripts/iterate_editorials.sh --tomorrow --no-deploy --no-linkedin

  # Regener une seule variante sans recolleter
  bash scripts/iterate_editorials.sh --skip-collect --styles=deep

  # Deux variantes avec prompt v2
  bash scripts/iterate_editorials.sh --styles=deep,angle --prompt-version=v2

Workflow:
  1. Phases 0+1 : WebSearch + RSS + dedup + rank → 01_candidates.json
  2. Phase 2    : Pour chaque style, genere une variante editoriale
                  → .pipeline/variants/editorial_{style}.json
  3. Resume     : Affiche titre, extrait et articles de chaque variante
  4. Choix      : Selection interactive de la variante a retenir
  5. Phase 3    : Generation HTML a partir de la variante choisie
  6. Phase 3b   : Post LinkedIn (sauf --no-linkedin)
  7. Phase 4    : Deploy gh-pages (sauf --no-deploy)
HELP
  exit 0
}

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
    -h|--help)         usage ;;
    *) echo "[ERROR] Unknown argument: $arg" >&2; echo "Use -h or --help for usage." >&2; exit 1 ;;
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
