"""
AI-Stylo Firebase Cloud Functions (Python 3.12)
================================================
Core Pipeline: Image → Gemini Vision → Embedding → Firestore Vector Search → Recommendation

PEAR Pipeline:
  Perceive  → Gemini Vision analyzes the outfit photo
  Enrich    → Text embedding captures semantic style
  Adapt     → Firestore Vector Search finds catalog matches
  Reflect   → Gemini generates a personalized recommendation

Endpoints:
  POST /analyze_and_recommend  — Main pipeline: base64 image → style advice + catalog matches
  GET  /get_catalog             — List catalog items (paginated)
  GET  /get_style_dna           — Get user's Style DNA from Firestore
  POST /save_outfit             — Save a generated outfit

FIRESTORE COLLECTIONS:
  catalog/                — items with: embedding (vector), name, brand, category, color, price, image_url, tags[]
  style_dna/              — user style profiles
  saved_outfits/          — saved looks
  recommendation_history/ — analysis logs per user

SETUP:
  Set env vars: GEMINI_API_KEY=your-key  [required]
                OPENAI_API_KEY=your-key  [optional, takes priority]
"""

import json
import os
import random

import google.generativeai as genai
from firebase_admin import firestore, initialize_app
from firebase_functions import https_fn, options
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
from google.cloud.firestore_v1.vector import Vector

try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

# ── Firebase Init ──────────────────────────────────────────────────────────────
initialize_app()

# ── AI Init ───────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

VISION_MODEL    = "gemini-2.0-flash"
EMBED_MODEL     = "models/gemini-embedding-001"
OPENAI_VISION   = "gpt-4o-mini"
OPENAI_EMBED    = "text-embedding-3-small"
EMBED_DIM       = 768

CORS = options.CorsOptions(cors_origins="*", cors_methods=["GET", "POST", "OPTIONS"])

# ── CORS Response Helper ───────────────────────────────────────────────────────
_CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}

def cors_ok(data: dict, status: int = 200) -> https_fn.Response:
    """Return a CORS-compliant JSON success/error response."""
    return https_fn.Response(
        json.dumps(data, ensure_ascii=False),
        status=status,
        headers=_CORS_HEADERS,
        mimetype="application/json",
    )

def cors_preflight() -> https_fn.Response:
    """Return a CORS pre-flight (OPTIONS) acknowledgment."""
    return https_fn.Response("", status=204, headers=_CORS_HEADERS)


# ── PEAR Stage 1: Perceive ────────────────────────────────────────────────────
def get_style_description(image_b64: str, mime_type: str = "image/jpeg") -> dict:
    """
    [P]erceive — Gemini Vision analyzes a clothing image.
    Returns a structured dict of style attributes.
    """
    model = genai.GenerativeModel(VISION_MODEL)
    prompt = (
        "You are an expert fashion analyst. Analyze this clothing/outfit image and return "
        "ONLY a JSON object with these exact fields:\n"
        "{\n"
        '  "style_description": "concise overall style description",\n'
        '  "colors": ["list", "of", "dominant", "colors"],\n'
        '  "category": "one of: tops, bottoms, dresses, outerwear, footwear, accessories, full_outfit",\n'
        '  "fit": "e.g., oversized, slim, regular, cropped",\n'
        '  "occasion": "e.g., casual, formal, sport, evening, business",\n'
        '  "season": "e.g., spring/summer, fall/winter, all-season",\n'
        '  "style_tags": ["up", "to", "8", "descriptive", "tags"],\n'
        '  "embedding_text": "A rich text combining all attributes for semantic search"\n'
        "}\n"
        "Return ONLY the JSON — no markdown, no explanation."
    )
    image_part = {"mime_type": mime_type, "data": image_b64}
    response = model.generate_content([prompt, image_part])

    try:
        raw = response.text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception as e:
        return {
            "style_description": response.text[:300],
            "embedding_text": response.text[:500],
            "parse_error": str(e),
        }


# ── PEAR Stage 2: Enrich ──────────────────────────────────────────────────────
def embed_text(text: str) -> list[float]:
    """
    [E]nrich — Generate a semantic text embedding (768-D).
    Priority: OpenAI → Gemini → random mock.
    """
    if OPENAI_API_KEY and HAS_OPENAI:
        try:
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            res = client.embeddings.create(
                input=text, model=OPENAI_EMBED, dimensions=EMBED_DIM
            )
            return res.data[0].embedding
        except Exception:
            pass  # Fall through to Gemini

    if GEMINI_API_KEY:
        try:
            result = genai.embed_content(
                model=EMBED_MODEL,
                content=text,
                task_type="retrieval_query",
                output_dimensionality=EMBED_DIM,
            )
            return result["embedding"]
        except Exception:
            pass  # Fall through to mock

    return [random.uniform(-1.0, 1.0) for _ in range(EMBED_DIM)]


# ── PEAR Stage 3: Adapt (Vector Search) ───────────────────────────────────────
def vector_search_catalog(db, query_vector: list[float], top_k: int = 5) -> list[dict]:
    """
    [A]dapt — Firestore Vector Search on the catalog collection.
    Requires a vector index on 'embedding' (dim=768, COSINE).
    """
    collection = db.collection("catalog")
    vector_query = collection.find_nearest(
        vector_field="embedding",
        query_vector=Vector(query_vector),
        distance_measure=DistanceMeasure.COSINE,
        limit=top_k,
    )
    results = []
    for doc in vector_query.stream():
        data = doc.to_dict()
        data.pop("embedding", None)       # Never send raw vector to client
        data.pop("embed_text", None)      # Strip internal fields
        results.append({"id": doc.id, **data})
    return results


# ── PEAR Stage 4: Reflect (AI Recommendation) ─────────────────────────────────
def generate_recommendation(style_analysis: dict, matches: list[dict]) -> str:
    """
    [R]eflect — AI writes a warm, personalized style recommendation.
    """
    matches_text = "\n".join([
        f"- {m.get('name', 'Item')} by {m.get('brand', 'Unknown')}: "
        f"{m.get('category', '')} in {m.get('color', '')} — ${m.get('price', '?')}"
        for m in matches[:5]
    ])

    prompt = (
        "You are AI-Stylo, a personal AI fashion advisor with a warm, inspiring, expert tone.\n\n"
        f"The user's style profile:\n"
        f"- Style: {style_analysis.get('style_description', 'unknown')}\n"
        f"- Colors: {', '.join(style_analysis.get('colors', []))}\n"
        f"- Occasion: {style_analysis.get('occasion', 'casual')}\n"
        f"- Tags: {', '.join(style_analysis.get('style_tags', []))}\n\n"
        f"Matched catalog items:\n{matches_text}\n\n"
        "Write a warm, personalized 2-3 sentence recommendation:\n"
        "1. What you noticed about their style\n"
        "2. Why these items complement it\n"
        "3. One specific styling tip\n\n"
        "Flowing prose. No bullet points. Be specific and inspiring."
    )

    if OPENAI_API_KEY and HAS_OPENAI:
        try:
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            res = client.chat.completions.create(
                model=OPENAI_VISION,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
            )
            return res.choices[0].message.content.strip()
        except Exception:
            pass

    if GEMINI_API_KEY:
        try:
            model = genai.GenerativeModel(VISION_MODEL)
            return model.generate_content(prompt).text.strip()
        except Exception:
            pass

    return "Your style selection speaks for itself — each piece complements the other with effortless sophistication."


# ── Endpoint: POST /analyze_and_recommend ─────────────────────────────────────
@https_fn.on_request(cors=CORS)
def analyze_and_recommend(req: https_fn.Request) -> https_fn.Response:
    """
    Full PEAR pipeline:
    Body: { "image_b64": "<base64>", "mime_type": "image/jpeg", "user_id": "optional" }
    Returns: { "style_analysis": {...}, "matches": [...], "recommendation": "..." }
    """
    if req.method == "OPTIONS":
        return cors_preflight()

    if not GEMINI_API_KEY and not OPENAI_API_KEY:
        return cors_ok({"error": "No AI API key configured (GEMINI_API_KEY or OPENAI_API_KEY)"}, 500)

    try:
        body = req.get_json(silent=True) or {}
        image_b64 = body.get("image_b64")
        mime_type = body.get("mime_type", "image/jpeg")

        if not image_b64:
            return cors_ok({"error": "image_b64 is required"}, 400)

        # ── P: Perceive
        style_analysis = get_style_description(image_b64, mime_type)

        # ── E: Enrich
        embed_input = (
            style_analysis.get("embedding_text")
            or style_analysis.get("style_description")
            or "fashion item"
        )
        query_vector = embed_text(embed_input)

        # ── A: Adapt
        db = firestore.client()
        matches = vector_search_catalog(db, query_vector, top_k=5)

        # ── R: Reflect
        recommendation = generate_recommendation(style_analysis, matches)

        # Optional: log for user history
        user_id = body.get("user_id")
        if user_id and matches:
            db.collection("recommendation_history").add({
                "user_id": user_id,
                "style_analysis": style_analysis,
                "matches": [m["id"] for m in matches],
                "recommendation": recommendation,
                "timestamp": firestore.SERVER_TIMESTAMP,
            })

        return cors_ok({
            "style_analysis": style_analysis,
            "matches": matches,
            "recommendation": recommendation,
        })

    except Exception as e:
        return cors_ok({"error": str(e)}, 500)


# ── Endpoint: GET /get_catalog ─────────────────────────────────────────────────
@https_fn.on_request(cors=CORS)
def get_catalog(req: https_fn.Request) -> https_fn.Response:
    """Returns catalog items paginated (without embedding vectors)."""
    if req.method == "OPTIONS":
        return cors_preflight()
    try:
        db = firestore.client()
        limit = min(int(req.args.get("limit", 50)), 200)  # Cap at 200
        docs = db.collection("catalog").limit(limit).stream()
        items = []
        for doc in docs:
            data = doc.to_dict()
            data.pop("embedding", None)
            data.pop("embed_text", None)
            items.append({"id": doc.id, **data})
        return cors_ok({"items": items, "count": len(items)})
    except Exception as e:
        return cors_ok({"error": str(e)}, 500)


# ── Endpoint: GET /get_style_dna ───────────────────────────────────────────────
@https_fn.on_request(cors=CORS)
def get_style_dna(req: https_fn.Request) -> https_fn.Response:
    """Returns a user's Style DNA profile from Firestore."""
    if req.method == "OPTIONS":
        return cors_preflight()
    user_id = req.args.get("user_id")
    if not user_id:
        return cors_ok({"error": "user_id query param is required"}, 400)
    try:
        db = firestore.client()
        doc = db.collection("style_dna").document(user_id).get()
        if not doc.exists:
            return cors_ok({"error": f"No Style DNA found for user '{user_id}'"}, 404)
        return cors_ok(doc.to_dict())
    except Exception as e:
        return cors_ok({"error": str(e)}, 500)


# ── Endpoint: POST /save_outfit ────────────────────────────────────────────────
@https_fn.on_request(cors=CORS)
def save_outfit(req: https_fn.Request) -> https_fn.Response:
    """Saves a generated outfit for a user."""
    if req.method == "OPTIONS":
        return cors_preflight()
    try:
        data = req.get_json(silent=True) or {}
        user_id = data.get("user_id")
        outfit = data.get("outfit")
        if not user_id or not outfit:
            return cors_ok({"error": "Both user_id and outfit fields are required"}, 400)
        db = firestore.client()
        db.collection("saved_outfits").add({
            "user_id": user_id,
            "outfit": outfit,
            "timestamp": firestore.SERVER_TIMESTAMP,
        })
        return cors_ok({"status": "saved"})
    except Exception as e:
        return cors_ok({"error": str(e)}, 500)


# ── Endpoint: POST /stylescape/design_collection ───────────────────────────────
@https_fn.on_request(cors=CORS)
def stylescape_design_collection(req: https_fn.Request) -> https_fn.Response:
    """
    AI-Designer: Co-create a collection.
    Receives user vibe/idea, generates a detailed prompt for image generation,
    and saves the 'blueprint' to Firestore user_designs.
    """
    if req.method == "OPTIONS":
        return cors_preflight()
    try:
        body = req.get_json(silent=True) or {}
        user_id = body.get("user_id")
        user_idea = body.get("idea", "A futuristic casual look")

        if not user_id:
            return cors_ok({"error": "user_id is required"}, 400)

        # Generate a detailed prompt for the image generator
        prompt = (
            "You are an expert fashion designer collaborating with a client. "
            f"Their raw idea: '{user_idea}'.\n"
            "Create a highly detailed, professional prompt for an AI image generator to visualize this look. "
            "Include details about fabrics, cut, lighting, mood, and color palette. "
            "Keep it under 80 words."
        )

        model = genai.GenerativeModel(VISION_MODEL)
        detailed_prompt = model.generate_content(prompt).text.strip()

        # Generate a cool capsule name
        name_prompt = f"Give a catchy 2-4 word name for this fashion capsule concept: {detailed_prompt}"
        capsule_name = model.generate_content(name_prompt).text.strip().replace('"', '')

        # Save to Firestore
        db = firestore.client()
        design_data = {
            "user_id": user_id,
            "original_idea": user_idea,
            "ai_prompt": detailed_prompt,
            "capsule_name": capsule_name,
            "timestamp": firestore.SERVER_TIMESTAMP,
            "status": "blueprint"
        }
        doc_ref = db.collection("user_designs").add(design_data)[1]

        return cors_ok({
            "design_id": doc_ref.id,
            "capsule_name": capsule_name,
            "generation_prompt": detailed_prompt,
            "message": "AI Designer has prepared your blueprint. Ready for visualization."
        })

    except Exception as e:
        return cors_ok({"error": str(e)}, 500)


# ── Endpoint: POST /stylescape/checkout_generated_look ─────────────────────────
@https_fn.on_request(cors=CORS)
def stylescape_checkout_generated_look(req: https_fn.Request) -> https_fn.Response:
    """
    Real-world Checkout: Bridges AI-generated image with real products in catalog.
    Takes the generated photo and returns an 'add to cart' manifest.
    """
    if req.method == "OPTIONS":
        return cors_preflight()
    try:
        body = req.get_json(silent=True) or {}
        image_b64 = body.get("image_b64")
        mime_type = body.get("mime_type", "image/jpeg")

        if not image_b64:
            return cors_ok({"error": "image_b64 is required. Provide the generated look."}, 400)

        # 1. P: Analyze the generated image
        style_analysis = get_style_description(image_b64, mime_type)

        # 2. E & A: Find closest real catalog items
        embed_input = style_analysis.get("embedding_text", style_analysis.get("style_description", "fashion item"))
        query_vector = embed_text(embed_input)
        
        db = firestore.client()
        real_matches = vector_search_catalog(db, query_vector, top_k=3)

        # Calculate total estimated cart
        total_price = sum(float(item.get("price", 0)) for item in real_matches if str(item.get("price", 0)).replace('.', '', 1).isdigit())

        return cors_ok({
            "generated_style": style_analysis.get("style_description"),
            "buy_manifest": real_matches,
            "estimated_cart_total": total_price,
            "message": "Dreams to Reality: Here are the closest real items to your AI-generated look."
        })

    except Exception as e:
        return cors_ok({"error": str(e)}, 500)

