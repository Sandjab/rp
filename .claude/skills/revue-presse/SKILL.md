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

## Procedure complete

Suivre ces 6 phases dans l'ordre. Chaque phase depend de la precedente.

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

### Phase 4 — Redaction editoriale

Lire `/tmp/rp_ranked.json`. Pour chaque article retenu :

1. **Reecrire le titre** en francais avec un angle editorial (champ `editorial_title`)
   - Ton : journalistique, informatif, precis
   - Pas de clickbait, pas de points d'exclamation superflus

2. **Rediger un resume** en francais de 2-3 phrases (champ `editorial_summary`)
   - Ton : analytique, factuel, concis
   - Inclure le "pourquoi c'est important"
   - Eviter le jargon inutile

3. Si un `research_context` existe, le reformuler en francais elegant

4. Ecrire le JSON final enrichi dans `/tmp/rp_editorial.json`

### Phase 5 — Generation HTML

```bash
cd /Users/jean-paulgavini/Documents/Dev/RevuePresse && cat /tmp/rp_editorial.json | python3 scripts/generate_edition.py
```

Verifier que le fichier a ete genere dans `editions/YYYY-MM-DD.html`.

### Phase 6 — Deploiement

```bash
cd /Users/jean-paulgavini/Documents/Dev/RevuePresse && python3 scripts/deploy.py
```

Confirmer que le deploiement a reussi en verifiant la sortie.
Afficher l'URL finale : `https://sandjab.github.io/rp/`

## Notes importantes

- Les articles doivent etre du jour (48h max)
- Maximum 15 articles par edition (configurable dans le YAML)
- Le ton editorial est serieux et analytique, pas sensationnaliste
- Tous les resumes sont en francais
- Le HTML genere est autonome (tout CSS+JS inline)
- Le script de deploiement utilise un clone temporaire pour eviter les conflits git
