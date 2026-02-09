# IA qu'à demander

Revue de presse quotidienne automatisee — tech, IA & sciences. Pipeline qui collecte, redige et publie une edition interactive sur GitHub Pages.

**[Voir le site live](https://sandjab.github.io/rp/)**

## Pipeline

```mermaid
flowchart TD
    subgraph Collecte
        WS{{Phase 0 — WebSearch\nclaude -p}}
        WS --> A0[(00_websearch.json)]
        A0 --> COL[Phase 1 — RSS + merge + dedup + rank]
        RSS[(RSS feeds)] --> COL
        COL --> A1[(01_candidates.json\n20 candidats)]
    end

    subgraph Production
        A1 --> ED{{Phase 2 — Selection + edito\nclaude -p}}
        ED --> A2[(02_editorial.json\n1 synthese + 10 articles)]
        A2 --> GEN[Phase 3 — Generation HTML]
        GEN --> HTML[(editions/latest.html)]
        A2 --> LI{{Phase 3b — LinkedIn post\nclaude -p + Gemini Pro}}
        LI --> LIF[(linkedin/\npost + image)]
        HTML --> DEP[Phase 4 — Deploy gh-pages]
        DEP --> SITE([sandjab.github.io/rp/])
    end

    classDef llm fill:#6C5CE7,color:#fff,stroke:#5A4BD1
    classDef script fill:#636e72,color:#fff,stroke:#535c60
    classDef artifact fill:#dfe6e9,color:#2d3436,stroke:#b2bec3
    classDef site fill:#00b894,color:#fff,stroke:#00a381

    class WS,ED,LI llm
    class COL,GEN,DEP script
    class A0,A1,A2,HTML,RSS,LIF artifact
    class SITE site
```

**Legende** : hexagones violets = LLM (`claude -p`) · rectangles gris = scripts Python · documents clairs = artefacts `.pipeline/`

## Installation

```bash
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt
```

Prerequis :
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- `claude` CLI (pour les phases LLM)
- `GOOGLE_API_KEY` dans l'environnement (pour la generation d'images LinkedIn)

## Lancer une edition

```bash
bash scripts/run_edition.sh
```

Sans deploiement (test local) :

```bash
bash scripts/run_edition.sh --no-deploy
```

Sans deploy ni LinkedIn :

```bash
bash scripts/run_edition.sh --no-deploy --no-linkedin
```

## Structure

```
config/
  revue-presse.yaml    # Config globale (topics, queries, styling)
  rss-feeds.yaml       # Flux RSS
scripts/
  run_edition.sh       # Orchestrateur (5 phases)
  websearch_collect.py # Phase 0 : WebSearch via claude -p
  collect.py           # Phase 1 : RSS + merge + dedup + rank
  write_editorial.py   # Phase 2 : selection + edito via claude -p
  generate_edition.py  # Phase 3 : generation HTML
  linkedin_post.py     # Phase 3b : post LinkedIn via claude -p + Gemini Pro
  deploy.py            # Phase 4 : push gh-pages
  validate.py          # Validation JSON inter-phases
  prompts/             # Prompts pour claude -p
    linkedin.md        # Prompt pour le post LinkedIn
templates/
  edition.html         # Template HTML (CSS + JS inline)
editions/              # HTML generes
  archives/
    manifest.json      # Metadonnees des editions (date, numero, titre)
.pipeline/             # Artefacts intermediaires (gitignore)
  linkedin/            # Post LinkedIn (post.txt, comment.txt, image.png)
requirements.txt       # Dependances Python
```

## Scripts

### `run_edition.sh` — Orchestrateur

Lance les 5 phases sequentiellement. Accepte `--no-deploy` pour sauter le deploiement et `--no-linkedin` pour sauter la Phase 3b. Recree `.pipeline/` a chaque run. Les Phases 0 et 3b sont tolerantes : si elles echouent, le pipeline continue.

### `websearch_collect.py` — Phase 0 : recherche web

Appelle `claude -p` avec l'outil WebSearch pour trouver des articles recents. Construit les requetes depuis les topics de `revue-presse.yaml`, remplit le prompt `prompts/websearch.md`, extrait le JSON de la reponse. Ecrit `.pipeline/00_websearch.json` (tableau vide si echec). Sauvegarde la reponse brute pour debug.

### `collect.py` — Phase 1 : collecte + tri

Orchestre les sous-scripts. Enchaine : RSS → merge WebSearch → dedup → filtre IA → ranking top 20. Communique avec les sous-scripts via JSON stdin/stdout. Ecrit `.pipeline/01_candidates.json`.

### `parse_rss.py` — Flux RSS

Charge les feeds depuis `rss-feeds.yaml`, parse chaque flux avec `feedparser` (timeout 10s), filtre les articles de +48h, nettoie le HTML des resumes (max 500 chars), attache le score d'autorite de la source. Renvoie le JSON sur stdout.

### `deduplicate.py` — Deduplication

Elimine les doublons par URL normalisee et par similarite de titre (`SequenceMatcher`). Trie par autorite decroissante pour garder la meilleure source. Seuils : 0.75 pour meme domaine, 0.85 en cross-domaine.

### `rank_articles.py` — Scoring

Score chaque article sur 80 points max :
- **Recency** (0-30) : bonus decroissant selon l'age (<3h, <6h, <12h, <24h, <48h)
- **Authority** (0-25) : depuis `source_authority` du config
- **Depth** (0-15) : bonus si `research_context` ou resume long
- **Breaking** (0-10) : heuristique sur mots-cles ("launches", "breaking"...)

Retourne le top N (`RP_MAX_CANDIDATES`, defaut 20).

### `write_editorial.py` — Phase 2 : redaction

Appelle `claude -p` avec le prompt `prompts/editorial.md` et les 20 candidats. Le LLM selectionne 8 articles, ecrit un titre editorial + resume en francais pour chacun, plus une synthese globale. Max 2 tentatives avec feedback d'erreur au retry. Ecrit `.pipeline/02_editorial.json`.

### `generate_edition.py` — Phase 3 : HTML

Remplit le template `templates/edition.html` avec les articles editorialises. Genere les cards pour le carrousel desktop et la grille mobile, les timestamps relatifs en francais ("il y a 2h"), le numero d'edition. Produit `latest.html` pour le deploy et une copie archivee horodatee dans `editions/archives/`. Met a jour `editions/archives/manifest.json` avec les metadonnees de l'edition (date, numero, titre editorial).

### `linkedin_post.py` — Phase 3b : post LinkedIn

Genere un post LinkedIn optimise a partir de l'edition du jour. Appelle `claude -p` avec le prompt `prompts/linkedin.md` pour produire un texte adapte au format LinkedIn (hook ≤210 chars, corps 800-1200 chars, CTA subtil). Genere une image editoriale via Gemini Pro (SDK `google-genai`), puis superpose le titre et sous-titre via Pillow pour un rendu typographique parfait. Ecrit `.pipeline/linkedin/post.txt`, `comment.txt`, `image.png`. Copie le post dans le presse-papier. Tolerant : si l'image ou le post echouent, le pipeline continue.

### `deploy.py` — Phase 4 : publication

Clone la branche `gh-pages` en shallow, copie `latest.html` comme `index.html`, nettoie les editions residuelles dans `editions/` et copie les archives dans `editions/archives/`. Genere `editions/archives/index.html` depuis `manifest.json` avec numero, titre editorial et date pour chaque edition. Commit et push vers GitHub Pages.

### `validate.py` — Validation inter-phases

Verifie la structure JSON entre les phases. Pour les candidats : tableau, ≥5 articles, champs `title`/`url`/`source`. Pour l'editorial : synthese en position 0, champs `editorial_title`/`editorial_summary`/`url`.

## Stack

- **Python** — collecte RSS, dedup, ranking, generation HTML, deploy
- **Claude Opus via `claude -p`** — recherche web, selection editoriale, redaction
- **Templating HTML** — template unique avec CSS + JS inline
- **GitHub Pages** — hebergement statique via branche `gh-pages`
- **Gemini Pro via `google-genai`** — generation d'images editoriales
- **uv** — gestion de l'environnement virtuel Python
