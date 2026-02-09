#!/usr/bin/env python3
"""Phase 2: Editorial selection and rewriting via claude -p.

Reads .pipeline/01_candidates.json (25 candidates),
calls claude -p to select top 10 + write editorials + synthesis,
validates output, retries on failure (max 2 attempts).
Writes .pipeline/02_editorial.json.
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
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

PROJECT_DIR = Path(__file__).parent.parent
PIPELINE_DIR = PROJECT_DIR / ".pipeline"
PROMPT_PATH = PROJECT_DIR / "scripts" / "prompts" / "editorial.md"
CANDIDATES_PATH = PIPELINE_DIR / "01_candidates.json"
OUTPUT_PATH = PIPELINE_DIR / "02_editorial.json"
MAX_ATTEMPTS = 2


def load_config():
    config_path = PROJECT_DIR / "config" / "revue-presse.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def extract_json(text):
    """Extract JSON array from claude response (handles markdown fences)."""
    # Try ```json ... ``` block
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        text = match.group(1)

    text = text.strip()
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass

    # Try to find array in text
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass

    return None


def validate_editorial(data):
    """Validate editorial output. Returns list of errors."""
    errors = []

    if not isinstance(data, list):
        return ["Response is not a JSON array"]

    if len(data) < 2:
        return ["Expected at least 2 articles (1 synthesis + 1 article)"]

    # Synthesis at position 0
    synth = data[0]
    if not synth.get("is_synthesis"):
        errors.append("Position 0 must have is_synthesis: true")
    if not synth.get("editorial_title"):
        errors.append("Synthesis missing editorial_title")
    if not synth.get("editorial_summary"):
        errors.append("Synthesis missing editorial_summary")

    # Check articles
    for i, article in enumerate(data[1:], start=1):
        if not article.get("editorial_title"):
            errors.append(f"Article {i}: missing editorial_title")
        if not article.get("editorial_summary"):
            errors.append(f"Article {i}: missing editorial_summary")
        if not article.get("url"):
            errors.append(f"Article {i}: missing url")

    # Validate "not serious" article if present
    if len(data) >= 3:
        last = data[-1]
        if last.get("is_not_serious"):
            if "C'est pas serieux" not in last.get("matched_topics", []):
                errors.append("'C'est pas serieux' article should have matched_topics containing 'C'est pas serieux'")

    return errors


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
        timeout=180,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude -p failed (exit {result.returncode}): {result.stderr[:500]}")
    return result.stdout


def main():
    PIPELINE_DIR.mkdir(exist_ok=True)
    config = load_config()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if not CANDIDATES_PATH.exists():
        print(f"[ERROR] Candidates file not found: {CANDIDATES_PATH}", file=sys.stderr)
        sys.exit(1)

    with open(CANDIDATES_PATH) as f:
        candidates = json.load(f)

    print(f"[EDITORIAL] {len(candidates)} candidates loaded", file=sys.stderr)

    # Load prompt template
    prompt_template = PROMPT_PATH.read_text()
    topics_list = ", ".join(t["tag"] for t in config.get("topics", []))

    # Determine edito style: CLI env var overrides config
    edito_style = config.get("edition", {}).get("edito_style", "focused")
    edito_style = os.environ.get("EDITO_STYLE", edito_style)
    style_instructions = EDITO_STYLES.get(edito_style, EDITO_STYLES["focused"])
    print(f"[EDITORIAL] Style: {edito_style}", file=sys.stderr)

    base_prompt = (
        prompt_template
        .replace("{{CANDIDATES_JSON}}", json.dumps(candidates, ensure_ascii=False, indent=2))
        .replace("{{MAX_ARTICLES}}", str(len(candidates)))
        .replace("{{DATE}}", today)
        .replace("{{TOPICS}}", topics_list)
        .replace("{{EDITO_STYLE_INSTRUCTIONS}}", style_instructions)
    )

    last_errors = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f"[EDITORIAL] Attempt {attempt}/{MAX_ATTEMPTS}...", file=sys.stderr)

        # Build prompt (with error feedback on retry)
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
            print(f"[ERROR] claude -p call failed: {e}", file=sys.stderr)
            last_errors = [str(e)]
            continue

        # Save raw response for debugging
        raw_path = PIPELINE_DIR / f"02_raw_attempt_{attempt}.txt"
        raw_path.write_text(raw_response)

        # Extract JSON
        data = extract_json(raw_response)
        if data is None:
            print(f"[ERROR] Could not extract JSON from response (attempt {attempt})", file=sys.stderr)
            last_errors = ["Could not parse JSON from response. Make sure to return ONLY a JSON array."]
            continue

        # Validate
        errors = validate_editorial(data)
        if errors:
            print(f"[ERROR] Validation failed ({len(errors)} errors, attempt {attempt}):", file=sys.stderr)
            for err in errors:
                print(f"  - {err}", file=sys.stderr)
            last_errors = errors
            continue

        # Success
        with open(OUTPUT_PATH, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"[EDITORIAL] Success: {len(data)} articles (1 synthesis + {len(data)-1} articles) -> {OUTPUT_PATH}", file=sys.stderr)
        print(str(OUTPUT_PATH))
        return

    # All attempts failed
    print(f"[ERROR] Editorial generation failed after {MAX_ATTEMPTS} attempts", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
