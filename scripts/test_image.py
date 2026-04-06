#!/usr/bin/env python3
"""Test image generation across all available Google models.

Models reference: config/image-models.yaml

Usage:
    python scripts/test_image.py                  # use prompt from .pipeline/linkedin/image_prompt.txt
    python scripts/test_image.py "a cute robot"   # use custom prompt
"""

import os
import sys
from pathlib import Path

from google import genai
from google.genai import types

api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    print("GOOGLE_API_KEY not set")
    sys.exit(1)

# Prompt: argument > file > default
if len(sys.argv) > 1:
    prompt = " ".join(sys.argv[1:])
else:
    prompt_path = Path(__file__).parent.parent / ".pipeline" / "linkedin" / "image_prompt.txt"
    if prompt_path.exists():
        prompt = prompt_path.read_text().strip()
    else:
        prompt = "a futuristic cityscape at sunset, digital art style"

print(f"Prompt ({len(prompt)} chars): {prompt[:200]}")
print()

client = genai.Client(api_key=api_key)
output_dir = Path(__file__).parent.parent / ".pipeline" / "linkedin"
output_dir.mkdir(parents=True, exist_ok=True)

results = []


def run_test(name, func):
    """Run a test and collect results."""
    print("=" * 60)
    print(f"  {name}")
    print("=" * 60)
    try:
        path = func()
        print(f"  OK -> {path}")
        results.append((name, "OK", str(path)))
    except Exception as e:
        err = str(e).split("\n")[0][:120]
        print(f"  ERREUR: {err}")
        results.append((name, "ERREUR", err))
    print()


# ── Gemini models (generate_content API) ─────────────────────

def test_gemini(model_id, filename):
    """Test a Gemini model via generate_content."""
    def _run():
        response = client.models.generate_content(
            model=model_id,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
            ),
        )
        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                out = output_dir / filename
                with open(out, "wb") as f:
                    f.write(part.inline_data.data)
                return out
        raise RuntimeError("Aucune image dans la reponse")
    return _run


# ── Imagen models (generate_images API) ──────────────────────

def test_imagen(model_id, filename, aspect_ratio=None):
    """Test an Imagen model via generate_images."""
    def _run():
        config = types.GenerateImagesConfig(
            number_of_images=1,
            output_mime_type="image/png",
        )
        if aspect_ratio:
            config.aspect_ratio = aspect_ratio
        response = client.models.generate_images(
            model=model_id,
            prompt=prompt,
            config=config,
        )
        if response.generated_images:
            out = output_dir / filename
            response.generated_images[0].image.save(str(out))
            return out
        raise RuntimeError("Aucune image retournee")
    return _run


# ── All tests ─────────────────────────────────────────────────

TESTS = [
    # Gemini family
    ("Nano Banana — gemini-2.5-flash-image",
     test_gemini("gemini-2.5-flash-image", "test_nano_banana.png")),

    ("Nano Banana Pro — gemini-3-pro-image-preview",
     test_gemini("gemini-3-pro-image-preview", "test_nano_banana_pro.png")),

    ("Nano Banana 2 — gemini-3.1-flash-image-preview",
     test_gemini("gemini-3.1-flash-image-preview", "test_nano_banana_2.png")),

    # Imagen family
    ("Imagen 4 Fast — imagen-4.0-fast-generate-001",
     test_imagen("imagen-4.0-fast-generate-001", "test_imagen4_fast.png")),

    ("Imagen 4 — imagen-4.0-generate-001",
     test_imagen("imagen-4.0-generate-001", "test_imagen4.png")),

    ("Imagen 4 (16:9) — imagen-4.0-generate-001",
     test_imagen("imagen-4.0-generate-001", "test_imagen4_16x9.png", aspect_ratio="16:9")),

    ("Imagen 4 Ultra — imagen-4.0-ultra-generate-001",
     test_imagen("imagen-4.0-ultra-generate-001", "test_imagen4_ultra.png")),
]

for name, func in TESTS:
    run_test(name, func)

# ── Summary ───────────────────────────────────────────────────

print("=" * 60)
print("  RESULTATS")
print("=" * 60)
ok = sum(1 for _, s, _ in results if s == "OK")
print(f"  {ok}/{len(results)} tests OK\n")
for name, status, detail in results:
    icon = "OK" if status == "OK" else "!!"
    print(f"  [{icon}] {name}")
    if status != "OK":
        print(f"       {detail}")
print()
print(f"Images dans {output_dir}/")
