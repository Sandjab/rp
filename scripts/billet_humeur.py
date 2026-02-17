#!/usr/bin/env python3
"""Standalone billet d'humeur generator from an HTML edition or any HTML article.

Usage (edition mode — HTML with embedded JSON):
    python3 scripts/billet_humeur.py editions/latest.html
    python3 scripts/billet_humeur.py editions/archives/2026-02-11.232324.html --style deep
    python3 scripts/billet_humeur.py editions/latest.html -o billet.txt
    python3 scripts/billet_humeur.py editions/latest.html -o -  # stdout

Usage (article mode — any HTML page saved from a browser):
    python3 scripts/billet_humeur.py ~/Downloads/article.html
    python3 scripts/billet_humeur.py ~/Downloads/article.html --style angle -o -
"""

import argparse
import json
import os
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

import yaml

EDITO_STYLES = {
    "focused": """   **Structure du billet :**
   - Choisis 2-3 themes parmi les articles selectionnes et construis un fil conducteur entre eux
   - Accroche : une phrase forte qui donne le la (question, constat percutant, anecdote)
   - Developpement : connecter ces 2-3 themes avec un fil conducteur personnel. Chaque theme doit servir l'argument general. Ne mentionne PAS les articles qui ne participent pas au fil conducteur.
   - Chute : phrase memorable, punchline, ouverture ou question au lecteur
   - REGLE : le billet ne doit PAS etre un tour d'horizon exhaustif de l'actualite. C'est une chronique selective.""",

    "angle": """   **Structure du billet :**
   - Identifie UN angle, une these, une idee-force qui emerge de l'actualite du jour
   - Accroche : une phrase forte qui pose la these (question, constat percutant, paradoxe)
   - Developpement : deroule l'argument en t'appuyant sur les articles du jour comme preuves ou illustrations. Tu peux mentionner plusieurs articles, mais chaque mention doit servir la these centrale. Pas de digressions hors-sujet.
   - Chute : phrase memorable qui boucle la these, punchline, ouverture
   - REGLE : tout le billet sert UN argument. Si une actu du jour ne rentre pas dans l'angle choisi, ne la mentionne pas.""",

    "deep": """   **Structure du billet :**
   - Identifie LE fait le plus marquant ou le plus interessant du jour parmi les articles selectionnes
   - Accroche : entre directement dans le sujet avec une phrase qui capte l'attention
   - Developpement : analyse en profondeur ce sujet unique — contexte, enjeux, implications, opinion personnelle. Creuse plutot qu'etaler. Les autres articles du jour sont ignores sauf s'ils eclairent directement ce sujet.
   - Chute : phrase memorable, prise de position claire, question ouverte au lecteur
   - REGLE : le billet est une chronique monothematique. Profondeur > largeur.""",
}

EDITO_STYLES_ARTICLE = {
    "focused": """   **Structure du billet :**
   - Choisis 2-3 aspects ou implications de cet article et construis un fil conducteur entre eux
   - Accroche : une phrase forte qui donne le la (question, constat percutant, anecdote)
   - Developpement : connecter ces 2-3 aspects avec un fil conducteur personnel. Chaque point doit servir l'argument general.
   - Chute : phrase memorable, punchline, ouverture ou question au lecteur
   - REGLE : le billet ne doit PAS etre un resume de l'article. C'est une chronique selective.""",

    "angle": """   **Structure du billet :**
   - Identifie UN angle, une these, une idee-force inspiree par cet article
   - Accroche : une phrase forte qui pose la these (question, constat percutant, paradoxe)
   - Developpement : deroule l'argument en t'appuyant sur le contenu de l'article comme preuve ou illustration. Chaque mention doit servir la these centrale. Pas de digressions hors-sujet.
   - Chute : phrase memorable qui boucle la these, punchline, ouverture
   - REGLE : tout le billet sert UN argument.""",

    "deep": """   **Structure du billet :**
   - Identifie LE point central de cet article, le plus marquant ou le plus interessant
   - Accroche : entre directement dans le sujet avec une phrase qui capte l'attention
   - Developpement : analyse en profondeur ce sujet unique — contexte, enjeux, implications, opinion personnelle. Creuse plutot qu'etaler.
   - Chute : phrase memorable, prise de position claire, question ouverte au lecteur
   - REGLE : le billet est une chronique monothematique. Profondeur > largeur.""",
}

ANTI_TICS_V2 = """   **Interdictions stylistiques (V2) :**
   - Phrases formulaiques INTERDITES : "Relisez ca lentement", "C'est peut-etre ca, le vrai X", "ce n'est pas une metaphore", "Et pendant ce temps", "Reste a voir", "Un classique de...", "Ce qui change, c'est...", "Derriere ce chiffre"
   - Mots/adjectifs a ne PAS repeter (max 1 occurrence par billet) : "signal", "enjeu", "colossal", "monumentale", "brutal", "galopante", "pivoter", "modele economique", "paradigme", "tectonique", "vertigineux"
   - Max 1 superlatif par paragraphe. Pas de superlatif dans le titre.
   - Guillemets uniquement pour les citations directes et les vrais neologismes. Pas de guillemets autour des termes techniques courants (AI, LLM, fine-tuning, etc.).
   - Ton d'alerte reserve a ce qui le merite vraiment. Le reste en mode sobre et factuel.
   - Pas d'inversion sujet-verbe systematique. Ecrire des phrases dans l'ordre naturel (sujet-verbe-complement) au moins 2 fois sur 3.
   - Pas de question ouverte en chute. Terminer par une affirmation, une prise de position."""

EDITO_STYLES_V2 = {
    "focused": """   **Structure du billet :**
   - Choisis 2-3 themes parmi les articles selectionnes et construis un fil conducteur entre eux
   - Accroche : un fait, un chiffre, un constat precis. Pas de mise en scene, pas d'esbroufe.
   - Developpement : connecter ces 2-3 themes avec un fil conducteur personnel. Chaque theme doit servir l'argument general. Ne mentionne PAS les articles qui ne participent pas au fil conducteur.
   - Chute : position claire, point final. Pas de question au lecteur, pas de "reste a voir".
   - REGLE : le billet ne doit PAS etre un tour d'horizon exhaustif de l'actualite. C'est une chronique selective.""",

    "angle": """   **Structure du billet :**
   - Identifie UN angle, une these, une idee-force qui emerge de l'actualite du jour
   - Accroche : un fait, un chiffre, un constat precis qui pose la these. Pas de question rhetorique.
   - Developpement : deroule l'argument en t'appuyant sur les articles du jour comme preuves ou illustrations. Tu peux mentionner plusieurs articles, mais chaque mention doit servir la these centrale. Pas de digressions hors-sujet.
   - Chute : position claire qui boucle la these. Phrase affirmative, pas interrogative.
   - REGLE : tout le billet sert UN argument. Si une actu du jour ne rentre pas dans l'angle choisi, ne la mentionne pas.""",

    "deep": """   **Structure du billet :**
   - Identifie LE fait le plus marquant ou le plus interessant du jour parmi les articles selectionnes
   - Accroche : entre directement dans le sujet avec un fait ou un chiffre precis. Pas de "mise en bouche".
   - Developpement : analyse en profondeur ce sujet unique — contexte, implications, opinion personnelle. Creuse plutot qu'etaler. Les autres articles du jour sont ignores sauf s'ils eclairent directement ce sujet.
   - Chute : prise de position claire, phrase affirmative. Pas de question ouverte, pas de "l'avenir nous dira".
   - REGLE : le billet est une chronique monothematique. Profondeur > largeur.""",
}

EDITO_STYLES_ARTICLE_V2 = {
    "focused": """   **Structure du billet :**
   - Choisis 2-3 aspects ou implications de cet article et construis un fil conducteur entre eux
   - Accroche : un fait, un chiffre, un constat precis tire de l'article. Pas de mise en scene.
   - Developpement : connecter ces 2-3 aspects avec un fil conducteur personnel. Chaque point doit servir l'argument general.
   - Chute : position claire, point final. Pas de question au lecteur.
   - REGLE : le billet ne doit PAS etre un resume de l'article. C'est une chronique selective.""",

    "angle": """   **Structure du billet :**
   - Identifie UN angle, une these, une idee-force inspiree par cet article
   - Accroche : un fait, un chiffre, un constat precis qui pose la these. Pas de question rhetorique.
   - Developpement : deroule l'argument en t'appuyant sur le contenu de l'article comme preuve ou illustration. Chaque mention doit servir la these centrale. Pas de digressions hors-sujet.
   - Chute : position claire qui boucle la these. Phrase affirmative, pas interrogative.
   - REGLE : tout le billet sert UN argument.""",

    "deep": """   **Structure du billet :**
   - Identifie LE point central de cet article, le plus marquant ou le plus interessant
   - Accroche : entre directement dans le sujet avec un fait ou un chiffre precis.
   - Developpement : analyse en profondeur ce sujet unique — contexte, implications, opinion personnelle. Creuse plutot qu'etaler.
   - Chute : prise de position claire, phrase affirmative. Pas de question ouverte.
   - REGLE : le billet est une chronique monothematique. Profondeur > largeur.""",
}

TEXT_MAX_CHARS = 8000

PROJECT_DIR = Path(__file__).parent.parent
PIPELINE_DIR = PROJECT_DIR / ".pipeline"
MAX_ATTEMPTS = 2


def load_config():
    config_path = PROJECT_DIR / "config" / "revue-presse.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def extract_articles_from_html(html_path):
    """Extract the articles JSON embedded in the HTML edition."""
    text = Path(html_path).read_text()
    match = re.search(r'const\s+articles\s*=\s*(\[.*?\])\s*;', text, re.DOTALL)
    if not match:
        return None
    raw = match.group(1)
    # Undo the <\/ escaping applied by generate_edition.py
    raw = raw.replace("<\\/", "</")
    return json.loads(raw)


class _HTMLTextExtractor(HTMLParser):
    """Extract visible text from arbitrary HTML."""

    _SKIP_TAGS = {"script", "style", "noscript", "svg", "head"}
    _BLOCK_TAGS = {
        "p", "br", "div", "section", "article", "aside", "header", "footer",
        "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote", "pre", "tr",
        "figcaption",
    }

    def __init__(self):
        super().__init__()
        self._result = []
        self._skip_depth = 0
        self._title = None
        self._h1 = None
        self._in_title = False
        self._in_h1 = False

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag in self._BLOCK_TAGS:
            self._result.append("\n")
        if tag == "title":
            self._in_title = True
            self._title_parts = []
        elif tag == "h1" and self._h1 is None:
            self._in_h1 = True
            self._h1_parts = []

    def handle_endtag(self, tag):
        if tag in self._SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth:
            return
        if tag == "title" and self._in_title:
            self._in_title = False
            self._title = "".join(self._title_parts).strip()
        elif tag == "h1" and self._in_h1:
            self._in_h1 = False
            self._h1 = "".join(self._h1_parts).strip()

    def handle_data(self, data):
        if self._skip_depth:
            return
        if self._in_title:
            self._title_parts.append(data)
        if self._in_h1:
            self._h1_parts.append(data)
        self._result.append(data)

    def get_title(self):
        return self._h1 or self._title or ""

    def get_text(self):
        raw = "".join(self._result)
        # Collapse whitespace, keep paragraph breaks
        lines = [" ".join(line.split()) for line in raw.split("\n")]
        return "\n".join(line for line in lines if line).strip()


def extract_text_from_html(html_path):
    """Extract visible text from any HTML file. Returns (title, text) or (None, None)."""
    content = Path(html_path).read_text(errors="replace")
    extractor = _HTMLTextExtractor()
    extractor.feed(content)
    text = extractor.get_text()
    if len(text) < 50:
        return None, None
    title = extractor.get_title()
    # Truncate to TEXT_MAX_CHARS, cutting at last sentence boundary
    if len(text) > TEXT_MAX_CHARS:
        truncated = text[:TEXT_MAX_CHARS]
        last_period = truncated.rfind(".")
        if last_period > TEXT_MAX_CHARS // 2:
            truncated = truncated[: last_period + 1]
        text = truncated
    return title or "Article sans titre", text


def simplify_article(article):
    """Keep only fields useful for the billet prompt."""
    return {
        "editorial_title": article.get("editorial_title", ""),
        "editorial_summary": article.get("editorial_summary", ""),
        "source": article.get("source", ""),
        "matched_topics": article.get("matched_topics", []),
        "url": article.get("url", ""),
    }


def build_prompt(serious_articles, synthesis, style_instructions, anti_tics=""):
    """Build the prompt for claude -p."""
    existing_billet = ""
    if synthesis:
        existing_title = synthesis.get("editorial_title", "")
        existing_text = synthesis.get("editorial_summary", "")
        existing_billet = f"""
## Billet existant (NE PAS repeter, NE PAS paraphraser)

Titre : {existing_title}
Texte : {existing_text}

Tu dois ecrire un billet DIFFERENT. Nouvel angle, nouvelle accroche, nouvelle chute. Ne reprends ni les memes phrases, ni la meme structure, ni le meme fil conducteur."""

    articles_json = json.dumps(
        [simplify_article(a) for a in serious_articles],
        ensure_ascii=False,
        indent=2,
    )

    anti_tics_block = f"\n{anti_tics}\n" if anti_tics else ""

    return f"""Tu es le redacteur en chef d'une revue de presse consacree a l'intelligence artificielle.

## Ta mission

A partir des articles ci-dessous (deja selectionnes et publies), ecris un NOUVEAU billet d'humeur editorial.

## Articles de l'edition

{articles_json}
{existing_billet}

## Instructions
{anti_tics_block}
{style_instructions}

   **Ton adaptatif — choisir selon l'actualite du jour :**
   - Si l'actu est absurde ou contradictoire → ironie, sarcasme leger
   - Si breakthrough majeur → enthousiasme technique, emerveillement assume
   - Si sujet grave (regulation, emploi, ethique) → gravite, analyse tranchee
   - Si l'actu est routiniere → prendre du recul, chercher l'angle decale
   - Melanger les registres si pertinent (humour + analyse)

   **Personnalite de l'auteur (JPG) :**
   - Technicien-artisan polyvalent, exigent intellectuellement
   - Communication directe : phrases courtes, pas de langue de bois
   - Pragmatique : prefere les faits aux buzzwords
   - Sceptique constructif : challenge les annonces creuses, salue les vraies avancees
   - Esprit maker : juge les outils a l'usage, pas au communique de presse
   - Opinions tranchees mais fondees : peut dire "c'est du vent" ou "c'est remarquable"

## Regles

- Tout le contenu est en francais. Les noms propres et termes techniques restent en anglais.
- Ton personnel, direct, intelligent. Ni corporate ni sensationnaliste.
- 10-15 phrases. Pas plus.
- NE PAS ajouter de signature a la fin du billet.
- Ce n'est PAS un resume des articles. C'est un billet personnel qui s'en inspire pour developper un angle, une reflexion, une prise de position.

## Format de sortie

Reponds UNIQUEMENT avec ce format (pas de texte avant ou apres) :

[TITRE]
Un titre accrocheur pour le billet (pas "Synthese du jour" — un vrai titre de chronique)

[BILLET]
Le texte du billet, 10-15 phrases...
"""


def build_prompt_article(title, text, style_instructions, anti_tics=""):
    """Build the prompt for claude -p in article mode."""
    anti_tics_block = f"\n{anti_tics}\n" if anti_tics else ""

    return f"""Tu es le redacteur en chef d'une revue de presse consacree a l'intelligence artificielle.

## Ta mission

Reagis a l'article ci-dessous avec ta propre perspective. Ecris un billet d'humeur editorial.

## Article

**{title}**

{text}

## Instructions
{anti_tics_block}
{style_instructions}

   **Ton adaptatif — choisir selon le contenu de l'article :**
   - Si le sujet est absurde ou contradictoire → ironie, sarcasme leger
   - Si breakthrough majeur → enthousiasme technique, emerveillement assume
   - Si sujet grave (regulation, emploi, ethique) → gravite, analyse tranchee
   - Si le sujet est routinier → prendre du recul, chercher l'angle decale
   - Melanger les registres si pertinent (humour + analyse)

   **Personnalite de l'auteur (JPG) :**
   - Technicien-artisan polyvalent, exigent intellectuellement
   - Communication directe : phrases courtes, pas de langue de bois
   - Pragmatique : prefere les faits aux buzzwords
   - Sceptique constructif : challenge les annonces creuses, salue les vraies avancees
   - Esprit maker : juge les outils a l'usage, pas au communique de presse
   - Opinions tranchees mais fondees : peut dire "c'est du vent" ou "c'est remarquable"

## Regles

- Tout le contenu est en francais. Les noms propres et termes techniques restent en anglais.
- Ton personnel, direct, intelligent. Ni corporate ni sensationnaliste.
- 10-15 phrases. Pas plus.
- NE PAS ajouter de signature a la fin du billet.
- Ce n'est PAS un resume de l'article. C'est un billet personnel qui s'en inspire pour developper un angle, une reflexion, une prise de position.

## Format de sortie

Reponds UNIQUEMENT avec ce format (pas de texte avant ou apres) :

[TITRE]
Un titre accrocheur pour le billet (pas "Synthese du jour" — un vrai titre de chronique)

[BILLET]
Le texte du billet, 10-15 phrases...
"""


def call_claude(prompt):
    """Call claude -p and return stdout."""
    result = subprocess.run(
        [
            "claude", "-p",
            "--model", "opus",
            "--permission-mode", "default",
            "--tools", "",
            "--output-format", "text",
            "--no-session-persistence",
        ],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude -p failed (exit {result.returncode}): {result.stderr[:500]}")
    return result.stdout


def parse_billet(text):
    """Extract title and billet from [TITRE] / [BILLET] markers."""
    title_match = re.search(r'\[TITRE\]\s*\n(.+?)(?:\n\s*\n|\n\[BILLET\])', text, re.DOTALL)
    billet_match = re.search(r'\[BILLET\]\s*\n(.+)', text, re.DOTALL)

    title = title_match.group(1).strip() if title_match else ""
    billet = billet_match.group(1).strip() if billet_match else ""

    return title, billet


def validate_billet(title, billet):
    """Validate the billet. Returns list of errors."""
    errors = []
    if not title:
        errors.append("Titre manquant ou vide. Utilise le format [TITRE] suivi du titre.")
    if not billet:
        errors.append("Billet manquant ou vide. Utilise le format [BILLET] suivi du texte.")
    elif len(billet) < 200:
        errors.append(f"Billet trop court ({len(billet)} caracteres, minimum 200). Ecris 10-15 phrases.")
    return errors


def main():
    parser = argparse.ArgumentParser(
        description="Genere un nouveau billet d'humeur a partir d'une edition HTML ou d'un article HTML quelconque."
    )
    parser.add_argument("html_file", help="Chemin vers un fichier HTML (edition ou article)")
    parser.add_argument(
        "--style", choices=["focused", "angle", "deep"], default=None,
        help="Style editorial (default: config ou env EDITO_STYLE)"
    )
    parser.add_argument(
        "-o", "--output", default=None,
        help="Fichier de sortie (default: .pipeline/billet.txt, '-' pour stdout)"
    )
    parser.add_argument(
        "--prompt-version", choices=["v1", "v2"], default=None,
        help="Version du prompt (default: config ou env PROMPT_VERSION)"
    )
    args = parser.parse_args()

    html_path = Path(args.html_file)
    if not html_path.exists():
        print(f"[ERROR] Fichier introuvable : {html_path}", file=sys.stderr)
        sys.exit(1)

    PIPELINE_DIR.mkdir(exist_ok=True)
    config = load_config()

    # Detect mode: edition (embedded JSON) or article (raw HTML)
    print(f"[BILLET] Extraction depuis {html_path}...", file=sys.stderr)
    mode = None
    articles = None
    article_title = None
    article_text = None

    try:
        articles = extract_articles_from_html(html_path)
    except (json.JSONDecodeError, Exception):
        articles = None

    if articles:
        # Mode edition
        synthesis = None
        serious_articles = []
        for article in articles:
            if article.get("is_synthesis"):
                synthesis = article
            elif not article.get("is_not_serious"):
                serious_articles.append(article)

        if not serious_articles:
            print("[ERROR] Aucun article serieux trouve dans l'edition", file=sys.stderr)
            sys.exit(1)

        mode = "edition"
        print(f"[BILLET] Mode: edition ({len(serious_articles)} articles)", file=sys.stderr)
    else:
        # Try article mode
        article_title, article_text = extract_text_from_html(html_path)
        if article_text:
            mode = "article"
            print(f"[BILLET] Mode: article (\"{article_title[:50]}...\", {len(article_text)} chars)", file=sys.stderr)
        else:
            print("[ERROR] Impossible d'extraire du contenu depuis le HTML (ni JSON d'edition, ni texte exploitable)", file=sys.stderr)
            sys.exit(1)

    # Determine prompt version: CLI > env > config > fallback v1
    prompt_version = args.prompt_version
    if not prompt_version:
        prompt_version = os.environ.get("PROMPT_VERSION")
    if not prompt_version:
        prompt_version = config.get("edition", {}).get("prompt_version", "v1")

    # Determine style
    edito_style = args.style
    if not edito_style:
        edito_style = os.environ.get("EDITO_STYLE")
    if not edito_style:
        edito_style = config.get("edition", {}).get("edito_style", "focused")

    if prompt_version == "v2":
        styles_dict = EDITO_STYLES_V2 if mode == "edition" else EDITO_STYLES_ARTICLE_V2
        anti_tics = ANTI_TICS_V2
    else:
        styles_dict = EDITO_STYLES if mode == "edition" else EDITO_STYLES_ARTICLE
        anti_tics = ""
    style_instructions = styles_dict.get(edito_style, styles_dict["focused"])
    print(f"[BILLET] Style : {edito_style}, Prompt : {prompt_version}", file=sys.stderr)

    # Build prompt
    if mode == "edition":
        base_prompt = build_prompt(serious_articles, synthesis, style_instructions, anti_tics)
    else:
        base_prompt = build_prompt_article(article_title, article_text, style_instructions, anti_tics)

    last_errors = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f"[BILLET] Tentative {attempt}/{MAX_ATTEMPTS}...", file=sys.stderr)

        if attempt == 1:
            prompt = base_prompt
        else:
            error_feedback = "\n".join(f"- {e}" for e in last_errors)
            prompt = (
                base_prompt
                + f"\n\n## ERREURS DE LA TENTATIVE PRECEDENTE\n\n"
                + f"Corrige ces erreurs dans ta reponse :\n{error_feedback}\n"
            )

        try:
            raw_response = call_claude(prompt)
        except Exception as e:
            print(f"[ERROR] claude -p failed: {e}", file=sys.stderr)
            last_errors = [str(e)]
            continue

        # Save raw response for debugging
        raw_path = PIPELINE_DIR / f"billet_raw_attempt_{attempt}.txt"
        raw_path.write_text(raw_response)

        # Parse
        title, billet = parse_billet(raw_response)

        # Validate
        errors = validate_billet(title, billet)
        if errors:
            print(f"[ERROR] Validation echouee ({len(errors)} erreurs, tentative {attempt}) :", file=sys.stderr)
            for err in errors:
                print(f"  - {err}", file=sys.stderr)
            last_errors = errors
            continue

        # Success — write output
        output_text = f"{title}\n\n{billet}"

        output_path = args.output
        if output_path == "-":
            print(output_text)
            return
        elif output_path:
            out = Path(output_path)
            out.write_text(output_text)
            print(f"[BILLET] Ecrit dans {out}", file=sys.stderr)
            print(str(out))
        else:
            out = PIPELINE_DIR / "billet.txt"
            out.write_text(output_text)
            print(f"[BILLET] Ecrit dans {out}", file=sys.stderr)
            print(str(out))

        print(f"[BILLET] Titre : {title}", file=sys.stderr)
        print(f"[BILLET] Longueur : {len(billet)} caracteres", file=sys.stderr)
        return

    # All attempts failed
    print(f"[ERROR] Generation du billet echouee apres {MAX_ATTEMPTS} tentatives", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
