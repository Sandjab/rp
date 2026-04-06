# Dashboard de pilotage — Revue de presse "IA qu'à demander"

## Contexte

Le pipeline éditorial est aujourd'hui piloté via deux scripts bash (`run_edition.sh`, `iterate_editorials.sh`) et un éditeur HTML minimal (`edit_variants.html`). Le workflow nécessite de jongler entre le terminal, l'éditeur, et le navigateur. L'édition des variantes exige de manipuler du JSON brut avec des `\n` manuels.

Ce dashboard remplace l'ensemble par une interface unique qui pilote toutes les phases, de la collecte au deploy, avec édition visuelle des variantes et génération d'image interactive.

## Stack technique

| Composant | Technologie |
|-----------|-------------|
| Frontend | Vite + React + TypeScript + Tailwind CSS + shadcn/ui |
| Backend | Python stdlib (`http.server`) — extension du serveur existant |
| Communication temps réel | SSE (Server-Sent Events) pour les logs et la progression |
| Build | Le serveur Python sert les fichiers buildés (`dashboard/dist/`) |

Un seul process, un seul port. `python scripts/dashboard_server.py` lance tout.

## Structure de fichiers

```
dashboard/                      ← app Vite (nouveau)
  index.html
  package.json
  tsconfig.json
  vite.config.ts
  tailwind.config.ts
  components.json               ← config shadcn/ui
  src/
    main.tsx
    App.tsx
    lib/
      api.ts                    ← fetch wrappers + SSE client
      types.ts                  ← types partagés (Phase, StepStatus, etc.)
    components/
      ui/                       ← shadcn/ui components
      layout/
        AppShell.tsx             ← header + tabs container
        TabNav.tsx               ← onglets Production / Config / Archives
      production/
        ProductionTab.tsx        ← stepper + zone contextuelle
        Stepper.tsx              ← stepper vertical (7 étapes)
        StepLauncher.tsx         ← formulaire de lancement (date, styles, options)
        StepProgress.tsx         ← progress bar + logs pour étapes auto
        StepEditor.tsx           ← éditeur de variantes (étape ④)
        StepImage.tsx            ← génération image (étape ⑤)
        StepDeploy.tsx           ← confirmation deploy (étape ⑦)
        LogPanel.tsx             ← panel de logs streaming (rétractable)
      config/
        ConfigTab.tsx            ← éditeur YAML revue-presse.yaml
      archives/
        ArchivesTab.tsx          ← liste des éditions passées
scripts/
  dashboard_server.py           ← remplace edit_variants_server.py
```

## Les 3 onglets

### Production

Layout : stepper vertical à gauche (~160px), zone contextuelle à droite (reste de l'écran), panel de logs rétractable en bas.

Le stepper affiche en permanence :
- Le numéro d'édition et la date (calculés depuis le manifest)
- L'état de chaque étape (pending / running / done / error / paused)
- Le temps écoulé par étape

#### Les 7 étapes

| # | Nom | Script(s) | Mode | Vue contextuelle |
|---|-----|-----------|------|-----------------|
| ① | WebSearch | `websearch_collect.py` | Auto | Progress + logs |
| ② | Collecte | `collect.py` | Auto | Progress + logs + nombre de candidats |
| ③ | Éditorial | `write_editorial.py` × N | Auto | Progress + variantes en cours, logs |
| ④ | Éditeur | — | **Pause** | 3 colonnes variantes pleine largeur |
| ⑤ | Image | `linkedin_post.py` (partiel) | **Pause** | Prompt + modèle + preview |
| ⑥ | HTML | `generate_edition.py` | Auto | Lien vers le HTML généré |
| ⑦ | Deploy | `deploy.py` | **Pause** | Bouton confirmer + lien site |

#### Formulaire de lancement (StepLauncher)

Affiché quand aucune exécution n'est en cours. Champs :

- **Date** : date picker, défaut = demain. Affiche "Édition #N du JJ mois AAAA"
- **Styles** : multi-select parmi `deep`, `angle`, `focused` (défaut : les 3)
- **Options** : checkboxes
  - ☐ Passer la collecte (--skip-collect) — réutilise les candidats existants
  - ☐ Sans LinkedIn (--no-linkedin) — saute l'étape image
  - ☐ Sans deploy (--no-deploy) — saute l'étape deploy
- **Bouton** : "Lancer l'édition #N"

Si "Sans LinkedIn" est coché, l'étape ⑤ est grisée et sautée.
Si "Sans deploy" est coché, l'étape ⑦ est grisée et sautée.
Si "Passer la collecte" est coché, les étapes ①② sont sautées (marquées "skipped").

#### Étape ④ Éditeur (StepEditor)

Reprend l'éditeur de variantes actuel, adapté en React :
- 3 colonnes côte à côte, une par variante, pleine largeur
- Seuls le titre éditorial et la synthèse sont éditables (slot 0)
- Boutons "copier titre →" / "copier édito →" entre variantes
- Diff highlighting (bordure violette quand les variantes diffèrent)
- Enregistrer (Ctrl+S) sauvegarde le JSON sur le serveur
- **"Publier & Continuer →"** : publie la variante choisie vers `02_editorial.json` et passe à l'étape ⑤

#### Étape ⑤ Image (StepImage)

Layout : prompt à gauche (flex:1), preview à droite (~340px).

**Colonne gauche :**
- Textarea avec le prompt d'image (généré automatiquement par Claude à l'arrivée sur l'étape)
- Bouton "Régénérer prompt" — relance `claude -p` avec le prompt linkedin.md
- Dropdown modèle : liste depuis `config/image-models.yaml`, défaut `gemini-3-pro-image-preview`
- Bouton "Générer image"

**Colonne droite :**
- Preview de l'image générée (1200×627px, ratio LinkedIn)
- L'image affichée est la version finale avec overlay texte (titre + numéro d'édition)
- Infos : dimensions, modèle utilisé, temps de génération
- Bouton "Regénérer" (même prompt, nouvelle image)
- Bouton **"Valider → HTML"** pour passer à l'étape ⑥

#### Étape ⑦ Deploy (StepDeploy)

- Résumé de ce qui va être déployé (titre, nombre d'articles, date)
- Lien de preview vers le HTML local
- Bouton **"Déployer"** avec confirmation (double-clic comme l'éditeur actuel)
- Après deploy : lien vers `https://sandjab.github.io/rp/`

### Config

Éditeur pour `config/revue-presse.yaml` :
- Affichage structuré par section (edition, topics, source_authority, styling, linkedin)
- Modification en place des valeurs
- Bouton "Sauvegarder" pour écrire le YAML
- Pas de formulaire complexe — un éditeur de texte YAML suffit dans un premier temps, avec coloration syntaxique via un composant type CodeMirror/Monaco ou simplement un textarea monospace

### Archives

- Liste des éditions passées depuis le manifest (numéro, date, titre)
- Lien pour ouvrir chaque archive HTML
- Informations : nombre d'articles, sources utilisées

## API Backend

### Endpoints existants (conservés)

```
GET  /api/variants              → {variants: [...], published: "..."}
GET  /api/variant/<name>        → JSON array
POST /api/variant/<name>        → save variant
POST /api/publish/<name>        → copy to 02_editorial.json
GET  /api/current               → 02_editorial.json
```

### Nouveaux endpoints

```
GET  /api/edition/next          → {number, date, title}
     Lit le manifest, calcule le prochain numéro et la date.

POST /api/pipeline/start        → {ok, run_id}
     Body: {date, styles: [...], skip_collect, no_linkedin, no_deploy}
     Lance la pipeline. Chaque phase est un subprocess.
     Retourne un run_id pour le suivi.

GET  /api/pipeline/events       → SSE stream
     Server-Sent Events. Chaque événement :
     - {type: "phase_start", phase: "websearch", timestamp}
     - {type: "log", phase: "websearch", line: "...", stream: "stdout"|"stderr"}
     - {type: "phase_done", phase: "websearch", duration_s, exit_code}
     - {type: "phase_error", phase: "websearch", error: "..."}
     - {type: "pause", phase: "editor", reason: "interactive"}
     - {type: "pipeline_done"}

POST /api/pipeline/resume       → {ok}
     Reprend après une pause (editor validé, image validée, deploy confirmé).

POST /api/pipeline/abort        → {ok}
     Kill le subprocess en cours, annule le run.

GET  /api/config                → contenu YAML brut (string)
POST /api/config                → sauvegarde YAML
     Body: {content: "yaml string"}

GET  /api/archives              → JSON array du manifest (depuis gh-pages local)

POST /api/image/prompt          → {prompt: "..."}
     Lance claude -p avec le prompt linkedin.md + editorial.
     Retourne le prompt d'image généré.

POST /api/image/generate        → {ok, image_path}
     Body: {prompt, model}
     Appelle l'API Gemini/Imagen, applique l'overlay texte.
     Retourne le chemin de l'image générée.

GET  /api/image/preview         → image/png
     Sert l'image générée pour affichage dans le frontend.
```

### Gestion des processus

Le serveur maintient un état global `PipelineRun` :
```python
class PipelineRun:
    run_id: str
    date: str
    styles: list[str]
    options: dict           # skip_collect, no_linkedin, no_deploy
    current_phase: str      # "websearch" | "collect" | ... | "done"
    phase_status: dict      # {phase: "pending"|"running"|"done"|"error"|"skipped"|"paused"}
    process: subprocess.Popen | None
    sse_clients: list       # connexions SSE actives
    start_time: float
    phase_times: dict       # {phase: duration_s}
```

Chaque phase auto lance un subprocess avec `stdout=PIPE, stderr=PIPE`. Un thread lit les pipes ligne par ligne et envoie les événements SSE. Quand le process termine, on vérifie le code retour et on passe à la phase suivante (ou erreur).

Aux phases interactives, le serveur envoie un événement `pause` et attend un `POST /api/pipeline/resume`.

## Exécution des phases

Mapping phase → script :

```python
PHASES = {
    "websearch": {
        "cmd": ["python", "scripts/websearch_collect.py"],
        "env": {"RP_EDITION_DATE": "{date}"},
        "auto": True,
    },
    "collect": {
        "cmd": ["python", "scripts/collect.py"],
        "env": {"RP_EDITION_DATE": "{date}", "RP_MAX_CANDIDATES": "25"},
        "auto": True,
    },
    "editorial": {
        "cmd": ["python", "scripts/write_editorial.py"],
        "env": {"EDITO_STYLE": "{style}", "PROMPT_VERSION": "v2"},
        "auto": True,
        "repeat_for_styles": True,  # lancé N fois, une par style
    },
    "editor": {
        "cmd": None,  # pas de script, étape interactive
        "auto": False,
    },
    "image": {
        "cmd": None,  # étape interactive, pas de subprocess auto
        "auto": False,
        # Sous-actions déclenchées par le frontend :
        # - POST /api/image/prompt → génère le prompt via claude -p
        # - POST /api/image/generate → appelle l'API Gemini, overlay texte
    },
    "html": {
        "cmd": ["python", "scripts/generate_edition.py"],
        "auto": True,
    },
    "deploy": {
        "cmd": ["python", "scripts/deploy.py"],
        "auto": False,  # confirmation manuelle
    },
}
```

## Compatibilité cross-platform (macOS / Windows)

Le dashboard doit fonctionner identiquement sur macOS et Windows. Le développement initial a été fait sous macOS, l'usage courant est sous Windows.

### Ce qui est déjà cross-platform

- Tous les scripts Python utilisent `sys.executable` pour lancer les sous-scripts (pas de hardcode `python3`)
- `pathlib.Path` pour tous les chemins
- `subprocess.run` sans `shell=True`
- `claude` CLI fonctionne sur les deux OS
- Git fonctionne sur les deux OS (via Git for Windows)

### Adaptations nécessaires

**1. Les scripts .sh sont remplacés par le dashboard**
`run_edition.sh` et `iterate_editorials.sh` ne sont plus utilisés. Le dashboard orchestre directement les scripts Python. Pas besoin de bash.

**2. Clipboard : `pbcopy` → API navigateur**
`linkedin_post.py` utilise `pbcopy` (macOS). Dans le dashboard, le clipboard est géré côté frontend via `navigator.clipboard.writeText()` — aucune dépendance OS. Le bouton "Copier" dans l'étape Image ou après le deploy copie le texte LinkedIn dans le presse-papier via le navigateur.

**3. Lancement des sous-processus**
Le serveur Python utilise `sys.executable` pour trouver l'interpréteur Python courant :
```python
cmd = [sys.executable, str(script_path)]
subprocess.Popen(cmd, stdout=PIPE, stderr=PIPE, env=env)
```
Pas de `shell=True`, pas de chemin hardcodé.

**4. Chemins et séparateurs**
Utiliser `pathlib.Path` partout dans le serveur. Les chemins envoyés au frontend via l'API sont normalisés en forward slashes (JSON). Le frontend ne manipule jamais de chemins filesystem directement.

**5. Détection OS (si nécessaire)**
Pour les rares cas où un comportement OS-spécifique est requis :
```python
import sys
IS_WINDOWS = sys.platform == "win32"
```
Cas identifié : aucun pour le moment. Si un cas apparaît à l'implémentation, ajouter un helper `platform_utils.py` plutôt que des `if/else` éparpillés.

**6. Variables d'environnement**
Les scripts utilisent des variables d'env (`RP_EDITION_DATE`, `EDITO_STYLE`, etc.). `os.environ` et `subprocess` les gèrent de manière identique sur les deux OS.

## Design visuel

- **shadcn/ui** pour tous les composants (Button, Tabs, Select, Textarea, Badge, Card, Sheet, ScrollArea, Separator)
- **Tailwind CSS** pour le layout et le spacing
- **Plugin impeccable** pour le polish final
- Dark mode par défaut (cohérent avec le style du projet)
- Typographie : Inter (body), JetBrains Mono (logs, labels), Instrument Serif (titres éditoriaux)
- Couleurs : accent #E63946 (rouge), published #059669 (vert), unsaved #F59E0B (ambre)

## Vérification

1. `cd dashboard && npm run build` — le frontend builde sans erreur
2. `python scripts/dashboard_server.py` — le serveur démarre et sert le frontend
3. L'onglet Production affiche le formulaire de lancement avec le bon numéro d'édition
4. Lancer une pipeline de test → les étapes s'enchaînent, les logs streament
5. Pause à l'étape Éditeur → les variantes s'affichent, édition fonctionne
6. Pause à l'étape Image → le prompt s'affiche, la génération produit une image
7. Pause au Deploy → confirmation, puis deploy effectif
8. L'onglet Config lit et écrit `revue-presse.yaml`
9. L'onglet Archives liste les éditions passées
