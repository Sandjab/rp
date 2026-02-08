---
name: revue-presse
description: "Genere et publie une revue de presse quotidienne interactive sur GitHub Pages. Agrege les news Tech, IA & Sciences depuis WebSearch, RSS et research-lookup, puis produit un HTML editorial premium avec cards swipeable."
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - WebSearch
  - Skill
user-invocable: true
---

# Skill : Revue de Presse quotidienne

Projet : `/Users/jean-paulgavini/Documents/Dev/RevuePresse/`

## Quand utiliser

- Revue de presse quotidienne (a la demande)
- Quand l'utilisateur demande "revue de presse", "news du jour", "edition"
- Pour generer une nouvelle edition HTML et la deployer

## Procedure complete

Suivre ces 6 phases dans l'ordre. Chaque phase depend de la precedente.
**NE JAMAIS sauter la Phase 4** — c'est elle qui transforme les donnees brutes en contenu editorial francais.

### Phase 1 — Chargement de la configuration

1. Lire `config/revue-presse.yaml` pour obtenir les topics, sources, styling
2. Lire `config/rss-feeds.yaml` pour la liste des flux RSS
3. Verifier que les dependances Python sont installees :
   ```bash
   pip3 install feedparser pyyaml 2>/dev/null
   ```

### Phase 2 — Collecte multi-sources

Collecter les articles depuis 3 types de sources :

**A. WebSearch (2-3 requetes par theme)**
Pour chaque topic dans la config, utiliser WebSearch avec les `queries` definies.
Formater les resultats en objets JSON avec : title, url, source, summary, topics, published.

**B. RSS**
```bash
cd /Users/jean-paulgavini/Documents/Dev/RevuePresse && python3 scripts/parse_rss.py > /tmp/rp_rss.json
```
Lire le fichier de sortie JSON.

**C. research-lookup (optionnel)**
Pour les 3-5 histoires les plus importantes trouvees en A et B, utiliser `Skill("research-lookup")` pour obtenir du contexte approfondi. Ajouter le resultat dans le champ `research_context` de l'article.

### Phase 3 — Traitement des donnees

1. Fusionner tous les articles (WebSearch + RSS + enrichis) dans un seul fichier JSON :
   ```bash
   # Ecrire le JSON fusionne dans /tmp/rp_all.json
   ```

2. Dedupliquer :
   ```bash
   cd /Users/jean-paulgavini/Documents/Dev/RevuePresse && cat /tmp/rp_all.json | python3 scripts/deduplicate.py > /tmp/rp_deduped.json
   ```

3. Classer et scorer :
   ```bash
   cd /Users/jean-paulgavini/Documents/Dev/RevuePresse && cat /tmp/rp_deduped.json | python3 scripts/rank_articles.py > /tmp/rp_ranked.json
   ```

### Phase 4 — Redaction editoriale (OBLIGATOIRE)

**Cette phase est CRITIQUE. Sans elle, l'edition contiendra des titres anglais bruts et aucun resume editorial.**

1. Lire `/tmp/rp_ranked.json`
2. Pour CHAQUE article du JSON, ajouter deux champs obligatoires :

   **`editorial_title`** — Titre en francais, angle editorial
   - Ton : journalistique, informatif, precis
   - Pas de traduction mot-a-mot, reformuler avec un angle
   - Pas de clickbait, pas de points d'exclamation superflus
   - Exemples :
     - EN: "Google launches Gemini 3.0 with real-time capabilities"
     - FR: "Google devoile Gemini 3.0 et ses capacites temps reel"

   **`editorial_summary`** — Resume en francais de 2-3 phrases
   - Ton : analytique, factuel, concis
   - Premiere phrase : le fait principal
   - Deuxieme phrase : le contexte ou l'enjeu
   - Troisieme phrase (optionnelle) : pourquoi c'est important
   - Eviter le jargon inutile, expliquer les acronymes
   - Exemples :
     - "Google a presente Gemini 3.0, son nouveau modele multimodal capable de traiter texte, image et video en temps reel. Le modele surpasse GPT-5 sur plusieurs benchmarks cles, notamment en raisonnement mathematique. Cette annonce intensifie la course aux modeles de fondation entre les geants de la tech."

3. Si un `research_context` existe, le reformuler en francais elegant (3-5 phrases)

4. Ecrire le JSON final enrichi dans `/tmp/rp_editorial.json`

**Verification Phase 4 :**
- [ ] Chaque article a un `editorial_title` en francais
- [ ] Chaque article a un `editorial_summary` en francais (2-3 phrases)
- [ ] Aucun titre n'est une traduction mot-a-mot de l'anglais
- [ ] Les resumes expliquent le "pourquoi c'est important"
- [ ] Tous les liens `url` pointent vers l'article source (pas vers des pages de commentaires)

### Phase 5 — Generation HTML

```bash
cd /Users/jean-paulgavini/Documents/Dev/RevuePresse && cat /tmp/rp_editorial.json | python3 scripts/generate_edition.py
```

Verifier :
- Le fichier a ete genere dans `editions/YYYY-MM-DD.html`
- Le script n'affiche PAS de warning `missing editorial_title or editorial_summary`

### Phase 6 — Deploiement

```bash
cd /Users/jean-paulgavini/Documents/Dev/RevuePresse && python3 scripts/deploy.py
```

Confirmer que le deploiement a reussi en verifiant la sortie.
Afficher l'URL finale : `https://sandjab.github.io/rp/`

## Regles strictes

1. **UNIQUEMENT les dernieres 48h** — si une news est plus ancienne, NE PAS l'inclure
2. **Tout en francais** — titres, resumes, contexte. Les noms propres et termes techniques restent en anglais
3. **Pas de doublons** — si un article apparait dans plusieurs sources, le garder une seule fois
4. **Liens fonctionnels obligatoires** — chaque article doit pointer vers l'article source, pas vers une page de commentaires
5. **Maximum 15 articles** par edition (configurable dans le YAML)
6. **Ton editorial serieux** — analytique, pas sensationnaliste
7. **Phase 4 obligatoire** — ne JAMAIS generer le HTML sans avoir ecrit les champs editorial_title et editorial_summary

## Verification qualite

Avant de deployer, verifier :
- [ ] Ouvrir `editions/YYYY-MM-DD.html` dans le navigateur
- [ ] Tous les titres sont en francais
- [ ] Chaque card a un resume de 2-3 phrases
- [ ] Les liens "Lire l'article" fonctionnent
- [ ] Le swipe fonctionne (ou les fleches clavier)
- [ ] Le dark mode fonctionne
