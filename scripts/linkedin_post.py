#!/usr/bin/env python3
"""Phase 3b: LinkedIn post generation via claude -p + NanoBanana Pro.

Reads .pipeline/02_editorial.json,
calls claude -p to generate a LinkedIn post + comment + image prompt,
generates an editorial image via google-genai (tolerant),
copies the post to macOS clipboard.
Writes .pipeline/linkedin/post.txt, comment.txt, image.png, image_prompt.txt.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

PROJECT_DIR = Path(__file__).parent.parent
PIPELINE_DIR = PROJECT_DIR / ".pipeline"
LINKEDIN_DIR = PIPELINE_DIR / "linkedin"
PROMPT_PATH = PROJECT_DIR / "scripts" / "prompts" / "linkedin.md"
EDITORIAL_PATH = PIPELINE_DIR / "02_editorial.json"
MAX_ATTEMPTS = 2


def load_config():
    config_path = PROJECT_DIR / "config" / "revue-presse.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def get_edition_number(archives_dir):
    """Count unique days in archives + 1."""
    if not archives_dir.exists():
        return 1
    existing = list(archives_dir.glob("????-??-??.*.html"))
    unique_days = set()
    for f in existing:
        date_part = f.name.split(".")[0]
        unique_days.add(date_part)
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    if today in unique_days:
        return len(unique_days)
    return len(unique_days) + 1


def extract_json(text):
    """Extract JSON dict from claude response (handles markdown fences)."""
    # Try ```json ... ``` block
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        text = match.group(1)

    text = text.strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    # Try to find object in text
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

    return None


def validate_linkedin(data):
    """Validate LinkedIn output. Returns list of errors."""
    errors = []

    if not isinstance(data, dict):
        return ["Response is not a JSON object"]

    post = data.get("post", "")
    if not post:
        errors.append("Missing 'post' field")
    elif len(post) < 200:
        errors.append(f"Post too short ({len(post)} chars, min 200)")
    elif len(post) > 3000:
        errors.append(f"Post too long ({len(post)} chars, max 3000)")

    if not data.get("comment"):
        errors.append("Missing 'comment' field")

    if not data.get("image_prompt"):
        errors.append("Missing 'image_prompt' field")

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
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude -p failed (exit {result.returncode}): {result.stderr[:500]}")
    return result.stdout


def generate_image(prompt, output_path):
    """Generate image via Google Generative AI (NanoBanana Pro). Tolerant."""
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("[WARN] GOOGLE_API_KEY not set, skipping image generation", file=sys.stderr)
        return False
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        response = client.models.generate_images(
            model="imagen-4.0-generate-001",
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                output_mime_type="image/png",
            ),
        )
        if response.generated_images:
            image = response.generated_images[0].image
            image.save(str(output_path))
            print(f"[LINKEDIN] Image generated: {output_path}", file=sys.stderr)
            return True
        else:
            print("[WARN] No image returned by API", file=sys.stderr)
            return False
    except Exception as e:
        print(f"[WARN] Image generation failed: {e}", file=sys.stderr)
        return False


def copy_to_clipboard(text):
    """Copy text to macOS clipboard via pbcopy. Returns True on success."""
    try:
        subprocess.run(["pbcopy"], input=text.encode(), check=True, timeout=5)
        return True
    except Exception:
        return False


def main():
    config = load_config()

    # Check if LinkedIn is enabled
    linkedin_config = config.get("linkedin", {})
    if not linkedin_config.get("enabled", True):
        print("[LINKEDIN] Disabled in config, skipping", file=sys.stderr)
        return

    # Check editorial JSON exists
    if not EDITORIAL_PATH.exists():
        print(f"[ERROR] Editorial file not found: {EDITORIAL_PATH}", file=sys.stderr)
        sys.exit(1)

    with open(EDITORIAL_PATH) as f:
        editorial = json.load(f)

    print(f"[LINKEDIN] {len(editorial)} articles loaded from editorial", file=sys.stderr)

    # Prepare output directory
    LINKEDIN_DIR.mkdir(parents=True, exist_ok=True)

    # Compute placeholders
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    archives_dir = PROJECT_DIR / "editions" / "archives"
    edition_number = get_edition_number(archives_dir)

    edition_title = config.get("edition", {}).get("title", "IA qu'a demander")
    edition_url = config.get("github", {}).get("url", "https://sandjab.github.io/rp/")
    hashtags = linkedin_config.get("hashtags", "#IA #IntelligenceArtificielle #Tech #AI #RevueDePresse")

    colors = config.get("styling", {}).get("colors", {}).get("light", {})
    brand_bg = colors.get("background", "#FAFAF8")
    brand_accent = colors.get("accent", "#E63946")
    brand_text = colors.get("text", "#1A1A1A")

    # Load prompt template
    prompt_template = PROMPT_PATH.read_text()

    base_prompt = (
        prompt_template
        .replace("{{EDITORIAL_JSON}}", json.dumps(editorial, ensure_ascii=False, indent=2))
        .replace("{{DATE}}", today)
        .replace("{{EDITION_NUMBER}}", str(edition_number))
        .replace("{{EDITION_TITLE}}", edition_title)
        .replace("{{EDITION_URL}}", edition_url)
        .replace("{{HASHTAGS}}", hashtags)
        .replace("{{BRAND_BG}}", brand_bg)
        .replace("{{BRAND_ACCENT}}", brand_accent)
        .replace("{{BRAND_TEXT}}", brand_text)
    )

    last_errors = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f"[LINKEDIN] Attempt {attempt}/{MAX_ATTEMPTS}...", file=sys.stderr)

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
        raw_path = LINKEDIN_DIR / f"raw_attempt_{attempt}.txt"
        raw_path.write_text(raw_response)

        # Extract JSON
        data = extract_json(raw_response)
        if data is None:
            print(f"[ERROR] Could not extract JSON from response (attempt {attempt})", file=sys.stderr)
            last_errors = ["Could not parse JSON from response. Make sure to return ONLY a JSON object."]
            continue

        # Validate
        errors = validate_linkedin(data)
        if errors:
            print(f"[ERROR] Validation failed ({len(errors)} errors, attempt {attempt}):", file=sys.stderr)
            for err in errors:
                print(f"  - {err}", file=sys.stderr)
            last_errors = errors
            continue

        # Success — write outputs
        post_text = data["post"]
        comment_text = data["comment"]
        image_prompt = data["image_prompt"]

        (LINKEDIN_DIR / "post.txt").write_text(post_text)
        (LINKEDIN_DIR / "comment.txt").write_text(comment_text)
        (LINKEDIN_DIR / "image_prompt.txt").write_text(image_prompt)

        print(f"[LINKEDIN] Post: {len(post_text)} chars", file=sys.stderr)
        print(f"[LINKEDIN] Comment: {len(comment_text)} chars", file=sys.stderr)

        # Generate image (tolerant)
        generate_image(image_prompt, LINKEDIN_DIR / "image.png")

        # Copy to clipboard
        if linkedin_config.get("clipboard", True):
            if copy_to_clipboard(post_text):
                print("[LINKEDIN] Post copied to clipboard", file=sys.stderr)
            else:
                print("[WARN] Could not copy to clipboard", file=sys.stderr)

        # Recap
        print(f"\n[LINKEDIN] Done! Files in {LINKEDIN_DIR}/", file=sys.stderr)
        print(f"  post.txt      ({len(post_text)} chars)", file=sys.stderr)
        print(f"  comment.txt   ({len(comment_text)} chars)", file=sys.stderr)
        if (LINKEDIN_DIR / "image.png").exists():
            print(f"  image.png     (generated)", file=sys.stderr)
        print(f"  image_prompt.txt", file=sys.stderr)

        print(str(LINKEDIN_DIR))
        return

    # All attempts failed
    print(f"[ERROR] LinkedIn post generation failed after {MAX_ATTEMPTS} attempts", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
