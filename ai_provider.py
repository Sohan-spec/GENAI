# ai_provider.py
import os
from dotenv import load_dotenv

load_dotenv()

# Normalize provider selection (case-insensitive, accept common aliases)
_raw_provider = (os.getenv("AI_PROVIDER", "gemini") or "").strip().lower()
if _raw_provider in ("gemini", "gemini-pro", "gemini-1.5-pro", "gemini-flash", "gemini-1.5-flash", "flash", "google-gemini"):
    AI_PROVIDER = "gemini"
else:
    AI_PROVIDER = _raw_provider

# ----------------------
# Gemini (Google Generative AI)
# ----------------------
def call_gemini(prompt: str):
    try:
        import google.generativeai as genai

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("Missing GEMINI_API_KEY in .env")

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print("Gemini call failed:", e)
        return None


# ----------------------
# Lightweight local fallback (no external API)
# ----------------------
def _local_generate(idea_text: str, tags: list[str] | None = None):
    tags = tags or []
    idea = (idea_text or "").strip()
    tags_snippet = ", ".join(tags[:6]) if tags else "visual elements"

    # Story fallback uses both prompt and tags, aiming for ~120-160 words
    story_lines = [
        f"This painting draws on {tags_snippet} and the artist's intent: {idea}.",
        "The composition balances texture and light to suggest personal memory and place.",
        "Subtle contrasts and repeating motifs build a quiet rhythm, inviting the viewer to pause and look closer.",
        "Symbols are used sparingly: details emerge only after a second glance, leaving room for interpretation.",
        "It feels contemporary yet rooted in lived experience, aiming to be both intimate and open-ended.",
    ]
    story = "\n\n".join(story_lines)

    purpose = (
        "To offer a reflective, human moment—something calm, grounded, and honest. "
        "It is meant to be revisited, revealing new details over time."
    )

    artist = (
        "An emerging artist focused on everyday symbolism and atmosphere, "
        "combining observational detail with gentle abstraction."
    )

    return story, purpose, artist


# ----------------------
# Vision API helper (optional)
# ----------------------
def extract_image_tags(image_path: str):
    try:
        from google.cloud import vision
        client = vision.ImageAnnotatorClient()
        with open(image_path, "rb") as f:
            content = f.read()
        image = vision.Image(content=content)
        response = client.label_detection(image=image)
        labels = [label.description for label in response.label_annotations]
        return labels
    except Exception as e:
        print("Vision API failed:", e)
        return []


# ----------------------
# Prompt builders
# ----------------------
def build_prompt_from_tags(tags):
    return f"""
You are an AI helping artisans tell stories about their artwork.
The image seems to include: {", ".join(tags)}.

Write three sections separated by "---":
1. Story behind the art
2. Purpose of the art
3. About the artist
"""

def build_prompt_from_text(idea_text):
    return f"""
You are an AI helping artisans design unique artworks.

The artisan's idea is: "{idea_text}"

Create three sections separated by "---":
1. Story behind the art
2. Purpose of the art
3. About the artist
"""


# ----------------------
# Public functions
# ----------------------
def generate_from_image(image_path: str):
    tags = extract_image_tags(image_path)
    prompt = build_prompt_from_tags(tags)
    out = call_gemini(prompt) if AI_PROVIDER == "gemini" else None

    if out:
        parts = out.split('---')
        story = parts[0].strip() if len(parts) > 0 else out
        purpose = parts[1].strip() if len(parts) > 1 else ""
        artist = parts[2].strip() if len(parts) > 2 else ""
    else:
        print("Using local fallback generation (image)")
        story, purpose, artist = _local_generate("", tags)
    return story, purpose, artist


def generate_from_text(idea_text: str):
    prompt = build_prompt_from_text(idea_text)
    out = call_gemini(prompt) if AI_PROVIDER == "gemini" else None

    if out:
        parts = out.split('---')
        story = parts[0].strip() if len(parts) > 0 else out
        purpose = parts[1].strip() if len(parts) > 1 else ""
        artist = parts[2].strip() if len(parts) > 2 else ""
    else:
        print("Using local fallback generation (text)")
        story, purpose, artist = _local_generate(idea_text, [])
    return story, purpose, artist


def generate_from_image_and_text(image_path: str, idea_text: str):
    tags = extract_image_tags(image_path)
    # Combine tags and artisan prompt into one richer prompt
    prompt = f"""
You are an AI helping artisans tell stories about their artwork.

Detected elements in the image: {", ".join(tags)}.
Artisan prompt: "{idea_text}"

Write three sections separated by "---":
1. Story behind the art that uses both the visual tags and the artisan's prompt
2. Purpose of the art
3. About the artist
"""
    out = call_gemini(prompt) if AI_PROVIDER == "gemini" else None

    if out:
        parts = out.split('---')
        story = parts[0].strip() if len(parts) > 0 else out
        purpose = parts[1].strip() if len(parts) > 1 else ""
        artist = parts[2].strip() if len(parts) > 2 else ""
    else:
        print("Using local fallback generation (image+text)")
        story, purpose, artist = _local_generate(idea_text, tags)
    return story, purpose, artist
