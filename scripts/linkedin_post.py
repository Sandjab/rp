#!/usr/bin/env python3
"""Phase 3b: LinkedIn post generation via claude -p + Gemini Pro + Pillow.

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
from PIL import Image, ImageDraw, ImageFont

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
    """Generate image via Gemini Pro (generate_content API). Tolerant."""
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("[WARN] GOOGLE_API_KEY not set, skipping image generation", file=sys.stderr)
        return False
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-3-pro-image-preview",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
            ),
        )
        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                with open(output_path, "wb") as f:
                    f.write(part.inline_data.data)
                print(f"[LINKEDIN] Image generated (gemini-3-pro): {output_path}", file=sys.stderr)
                return True
        print("[WARN] No image returned by API", file=sys.stderr)
        return False
    except Exception as e:
        print(f"[WARN] Image generation failed: {e}", file=sys.stderr)
        return False


def overlay_text_on_image(image_path, edition_title, edition_number, subtitle):
    """Overlay title + subtitle on image using Pillow. Guarantees perfect text."""
    TARGET_W, TARGET_H = 1200, 627
    BANNER_COLOR = (26, 26, 26)  # #1A1A1A
    BANNER_OPACITY = int(255 * 0.78)
    ACCENT_COLOR = (230, 57, 70)  # #E63946
    ACCENT_HEIGHT = 4
    MARGIN_TOP = 70  # safe-zone LinkedIn
    PADDING_H = 60  # horizontal padding inside banner
    PADDING_V = 20  # vertical padding inside banner

    # Font paths (macOS system fonts)
    LUCIDA_PATH = "/System/Library/Fonts/LucidaGrande.ttc"
    HELVETICA_PATH = "/System/Library/Fonts/HelveticaNeue.ttc"

    img = Image.open(image_path).convert("RGBA")

    # Resize to target dimensions
    if img.size != (TARGET_W, TARGET_H):
        img = img.resize((TARGET_W, TARGET_H), Image.LANCZOS)

    # Load fonts with fallback
    try:
        font_title = ImageFont.truetype(LUCIDA_PATH, 52, index=0)
    except (OSError, IndexError):
        font_title = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 52)

    try:
        font_subtitle = ImageFont.truetype(HELVETICA_PATH, 26, index=0)
    except OSError:
        font_subtitle = ImageFont.load_default()

    # Compose title line: "IA qu'à demander N°2"
    title_text = f"{edition_title} N\u00b0{edition_number}"

    # Truncate subtitle if too long
    max_subtitle_w = TARGET_W - 2 * PADDING_H
    if font_subtitle.getlength(subtitle) > max_subtitle_w:
        while font_subtitle.getlength(subtitle + "\u2026") > max_subtitle_w and len(subtitle) > 10:
            subtitle = subtitle[:-1].rstrip()
        subtitle = subtitle + "\u2026"

    # Measure text
    title_bbox = font_title.getbbox(title_text)
    title_h = title_bbox[3] - title_bbox[1]
    subtitle_bbox = font_subtitle.getbbox(subtitle)
    subtitle_h = subtitle_bbox[3] - subtitle_bbox[1]

    # Banner dimensions
    banner_top = MARGIN_TOP
    banner_height = PADDING_V + title_h + 12 + subtitle_h + PADDING_V
    banner_bottom = banner_top + banner_height

    # Draw semi-transparent banner
    overlay = Image.new("RGBA", (TARGET_W, TARGET_H), (0, 0, 0, 0))
    draw_overlay = ImageDraw.Draw(overlay)
    draw_overlay.rectangle(
        [(0, banner_top), (TARGET_W, banner_bottom)],
        fill=(*BANNER_COLOR, BANNER_OPACITY),
    )
    # Accent bar below banner
    draw_overlay.rectangle(
        [(0, banner_bottom), (TARGET_W, banner_bottom + ACCENT_HEIGHT)],
        fill=(*ACCENT_COLOR, 255),
    )
    img = Image.alpha_composite(img, overlay)

    # Draw text (centered horizontally)
    draw = ImageDraw.Draw(img)
    text_y = banner_top + PADDING_V
    title_w = font_title.getlength(title_text)
    title_x = (TARGET_W - title_w) / 2
    draw.text((title_x, text_y), title_text, font=font_title, fill=(255, 255, 255, 255))
    text_y += title_h + 12
    subtitle_w = font_subtitle.getlength(subtitle)
    subtitle_x = (TARGET_W - subtitle_w) / 2
    draw.text((subtitle_x, text_y), subtitle, font=font_subtitle, fill=(255, 255, 255, 210))

    # Save as RGB PNG
    img.convert("RGB").save(image_path, "PNG")
    print(f"[LINKEDIN] Text overlay applied: {image_path}", file=sys.stderr)


def copy_to_clipboard(text):
    """Copy text to macOS clipboard via pbcopy. Returns True on success."""
    try:
        subprocess.run(["pbcopy"], input=text.encode(), check=True, timeout=5)
        return True
    except Exception:
        return False


def main():
    image_only = "--image-only" in sys.argv

    # --editorial <path>: use a specific editorial JSON instead of .pipeline/02_editorial.json
    editorial_override = None
    if "--editorial" in sys.argv:
        idx = sys.argv.index("--editorial")
        if idx + 1 < len(sys.argv):
            editorial_override = Path(sys.argv[idx + 1])
            if not editorial_override.exists():
                print(f"[ERROR] Editorial file not found: {editorial_override}", file=sys.stderr)
                sys.exit(1)
            print(f"[LINKEDIN] Using editorial override: {editorial_override}", file=sys.stderr)
        else:
            print("[ERROR] --editorial requires a path argument", file=sys.stderr)
            sys.exit(1)

    editorial_path = editorial_override or EDITORIAL_PATH

    config = load_config()

    # Check if LinkedIn is enabled
    linkedin_config = config.get("linkedin", {})
    if not linkedin_config.get("enabled", True):
        print("[LINKEDIN] Disabled in config, skipping", file=sys.stderr)
        return

    # --image-only: regenerate image from existing prompt, skip claude -p
    if image_only:
        prompt_file = LINKEDIN_DIR / "image_prompt.txt"
        if not prompt_file.exists():
            print(f"[ERROR] {prompt_file} not found. Run without --image-only first.", file=sys.stderr)
            sys.exit(1)

        image_prompt = prompt_file.read_text().strip()
        print(f"[LINKEDIN] --image-only: reusing existing prompt ({len(image_prompt)} chars)", file=sys.stderr)

        archives_dir = PROJECT_DIR / "editions" / "archives"
        edition_number = get_edition_number(archives_dir)
        edition_title = config.get("edition", {}).get("title", "IA qu'a demander")

        image_path = LINKEDIN_DIR / "image.png"
        if not generate_image(image_prompt, image_path):
            print("[ERROR] Image generation failed", file=sys.stderr)
            sys.exit(1)

        # Save raw API image before overlay (debug)
        raw_path = LINKEDIN_DIR / "image_raw.png"
        import shutil
        shutil.copy2(image_path, raw_path)
        print(f"[LINKEDIN] Raw API image saved: {raw_path}", file=sys.stderr)

        # Editorial subtitle for overlay
        edito_subtitle = ""
        if editorial_path.exists():
            with open(editorial_path) as f:
                editorial = json.load(f)
            for article in editorial:
                if article.get("editorial_title"):
                    edito_subtitle = article["editorial_title"]
                    break

        overlay_text_on_image(image_path, edition_title, edition_number, edito_subtitle)
        print(f"[LINKEDIN] Image regenerated: {image_path}", file=sys.stderr)
        return

    # Check editorial JSON exists
    if not editorial_path.exists():
        print(f"[ERROR] Editorial file not found: {editorial_path}", file=sys.stderr)
        sys.exit(1)

    with open(editorial_path) as f:
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

        # Generate image (tolerant) + text overlay
        image_path = LINKEDIN_DIR / "image.png"
        image_generated = generate_image(image_prompt, image_path)

        if image_generated:
            # Save raw API image before Pillow overlay (debug)
            raw_path = LINKEDIN_DIR / "image_raw.png"
            import shutil
            shutil.copy2(image_path, raw_path)
            print(f"[LINKEDIN] Raw API image saved: {raw_path}", file=sys.stderr)

            # Extract editorial subtitle from synthesis article
            edito_subtitle = ""
            for article in editorial:
                if article.get("editorial_title"):
                    edito_subtitle = article["editorial_title"]
                    break
            overlay_text_on_image(image_path, edition_title, edition_number, edito_subtitle)

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
