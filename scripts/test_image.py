#!/usr/bin/env python3
"""Test image generation with the actual LinkedIn prompt across different models."""

import os
import sys
from pathlib import Path

from google import genai
from google.genai import types

api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    print("GOOGLE_API_KEY not set")
    sys.exit(1)

# Load actual LinkedIn image prompt
prompt_path = Path(__file__).parent.parent / ".pipeline" / "linkedin" / "image_prompt.txt"
if not prompt_path.exists():
    print(f"Prompt not found: {prompt_path}")
    print("Run the LinkedIn pipeline first, or pass a prompt as argument.")
    sys.exit(1)

prompt = prompt_path.read_text().strip()
print(f"Prompt ({len(prompt)} chars):\n{prompt[:200]}...\n")

client = genai.Client(api_key=api_key)
output_dir = Path(__file__).parent.parent / ".pipeline" / "linkedin"

# --- Test 1: Imagen (generate_images API) ---
print("=" * 60)
print("Test 1: imagen-4.0-generate-001 via generate_images")
print("=" * 60)
try:
    response = client.models.generate_images(
        model="imagen-4.0-generate-001",
        prompt=prompt,
        config=types.GenerateImagesConfig(
            number_of_images=1,
            output_mime_type="image/png",
        ),
    )
    if response.generated_images:
        out = output_dir / "test_imagen.png"
        response.generated_images[0].image.save(str(out))
        print(f"OK -> {out}")
    else:
        print("Aucune image retournee")
except Exception as e:
    print(f"ERREUR: {e}")

# --- Test 2: Imagen with aspect_ratio 16:9 ---
print()
print("=" * 60)
print("Test 2: imagen-4.0-generate-001 + aspect_ratio=16:9")
print("=" * 60)
try:
    response = client.models.generate_images(
        model="imagen-4.0-generate-001",
        prompt=prompt,
        config=types.GenerateImagesConfig(
            number_of_images=1,
            output_mime_type="image/png",
            aspect_ratio="16:9",
        ),
    )
    if response.generated_images:
        out = output_dir / "test_imagen_16x9.png"
        response.generated_images[0].image.save(str(out))
        print(f"OK -> {out}")
    else:
        print("Aucune image retournee")
except Exception as e:
    print(f"ERREUR: {e}")

# --- Test 3: Gemini (generate_content API) ---
print()
print("=" * 60)
print("Test 3: gemini-2.0-flash-preview-image-generation via generate_content")
print("=" * 60)
try:
    response = client.models.generate_content(
        model="gemini-2.0-flash-preview-image-generation",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
        ),
    )
    for part in response.candidates[0].content.parts:
        if part.inline_data and part.inline_data.mime_type.startswith("image/"):
            out = output_dir / "test_gemini_flash.png"
            with open(out, "wb") as f:
                f.write(part.inline_data.data)
            print(f"OK -> {out}")
            break
    else:
        print("Aucune image dans la reponse")
except Exception as e:
    print(f"ERREUR: {e}")

# --- Test 4: Gemini Pro image ---
print()
print("=" * 60)
print("Test 4: gemini-3-pro-image-preview via generate_content")
print("=" * 60)
try:
    response = client.models.generate_content(
        model="gemini-3-pro-image-preview",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
        ),
    )
    for part in response.candidates[0].content.parts:
        if part.inline_data and part.inline_data.mime_type.startswith("image/"):
            out = output_dir / "test_gemini_pro.png"
            with open(out, "wb") as f:
                f.write(part.inline_data.data)
            print(f"OK -> {out}")
            break
    else:
        print("Aucune image dans la reponse")
except Exception as e:
    print(f"ERREUR: {e}")

print()
print("Done. Compare les images dans .pipeline/linkedin/")
