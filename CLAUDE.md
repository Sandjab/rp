# IA qu'à demander — Contexte projet

## Architecture

Pipeline automatise en 5 phases via `bash scripts/run_edition.sh` :

| Phase | Script | Role |
|-------|--------|------|
| 0 | `websearch_collect.py` | WebSearch via `claude -p` → `.pipeline/00_websearch.json` (tolerant) |
| 1 | `collect.py` | RSS + merge WebSearch + dedup + rank → `.pipeline/01_candidates.json` (20 candidats) |
| 2 | `write_editorial.py` | `claude -p` selectionne 8 articles + edito FR + synthese → `.pipeline/02_editorial.json` |
| 3 | `generate_edition.py` | HTML generation → `editions/YYYY-MM-DD.html` |
| 4 | `deploy.py` | Push gh-pages → https://sandjab.github.io/rp/ |

Les etapes deterministes (RSS, dedup, HTML, deploy) sont des scripts Python. Les etapes intelligentes (recherche web, selection, redaction) utilisent `claude -p` avec des prompts dans `scripts/prompts/`.

## Fichiers cles

| Fichier | Role |
|---------|------|
| `config/revue-presse.yaml` | Config globale (max_articles: 8, topics, queries, source_authority, styling) |
| `config/rss-feeds.yaml` | Flux RSS |
| `scripts/run_edition.sh` | Orchestrateur principal (5 phases, `--no-deploy`) |
| `scripts/websearch_collect.py` | Phase 0 : WebSearch via claude -p |
| `scripts/collect.py` | Phase 1 : RSS + merge + dedup + rank |
| `scripts/write_editorial.py` | Phase 2 : selection + edito via claude -p |
| `scripts/generate_edition.py` | Phase 3 : generation HTML |
| `scripts/deploy.py` | Phase 4 : push gh-pages |
| `scripts/validate.py` | Validation JSON inter-phases (candidates / editorial) |
| `scripts/prompts/editorial.md` | Prompt pour la redaction editoriale |
| `scripts/prompts/websearch.md` | Prompt pour la collecte WebSearch |
| `scripts/parse_rss.py` | Fetch RSS, clean_summary |
| `scripts/deduplicate.py` | Dedup par URL + similarite titre |
| `scripts/rank_articles.py` | Score recency+authority+depth+breaking (pas de topic score), top N |
| `templates/edition.html` | Template HTML unique (CSS + JS inline) |

## Pipeline `.pipeline/`

Repertoire local (gitignore) recree a chaque run. Contient les artefacts intermediaires :
- `00_websearch.json` — resultats WebSearch ([] si echec)
- `01_candidates.json` — 20 candidats post-dedup/rank
- `02_editorial.json` — sortie finale (1 synthese + 8 articles)
- `02_raw_attempt_N.txt` — reponses brutes claude -p pour debug

## Design decisions

- **topic_relevance_score supprime du ranking** : le keyword matching generique (`"Apple"`, `"software"`) laissait passer des articles non pertinents (aspirateurs). Le LLM gere la selection intelligente en Phase 2.
- **20 candidats → 8 selectionnes** : sur-collecte pour donner du choix au LLM.
- **claude -p (forfait Max)** : inclus dans l'abonnement, pas de frais API. Modele Sonnet.
- **WebSearch tolerant** : si Phase 0 echoue, le pipeline continue avec RSS seuls.
- **Transitions** : slide+fade sans rotation. Pas de page-curl.
