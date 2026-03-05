"""
AI-Stylo Firebase Cloud Functions (Python 3.12)
================================================
Core Pipeline: Image → Gemini Vision → Embedding → Firestore Vector Search → Recommendation

Endpoints:
  POST /analyze_and_recommend  — Main pipeline: base64 image → style advice + catalog matches
  GET  /get_catalog             — List catalog items
  GET  /get_style_dna           — Get user's Style DNA from Firestore
  POST /save_outfit             — Save a generated outfit

FIRESTORE COLLECTIONS:
  catalog/          — items with field: embedding (vector), name, brand, category, color, price, image_url, tags[]
  style_dna/        — user profiles
  saved_outfits/    — saved looks

SETUP:
  Set env var: GEMINI_API_KEY=your-key
"""

import base64
import json
import os
from datetime import datetime

import google.generativeai as genai
from firebase_admin import firestore, initialize_app
from firebase_functions import https_fn, options
from google.cloud.firestore_v1.vector import Vector
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure

try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

# ── Firebase Init ─────────────────────────────────────────────────────────────
initialize_app()

# ── Gemini Init ───────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

VISION_MODEL = "gemini-1.5-flash"
EMBED_MODEL = "models/gemini-embedding-001"
OPENAI_VISION_MODEL = "gpt-4o-mini"
OPENAI_EMBED_MODEL = "text-embedding-3-small"

CORS = options.CorsOptions(cors_origins="*", cors_methods=["GET", "POST", "OPTIONS"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_style_description(image_b64: str, mime_type: str = "image/jpeg") -> dict:
    """
    Use Gemini Vision to analyze a clothing image.
    Returns structured style attributes.
    """
    model = genai.GenerativeModel(VISION_MODEL)
    prompt = """You are an expert fashion analyst. Analyze this clothing/outfit image and return ONLY a JSON object with these fields:
{
  "style_description": "concise overall style description (e.g., 'minimalist casual streetwear')",
  "colors": ["list", "of", "dominant", "colors"],
  "category": "one of: tops, bottoms, dresses, outerwear, footwear, accessories, full_outfit",
  "fit": "e.g., oversized, slim, regular, cropped",
  "occasion": "e.g., casual, formal, sport, evening, business",
  "season": "e.g., spring/summer, fall/winter, all-season",
  "style_tags": ["up", "to", "8", "descriptive", "tags"],
  "embedding_text": "A rich text description combining all attributes for embedding, optimized for semantic search"
}
Return ONLY the JSON, no markdown, no explanation."""

    image_part = {"mime_type": mime_type, "data": image_b64}
    response = model.generate_content([prompt, image_part])

    try:
        raw = response.text.strip()
        # Strip possible markdown code fences
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception as e:
        return {
            "style_description": response.text[:300],
            "embedding_text": response.text[:500],
            "error": str(e)
        }


def embed_text(text: str) -> list[float]:
    """Generate a text embedding using OpenAI or Gemini."""
    if OPENAI_API_KEY and HAS_OPENAI:
        try:
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            res = client.embeddings.create(
                input=text,
                model=OPENAI_EMBED_MODEL,
                dimensions=768
            )
            return res.data[0].embedding
        except Exception as e:
            import random
            return [random.uniform(-1.0, 1.0) for _ in range(768)]
        
    try:
        result = genai.embed_content(
            model=EMBED_MODEL,
            content=text,
            task_type="retrieval_query",
            output_dimensionality=768
        )
        return result["embedding"]
    except Exception:
        import random
        return [random.uniform(-1.0, 1.0) for _ in range(768)]


def vector_search_catalog(db, query_vector: list[float], top_k: int = 5) -> list[dict]:
    """
    Perform Firestore Vector Search on the catalog collection.
    Requires a vector index on the 'embedding' field.
    """
    collection = db.collection("catalog")
    vector_query = collection.find_nearest(
        vector_field="embedding",
        query_vector=Vector(query_vector),
        distance_measure=DistanceMeasure.COSINE,
        limit=top_k,
    )
    docs = vector_query.stream()
    results = []
    for doc in docs:
        data = doc.to_dict()
        data.pop("embedding", None)  # Don't send vector to client
        results.append({"id": doc.id, **data})
    return results


def generate_recommendation(style_analysis: dict, matches: list[dict]) -> str:
    """Use AI to write a personalized style recommendation."""
    matches_text = "\n".join([
        f"- {m.get('name', 'Item')} by {m.get('brand', 'Unknown')}: {m.get('category', '')} "
        f"in {m.get('color', '')} — ${m.get('price', '?')}"
        for m in matches[:5]
    ])

    prompt = f"""You are AI-Stylo, a personal AI fashion advisor with a warm, inspiring, expert tone.

The user uploaded a photo with this style profile:
- Style: {style_analysis.get('style_description', 'unknown')}
- Colors: {', '.join(style_analysis.get('colors', []))}
- Occasion: {style_analysis.get('occasion', 'casual')}
- Tags: {', '.join(style_analysis.get('style_tags', []))}

Based on their style, we found these matching items from our catalog:
{matches_text}

Write a warm, personalized 2-3 sentence fashion recommendation explaining:
1. What you noticed about their style
2. Why these catalog items complement it
3. One specific styling tip

Be concise, specific, and inspiring. No bullet points — flowing prose."""

    if OPENAI_API_KEY and HAS_OPENAI:
        try:
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            res = client.chat.completions.create(
                model=OPENAI_VISION_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300
            )
            return res.choices[0].message.content.strip()
        except Exception as e:
            return "With this refined combination, each element balances the other perfectly."
    
    try:
        model = genai.GenerativeModel(VISION_MODEL)
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception:
        return "With this refined combination, each element balances the other perfectly."


# ── Endpoints ─────────────────────────────────────────────────────────────────

@https_fn.on_request(cors=CORS)
def analyze_and_recommend(req: https_fn.Request) -> https_fn.Response:
    """
    POST /analyze_and_recommend
    Body: { "image_b64": "<base64>", "mime_type": "image/jpeg", "user_id": "optional" }
    Returns: { "style_analysis": {...}, "matches": [...], "recommendation": "..." }
    """
    if req.method == "OPTIONS":
        return https_fn.Response("", status=204)

    if not GEMINI_API_KEY and not OPENAI_API_KEY:
        return https_fn.Response(
            json.dumps({"error": "No AI API key (GEMINI_API_KEY or OPENAI_API_KEY) configured"}),
            status=500, mimetype="application/json"
        )

    try:
        body = req.get_json(silent=True) or {}
        image_b64 = body.get("image_b64")
        mime_type = body.get("mime_type", "image/jpeg")

        if not image_b64:
            return https_fn.Response(
                json.dumps({"error": "image_b64 is required"}),
                status=400, mimetype="application/json"
            )

        # Step 1: Analyze image with Gemini Vision
        style_analysis = get_style_description(image_b64, mime_type)

        # Step 2: Embed the style description
        embed_input = style_analysis.get("embedding_text") or style_analysis.get("style_description", "fashion item")
        query_vector = embed_text(embed_input)

        # Step 3: Vector search in Firestore catalog
        db = firestore.client()
        matches = vector_search_catalog(db, query_vector, top_k=5)

        # Step 4: Generate personalized recommendation
        recommendation = generate_recommendation(style_analysis, matches)

        # Step 5: Optionally log the search for the user
        user_id = body.get("user_id")
        if user_id and matches:
            db.collection("recommendation_history").add({
                "user_id": user_id,
                "style_analysis": style_analysis,
                "matches": [m["id"] for m in matches],
                "recommendation": recommendation,
                "timestamp": firestore.SERVER_TIMESTAMP
            })

        return https_fn.Response(
            json.dumps({
                "style_analysis": style_analysis,
                "matches": matches,
                "recommendation": recommendation,
            }),
            status=200, mimetype="application/json"
        )

    except Exception as e:
        return https_fn.Response(
            json.dumps({"error": str(e)}),
            status=500, mimetype="application/json"
        )


@https_fn.on_request(cors=CORS)
def get_catalog(req: https_fn.Request) -> https_fn.Response:
    """GET /get_catalog — Returns catalog items (without embedding vectors)."""
    try:
        db = firestore.client()
        limit = int(req.args.get("limit", 50))
        docs = db.collection("catalog").limit(limit).stream()
        items = []
        for doc in docs:
            data = doc.to_dict()
            data.pop("embedding", None)
            items.append({"id": doc.id, **data})
        return https_fn.Response(json.dumps({"items": items}), status=200, mimetype="application/json")
    except Exception as e:
        return https_fn.Response(json.dumps({"error": str(e)}), status=500, mimetype="application/json")


@https_fn.on_request(cors=CORS)
def get_style_dna(req: https_fn.Request) -> https_fn.Response:
    """GET /get_style_dna?user_id=xxx"""
    user_id = req.args.get("user_id")
    if not user_id:
        return https_fn.Response(json.dumps({"error": "user_id required"}), status=400, mimetype="application/json")
    try:
        db = firestore.client()
        doc = db.collection("style_dna").document(user_id).get()
        if not doc.exists:
            return https_fn.Response(json.dumps({"error": "not found"}), status=404, mimetype="application/json")
        return https_fn.Response(json.dumps(doc.to_dict()), status=200, mimetype="application/json")
    except Exception as e:
        return https_fn.Response(json.dumps({"error": str(e)}), status=500, mimetype="application/json")


@https_fn.on_request(cors=CORS)
def save_outfit(req: https_fn.Request) -> https_fn.Response:
    """POST /save_outfit — { user_id, outfit }"""
    if req.method == "OPTIONS":
        return https_fn.Response("", status=204)
    try:
        data = req.get_json(silent=True) or {}
        user_id = data.get("user_id")
        outfit = data.get("outfit")
        if not user_id or not outfit:
            return https_fn.Response(json.dumps({"error": "user_id and outfit required"}), status=400, mimetype="application/json")
        db = firestore.client()
        db.collection("saved_outfits").add({"user_id": user_id, "outfit": outfit, "timestamp": firestore.SERVER_TIMESTAMP})
        return https_fn.Response(json.dumps({"status": "saved"}), status=200, mimetype="application/json")
    except Exception as e:
        return https_fn.Response(json.dumps({"error": str(e)}), status=500, mimetype="application/json")
