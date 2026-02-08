#!/usr/bin/env python3
"""Test minimal Google GenAI image generation."""

import os
import sys
from google import genai
from google.genai import types

api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    print("GOOGLE_API_KEY not set")
    sys.exit(1)

client = genai.Client(api_key=api_key)
prompt = "A red geometric abstract illustration on white background, minimalist editorial style"

# --- Test 1: Imagen via generate_images ---
print("=== Test 1: imagen-4.0-generate-001 via generate_images ===")
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
        response.generated_images[0].image.save("test_imagen.png")
        print("OK -> test_imagen.png")
    else:
        print("Aucune image retournee")
except Exception as e:
    print(f"ERREUR: {e}")

# --- Test 2: Gemini via generate_content ---
print("\n=== Test 2: gemini-3-pro-image-preview via generate_content ===")
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
            with open("test_gemini.png", "wb") as f:
                f.write(part.inline_data.data)
            print("OK -> test_gemini.png")
            break
    else:
        print("Aucune image dans la reponse")
except Exception as e:
    print(f"ERREUR: {e}")
