# IA qu'à demander — Contexte projet

## Architecture

Pipeline automatise en 7 etapes, pilote depuis le **dashboard web** ou via les scripts bash legacy.

| Etape | Script | Role |
|-------|--------|------|
| 1 | `websearch_collect.py` | WebSearch via `claude -p` → `.pipeline/00_websearch.json` (tolerant) |
| 2 | `collect.py` | RSS + merge WebSearch + dedup + rank → `.pipeline/01_candidates.json` (25 candidats) |
| 3 | `write_editorial.py` | `claude -p` selectionne 10 articles + edito FR + synthese → `.pipeline/02_editorial.json` |
| 4 | *(interactif)* | Edition des variantes (titre + synthese) dans le dashboard |
| 5 | `linkedin_post.py` | Image LinkedIn via `claude -p` + Gemini (prompt editable, choix du modele) |
| 6 | `generate_edition.py` | HTML generation → `editions/latest.html` + snapshots archives |
| 7 | `deploy.py` | Push gh-pages → https://sandjab.github.io/rp/ |

Les etapes deterministes (RSS, dedup, HTML, deploy) sont des scripts Python. Les etapes intelligentes (recherche web, selection, redaction, image) utilisent `claude -p` ou des API Google.

## Dashboard web (methode recommandee)

Le dashboard remplace les scripts bash pour piloter la pipeline depuis le navigateur.

```bash
python scripts/dashboard_server.py          # demarre sur http://127.0.0.1:7432
python scripts/dashboard_server.py --dev    # mode dev (CORS, pas de fichiers statiques)
python scripts/dashboard_server.py --port 8080 --no-browser
```

**3 onglets :**
- **Production** — stepper guide (7 etapes avec pause auto aux etapes interactives) + reprise manuelle (lancer des etapes individuellement)
- **Config** — editeur YAML pour `revue-presse.yaml` (Ctrl+S pour sauver)
- **Archives** — liste des editions passees depuis le manifest gh-pages

**Workflow typique :**
1. Ouvrir le dashboard
2. Choisir date, styles (deep/angle/focused), options
3. Cliquer "Lancer l'edition #N"
4. Les etapes auto s'enchainent (websearch → collecte → editorial)
5. Pause a l'editeur : comparer les variantes, copier des bouts entre elles, publier
6. Pause a l'image : editer le prompt, choisir le modele, generer/regenerer, valider
7. Pause au deploy : confirmer

**Reprise manuelle :** quand la pipeline est idle, le stepper montre quelles etapes sont lançables (▶), bloquees (🔒), ou deja faites (✓). Cliquer sur une etape verte la lance individuellement.

**Frontend :** `dashboard/` — Vite + React + TypeScript + shadcn/ui + Tailwind. Rebuild avec `cd dashboard && npm run build`.

**Backend :** `scripts/dashboard_server.py` — Python stdlib (http.server), sert le frontend builde + API REST + SSE pour les logs temps reel.

## Fichiers cles

| Fichier | Role |
|---------|------|
| `config/revue-presse.yaml` | Config globale (max_articles: 10, topics, queries, source_authority, styling) |
| `config/rss-feeds.yaml` | Flux RSS |
| `config/image-models.yaml` | Reference des modeles de generation d'image Google (Gemini + Imagen) |
| `scripts/dashboard_server.py` | Serveur dashboard (API + frontend + SSE + pipeline orchestration) |
| `scripts/run_edition.sh` | Orchestrateur legacy bash (5 phases, `--no-deploy`) |
| `scripts/iterate_editorials.sh` | Multi-variantes legacy bash (collecte 1x, N styles, choix interactif) |
| `scripts/websearch_collect.py` | WebSearch via claude -p |
| `scripts/collect.py` | RSS + merge + dedup + rank |
| `scripts/write_editorial.py` | Selection + edito via claude -p |
| `scripts/generate_edition.py` | Generation HTML |
| `scripts/deploy.py` | Push gh-pages |
| `scripts/linkedin_post.py` | Post LinkedIn via claude -p (`--editorial <path>` pour choisir une edition) |
| `scripts/test_image.py` | Test des 7 modeles de generation d'image Google |
| `scripts/validate.py` | Validation JSON inter-phases (candidates / editorial) |
| `scripts/prompts/editorial.md` | Prompt pour la redaction editoriale |
| `scripts/prompts/websearch.md` | Prompt pour la collecte WebSearch |
| `scripts/prompts/linkedin.md` | Prompt pour la generation du prompt d'image |
| `scripts/parse_rss.py` | Fetch RSS, clean_summary |
| `scripts/deduplicate.py` | Dedup par URL + similarite titre |
| `scripts/rank_articles.py` | Score recency+authority+depth+breaking (pas de topic score), top N |
| `templates/edition.html` | Template HTML unique (CSS + JS inline) |
| `dashboard/` | App frontend (Vite + React + shadcn/ui + Tailwind) |

## Pipeline `.pipeline/`

Repertoire local (gitignore) recree a chaque run. Contient les artefacts intermediaires :
- `00_websearch.json` — resultats WebSearch ([] si echec)
- `01_candidates.json` — 20 candidats post-dedup/rank
- `02_editorial.json` — sortie finale (1 synthese + 8 articles)
- `02_raw_attempt_N.txt` — reponses brutes claude -p pour debug
- `variants/editorial_{style}.json` — variantes editoriales (via `iterate_editorials.sh`)

## Archives et snapshots

Chaque run de `generate_edition.py` produit dans `editions/archives/` :
- `{timestamp}.html` — archive HTML timestampee
- `editorial.{timestamp}.json` — snapshot du JSON editorial (source du HTML et du LinkedIn)
- `manifest.{timestamp}.json` — snapshot du manifest (titre, URLs, titres des articles)

Le `manifest.json` et `latest.html` generiques sont ecrases a chaque run.

### Via le dashboard (recommande)

```bash
python scripts/dashboard_server.py
# Ouvrir http://127.0.0.1:7432
# Onglet Production → configurer et lancer
```

### Via les scripts bash (legacy, macOS uniquement)

```bash
# Multi-variantes (recommande)
bash scripts/iterate_editorials.sh --tomorrow
bash scripts/iterate_editorials.sh --tomorrow --no-deploy --no-linkedin
bash scripts/iterate_editorials.sh --skip-collect --styles=deep

# Run simple
bash scripts/run_edition.sh
bash scripts/run_edition.sh --no-deploy
```

Flags iterate_editorials.sh : `--styles=s1,s2`, `--skip-collect`, `--tomorrow`, `--date=YYYY-MM-DD`, `--prompt-version=v1|v2`, `--no-linkedin`, `--no-deploy`, `-h`/`--help`.

Les variantes sont sauvegardees dans `.pipeline/variants/editorial_{style}.json`.

## Generation d'image

Le dashboard propose 6 modeles Google pour la generation d'image LinkedIn (voir `config/image-models.yaml` et `IMAGE-MODELS.md`) :

| Modele | Alias | API |
|--------|-------|-----|
| `gemini-2.5-flash-image` | Nano Banana | generate_content |
| `gemini-3-pro-image-preview` | Nano Banana Pro (defaut) | generate_content |
| `gemini-3.1-flash-image-preview` | Nano Banana 2 | generate_content |
| `imagen-4.0-fast-generate-001` | Imagen 4 Fast | generate_images |
| `imagen-4.0-generate-001` | Imagen 4 | generate_images |
| `imagen-4.0-ultra-generate-001` | Imagen 4 Ultra | generate_images |

Le script `scripts/test_image.py` teste les 7 modeles. Necessite `GOOGLE_API_KEY` dans l'environnement.

## Design decisions

- **topic_relevance_score supprime du ranking** : le keyword matching generique (`"Apple"`, `"software"`) laissait passer des articles non pertinents (aspirateurs). Le LLM gere la selection intelligente en Phase 2.
- **25 candidats → 10 selectionnes** : sur-collecte pour donner du choix au LLM.
- **claude -p (forfait Max)** : inclus dans l'abonnement, pas de frais API. Modele Opus.
- **WebSearch tolerant** : si Phase 0 echoue, le pipeline continue avec RSS seuls.
- **Transitions** : slide+fade sans rotation. Pas de page-curl.
- **Dashboard vs bash** : les scripts .sh restent pour compatibilite mais le dashboard est la methode recommandee (cross-platform, visuel, reprise manuelle).
- **SSE pour les logs** : Server-Sent Events unidirectionnels, pas de websockets. Le serveur Python stdlib gere tout.
