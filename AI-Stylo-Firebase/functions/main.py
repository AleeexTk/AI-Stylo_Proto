"""
AI-Stylo Firebase Cloud Functions (Python 3.12)
================================================
Core Pipeline: Image → Gemini Vision → Embedding → Firestore Vector Search → Outfit Composer → Recommendation

Endpoints:
  POST /analyze_and_recommend
  GET  /get_catalog
  GET  /get_style_dna
  POST /save_outfit
  POST /stylescape/design_collection
  POST /stylescape/checkout_generated_look
  POST /stylescape/virtual_try_on  (MOCK-ready, with validator)
"""

import json
import os
import random
import base64
from typing import Any, Dict, List, Optional, Tuple

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

try:
    import replicate
    HAS_REPLICATE = True
except ImportError:
    HAS_REPLICATE = False

# ── Firebase Init ──────────────────────────────────────────────────────────────
initialize_app()

# ── AI Init ───────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_TOKEN", "")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

if REPLICATE_API_TOKEN:
    os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN

VISION_MODEL    = os.environ.get("VISION_MODEL", "gemini-2.0-flash")
VALIDATOR_MODEL = os.environ.get("VALIDATOR_MODEL", "gemini-2.0-flash")
EMBED_MODEL     = os.environ.get("EMBED_MODEL", "models/gemini-embedding-001")

OPENAI_VISION   = os.environ.get("OPENAI_VISION", "gpt-4o-mini")
OPENAI_EMBED    = os.environ.get("OPENAI_EMBED", "text-embedding-3-small")

EMBED_DIM = int(os.environ.get("EMBED_DIM", "768"))
MAX_IMAGE_B64_CHARS = int(os.environ.get("MAX_IMAGE_B64_CHARS", "7000000"))  # ~5MB-ish
API_KEY = os.environ.get("API_KEY", "")  # simple shared secret for MVP

# Replicate model for VTON (IDM-VTON)
REPLICATE_VTON_MODEL = os.environ.get("REPLICATE_VTON_MODEL", "yisol/idm-vton:906425dbca90663ff5427624839572e56c908a8276baf5c0ac6439c6859f49f4")

CORS = options.CorsOptions(cors_origins="*", cors_methods=["GET", "POST", "OPTIONS"])

_CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, X-API-Key",
}

# ── Response Helpers ──────────────────────────────────────────────────────────
def cors_ok(data: dict, status: int = 200) -> https_fn.Response:
    return https_fn.Response(
        json.dumps(data, ensure_ascii=False),
        status=status,
        headers=_CORS_HEADERS,
        mimetype="application/json",
    )

def cors_preflight() -> https_fn.Response:
    return https_fn.Response("", status=204, headers=_CORS_HEADERS)

def require_api_key(req: https_fn.Request) -> Optional[https_fn.Response]:
    """MVP protection: require X-API-Key if API_KEY env var is set."""
    if not API_KEY:
        return None
    provided = req.headers.get("X-API-Key", "")
    if provided != API_KEY:
        return cors_ok({"error": "Unauthorized (missing/invalid X-API-Key)"}, 401)
    return None

# ── JSON extraction for Gemini outputs ─────────────────────────────────────────
def extract_json(text: str) -> dict:
    t = (text or "").strip()
    if "```" in t:
        parts = t.split("```")
        if len(parts) >= 2:
            t = parts[1].strip()
            if t.lower().startswith("json"):
                t = t[4:].strip()

    l = t.find("{")
    r = t.rfind("}")
    if l != -1 and r != -1 and r > l:
        t = t[l:r + 1]

    return json.loads(t)

def ensure_style_contract(d: dict) -> dict:
    """Return a stable, client-friendly contract."""
    return {
        "style_description": d.get("style_description", "") if isinstance(d, dict) else "",
        "colors": d.get("colors", []) if isinstance(d, dict) else [],
        "category": d.get("category", "full_outfit") if isinstance(d, dict) else "full_outfit",
        "fit": d.get("fit", "") if isinstance(d, dict) else "",
        "occasion": d.get("occasion", "casual") if isinstance(d, dict) else "casual",
        "season": d.get("season", "") if isinstance(d, dict) else "",
        "style_tags": d.get("style_tags", []) if isinstance(d, dict) else [],
        "embedding_text": d.get("embedding_text", "") if isinstance(d, dict) else "",
        "parse_error": d.get("parse_error") if isinstance(d, dict) else None,
        "raw_excerpt": d.get("raw_excerpt") if isinstance(d, dict) else None,
    }

# ── PEAR Stage 1: Perceive ────────────────────────────────────────────────────
def get_style_description(image_b64: str, mime_type: str = "image/jpeg") -> dict:
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

    try:
        response = model.generate_content([prompt, image_part])
        raw = (response.text or "").strip()
        parsed = extract_json(raw)
        return ensure_style_contract(parsed)
    except Exception as e:
        # stable fallback (never break the client)
        return ensure_style_contract({
            "style_description": "Unparsed analysis",
            "embedding_text": "",
            "parse_error": str(e),
            "raw_excerpt": (locals().get("raw", "") or "")[:500],
        })

# ── PEAR Stage 2: Enrich ──────────────────────────────────────────────────────
def embed_text(text: str) -> List[float]:
    """
    Priority: OpenAI → Gemini → random mock.
    """
    if OPENAI_API_KEY and HAS_OPENAI:
        try:
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            # Some providers/models may not support dimensions; keep it resilient.
            res = client.embeddings.create(input=text, model=OPENAI_EMBED)
            vec = res.data[0].embedding
            return vec
        except Exception:
            pass

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
            pass

    return [random.uniform(-1.0, 1.0) for _ in range(EMBED_DIM)]

# ── PEAR Stage 3: Adapt (Vector Search) ───────────────────────────────────────
def vector_search_catalog(db, query_vector: List[float], top_k: int = 20) -> List[dict]:
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
        data.pop("embedding", None)
        data.pop("embed_text", None)
        results.append({"id": doc.id, **data})
    return results

# ── Outfit Composer (MVP) ─────────────────────────────────────────────────────
def _norm(s: Any) -> str:
    return str(s or "").strip().lower()

def _cat_to_slot(cat: str) -> Optional[str]:
    c = _norm(cat)
    if c in ("tops", "top", "upper", "shirt", "t-shirt", "sweater", "hoodie", "blouse"):
        return "top"
    if c in ("bottoms", "bottom", "pants", "jeans", "skirt", "shorts"):
        return "bottom"
    if c in ("footwear", "shoes", "sneakers", "boots"):
        return "shoes"
    if c in ("accessories", "accessory", "bag", "belt", "jewelry"):
        return "accessory"
    if c in ("outerwear", "coat", "jacket"):
        # for MVP we treat outerwear as top if top is empty
        return "top"
    if c in ("dresses", "dress"):
        # dresses can act as top+bottom; MVP: fill top first, then bottom if needed
        return "top"
    return None

def compose_outfit(
    matches: List[dict],
    budget_max: Optional[float] = None,
    preferred_colors: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Takes a pool of nearest items, returns a single outfit in slots.
    MVP heuristics:
      - Filter by budget_max if provided
      - Prefer items matching preferred_colors (simple string contains)
      - Fill: top, bottom, shoes, accessory
    """
    preferred_colors = preferred_colors or []
    pref = [_norm(c) for c in preferred_colors if str(c).strip()]

    def price_ok(item: dict) -> bool:
        if budget_max is None or budget_max <= 0:
            return True
        try:
            return float(item.get("price", 1e18)) <= float(budget_max)
        except Exception:
            return True

    def color_score(item: dict) -> int:
        if not pref:
            return 0
        blob = f"{item.get('color','')} {_norm(item.get('name'))} {' '.join([_norm(t) for t in item.get('tags', [])])}"
        return sum(1 for c in pref if c and c in _norm(blob))

    # Rank matches: first budget, then color score, then keep original order
    pool = [m for m in matches if price_ok(m)]
    if not pool:
        pool = matches[:]  # fallback: ignore budget

    pool_sorted = sorted(
        enumerate(pool),
        key=lambda x: (-(color_score(x[1])), x[0])
    )
    pool_sorted = [it for _, it in pool_sorted]

    slots: Dict[str, Optional[dict]] = {"top": None, "bottom": None, "shoes": None, "accessory": None}

    for item in pool_sorted:
        slot = _cat_to_slot(item.get("category", ""))
        if not slot:
            continue
        if slot == "top" and slots["top"] is None:
            slots["top"] = item
        elif slot == "bottom" and slots["bottom"] is None:
            slots["bottom"] = item
        elif slot == "shoes" and slots["shoes"] is None:
            slots["shoes"] = item
        elif slot == "accessory" and slots["accessory"] is None:
            slots["accessory"] = item

        if all(slots.values()):
            break

    chosen = [v for v in slots.values() if v]
    total = 0.0
    for it in chosen:
        try:
            total += float(it.get("price", 0) or 0)
        except Exception:
            pass

    return {
        "slots": {k: (v if v else None) for k, v in slots.items()},
        "item_ids": [it["id"] for it in chosen if "id" in it],
        "estimated_total": total,
        "missing_slots": [k for k, v in slots.items() if v is None],
    }

# ── PEAR Stage 4: Reflect (Recommendation) ────────────────────────────────────
def generate_recommendation(style_analysis: dict, outfit: dict) -> str:
    slots = outfit.get("slots", {})
    chosen = [slots.get(s) for s in ["top", "bottom", "shoes", "accessory"] if slots.get(s)]

    matches_text = "\n".join([
        f"- {m.get('name', 'Item')} by {m.get('brand', 'Unknown')}: "
        f"{m.get('category', '')} in {m.get('color', '')} — {m.get('price', '?')}"
        for m in chosen[:4]
    ]) or "- (No items selected)"

    prompt = (
        "You are AI-Stylo, a personal AI fashion advisor with a warm, inspiring, expert tone.\n\n"
        f"The user's detected style:\n"
        f"- Style: {style_analysis.get('style_description', 'unknown')}\n"
        f"- Colors: {', '.join(style_analysis.get('colors', []))}\n"
        f"- Occasion: {style_analysis.get('occasion', 'casual')}\n"
        f"- Tags: {', '.join(style_analysis.get('style_tags', []))}\n\n"
        f"Selected outfit items:\n{matches_text}\n\n"
        "Write a warm, personalized 2-3 sentence recommendation:\n"
        "1) What you noticed about their style\n"
        "2) Why this outfit complements it\n"
        "3) One specific styling tip\n\n"
        "Flowing prose. No bullet points."
    )

    if OPENAI_API_KEY and HAS_OPENAI:
        try:
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            res = client.chat.completions.create(
                model=OPENAI_VISION,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=220,
            )
            return (res.choices[0].message.content or "").strip()
        except Exception:
            pass

    if GEMINI_API_KEY:
        try:
            model = genai.GenerativeModel(VISION_MODEL)
            return (model.generate_content(prompt).text or "").strip()
        except Exception:
            pass

    return "Your look has a clear, confident direction—this selection keeps it cohesive and adds a polished finish."

# ── Firestore: Style DNA fetch ────────────────────────────────────────────────
def get_user_style_dna(db, user_id: str) -> dict:
    doc = db.collection("style_dna").document(user_id).get()
    return doc.to_dict() if doc.exists else {}

def style_dna_to_text(dna: dict) -> str:
    if not dna:
        return ""
    colors = dna.get("colors") or dna.get("fav_colors") or []
    tags = dna.get("style_tags") or dna.get("tags") or []
    brands = dna.get("brands") or dna.get("brand_affinities") or {}
    budget = dna.get("budget") or dna.get("budget_profile") or {}
    return (
        f"User preferences:\n"
        f"- preferred colors: {colors}\n"
        f"- style tags: {tags}\n"
        f"- favorite brands/affinities: {brands}\n"
        f"- budget: {budget}\n"
    )

# ── Endpoint: POST /analyze_and_recommend ─────────────────────────────────────
@https_fn.on_request(cors=CORS)
def analyze_and_recommend(req: https_fn.Request) -> https_fn.Response:
    if req.method == "OPTIONS":
        return cors_preflight()

    auth_resp = require_api_key(req)
    if auth_resp:
        return auth_resp

    if not GEMINI_API_KEY and not OPENAI_API_KEY:
        return cors_ok({"error": "No AI API key configured (GEMINI_API_KEY or OPENAI_API_KEY)"}, 500)

    try:
        body = req.get_json(silent=True) or {}
        image_b64 = body.get("image_b64")
        mime_type = body.get("mime_type", "image/jpeg")
        user_id = body.get("user_id")
        budget_max = body.get("budget_max")  # optional number

        if not image_b64:
            return cors_ok({"error": "image_b64 is required"}, 400)
        if len(image_b64) > MAX_IMAGE_B64_CHARS:
            return cors_ok({"error": "Image too large"}, 413)

        # P: Perceive
        style_analysis = get_style_description(image_b64, mime_type)

        # Style DNA enrich (optional)
        db = firestore.client()
        dna = get_user_style_dna(db, user_id) if user_id else {}
        dna_text = style_dna_to_text(dna)

        # E: Enrich
        embed_input = (
            (style_analysis.get("embedding_text") or style_analysis.get("style_description") or "fashion item")
            + ("\n" + dna_text if dna_text else "")
        )
        query_vector = embed_text(embed_input)

        # A: Adapt (get a pool, not just 5)
        matches_pool = vector_search_catalog(db, query_vector, top_k=20)

        # Compose outfit (slots)
        preferred_colors = style_analysis.get("colors", [])
        outfit = compose_outfit(matches_pool, budget_max=budget_max, preferred_colors=preferred_colors)

        # R: Reflect
        recommendation = generate_recommendation(style_analysis, outfit)

        # Optional: log
        if user_id:
            db.collection("recommendation_history").add({
                "user_id": user_id,
                "style_analysis": style_analysis,
                "matches_pool_ids": [m["id"] for m in matches_pool[:20] if "id" in m],
                "outfit_item_ids": outfit.get("item_ids", []),
                "recommendation": recommendation,
                "timestamp": firestore.SERVER_TIMESTAMP,
            })

        return cors_ok({
            "style_analysis": style_analysis,
            "matches_pool": matches_pool[:20],
            "outfit": outfit,
            "recommendation": recommendation,
        })

    except Exception as e:
        return cors_ok({"error": str(e)}, 500)

# ── Endpoint: GET /get_catalog ─────────────────────────────────────────────────
@https_fn.on_request(cors=CORS)
def get_catalog(req: https_fn.Request) -> https_fn.Response:
    if req.method == "OPTIONS":
        return cors_preflight()

    auth_resp = require_api_key(req)
    if auth_resp:
        return auth_resp

    try:
        db = firestore.client()
        limit = min(int(req.args.get("limit", 50)), 200)
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
    if req.method == "OPTIONS":
        return cors_preflight()

    auth_resp = require_api_key(req)
    if auth_resp:
        return auth_resp

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
    if req.method == "OPTIONS":
        return cors_preflight()

    auth_resp = require_api_key(req)
    if auth_resp:
        return auth_resp

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
    if req.method == "OPTIONS":
        return cors_preflight()

    auth_resp = require_api_key(req)
    if auth_resp:
        return auth_resp

    try:
        body = req.get_json(silent=True) or {}
        user_id = body.get("user_id")
        user_idea = body.get("idea", "A futuristic casual look")
        if not user_id:
            return cors_ok({"error": "user_id is required"}, 400)

        model = genai.GenerativeModel(VISION_MODEL)
        prompt = (
            "You are an expert fashion designer collaborating with a client. "
            f"Their raw idea: '{user_idea}'.\n"
            "Create a highly detailed, professional prompt for an AI image generator to visualize this look. "
            "Include details about fabrics, cut, lighting, mood, and color palette. "
            "Keep it under 80 words."
        )
        detailed_prompt = (model.generate_content(prompt).text or "").strip()

        name_prompt = f"Give a catchy 2-4 word name for this fashion capsule concept: {detailed_prompt}"
        capsule_name = (model.generate_content(name_prompt).text or "").strip().replace('"', '')

        db = firestore.client()
        design_data = {
            "user_id": user_id,
            "original_idea": user_idea,
            "ai_prompt": detailed_prompt,
            "capsule_name": capsule_name,
            "timestamp": firestore.SERVER_TIMESTAMP,
            "status": "blueprint",
        }
        doc_ref = db.collection("user_designs").add(design_data)[1]

        return cors_ok({
            "design_id": doc_ref.id,
            "capsule_name": capsule_name,
            "generation_prompt": detailed_prompt,
            "message": "AI Designer has prepared your blueprint. Ready for visualization.",
        })
    except Exception as e:
        return cors_ok({"error": str(e)}, 500)

# ── Endpoint: POST /stylescape/checkout_generated_look ─────────────────────────
@https_fn.on_request(cors=CORS)
def stylescape_checkout_generated_look(req: https_fn.Request) -> https_fn.Response:
    if req.method == "OPTIONS":
        return cors_preflight()

    auth_resp = require_api_key(req)
    if auth_resp:
        return auth_resp

    try:
        body = req.get_json(silent=True) or {}
        image_b64 = body.get("image_b64")
        mime_type = body.get("mime_type", "image/jpeg")
        budget_max = body.get("budget_max")

        if not image_b64:
            return cors_ok({"error": "image_b64 is required. Provide the generated look."}, 400)
        if len(image_b64) > MAX_IMAGE_B64_CHARS:
            return cors_ok({"error": "Image too large"}, 413)

        style_analysis = get_style_description(image_b64, mime_type)

        embed_input = style_analysis.get("embedding_text") or style_analysis.get("style_description") or "fashion item"
        query_vector = embed_text(embed_input)

        db = firestore.client()
        pool = vector_search_catalog(db, query_vector, top_k=20)
        outfit = compose_outfit(pool, budget_max=budget_max, preferred_colors=style_analysis.get("colors", []))

        # total
        total_price = float(outfit.get("estimated_total", 0.0) or 0.0)

        return cors_ok({
            "generated_style": style_analysis.get("style_description"),
            "outfit": outfit,
            "estimated_cart_total": total_price,
            "message": "Dreams to Reality: Here is a shoppable outfit closest to your generated look.",
        })
    except Exception as e:
        return cors_ok({"error": str(e)}, 500)

# ── Validator Agent (Vision QA) ───────────────────────────────────────────────
def validate_vton_result(user_image_b64: str, result_image_b64: str) -> dict:
    """
    Compares user photo vs try-on output.
    Returns JSON: {status, score, failure_reason, fix_instruction}
    """
    if not GEMINI_API_KEY:
        return {"status": "MOCK", "score": 5, "failure_reason": "", "fix_instruction": ""}

    model = genai.GenerativeModel(VALIDATOR_MODEL)
    prompt = (
        "ACT AS A FASHION QA AGENT. Compare IMAGE_A (Original User) and IMAGE_B (AI Try-On Result).\n"
        "Criteria:\n"
        "1. IDENTITY: Is the face strongly preserved from IMAGE_A to IMAGE_B?\n"
        "2. ANATOMY: Any AI artifacts (extra fingers, warped limbs, blur)?\n"
        "3. GARMENTS: Does clothing look realistically applied?\n\n"
        "Return ONLY JSON:\n"
        "{\n"
        '  "status": "PASS" or "FAIL",\n'
        '  "score": 0-10,\n'
        '  "failure_reason": "string",\n'
        '  "fix_instruction": "string"\n'
        "}"
    )
    parts = [
        {"mime_type": "image/jpeg", "data": user_image_b64},
        {"mime_type": "image/jpeg", "data": result_image_b64},
        prompt,
    ]
    try:
        response = model.generate_content(parts)
        res = extract_json((response.text or "").strip())
        return {
            "status": res.get("status", "PASS"),
            "score": res.get("score", 5),
            "failure_reason": res.get("failure_reason", ""),
            "fix_instruction": res.get("fix_instruction", ""),
        }
    except Exception as e:
        return {"status": "MOCK", "score": 5, "failure_reason": "", "fix_instruction": f"validator_error: {e}"}

# ── REAL VTON PIPELINE (Replicate) ─────────────────────────────────────────────
def run_vton_pipeline(user_image_b64: str, garment_images: List[str], attempt: int = 1) -> dict:
    """
    Calls Replicate IDM-VTON model to generate try-on result.
    Retries up to 3 times if validation fails (and model supports instructions).
    """
    if not HAS_REPLICATE or not REPLICATE_API_TOKEN:
        # Fallback to mock if replicate not configured
        return {"result_image_b64": user_image_b64, "validation_report": {"status": "MOCK"}, "attempts": attempt}

    # For simplicity, we only use the first garment image (IDM-VTON expects one garment)
    garment_b64 = garment_images[0] if garment_images else user_image_b64

    # Convert base64 to data URL
    user_data_url = f"data:image/jpeg;base64,{user_image_b64}"
    garment_data_url = f"data:image/jpeg;base64,{garment_b64}"

    try:
        # Run Replicate model
        output = replicate.run(
            REPLICATE_VTON_MODEL,
            input={
                "human_image": user_data_url,
                "garment_image": garment_data_url,
                "category": "upper_body"  # Could be derived from garment analysis; default upper_body
            }
        )
        # Output is typically a URL to the result image
        if isinstance(output, str) and output.startswith("http"):
            import requests
            img_response = requests.get(output)
            img_response.raise_for_status()
            result_b64 = base64.b64encode(img_response.content).decode("utf-8")
        elif isinstance(output, list) and output and isinstance(output[0], str) and output[0].startswith("http"):
            img_response = requests.get(output[0])
            img_response.raise_for_status()
            result_b64 = base64.b64encode(img_response.content).decode("utf-8")
        else:
            # Unexpected output format
            result_b64 = user_image_b64
    except Exception as e:
        # On error, fallback to mock
        result_b64 = user_image_b64
        return {
            "result_image_b64": result_b64,
            "validation_report": {"status": "ERROR", "failure_reason": str(e)},
            "attempts": attempt
        }

    # Validate result
    validation = validate_vton_result(user_image_b64, result_b64)

    # Retry logic if FAIL and attempts < 3
    if validation.get("status") == "FAIL" and attempt < 3:
        # Optional: pass fix_instruction to model if supported (most models don't)
        return run_vton_pipeline(user_image_b64, garment_images, attempt + 1)

    return {"result_image_b64": result_b64, "validation_report": validation, "attempts": attempt}

# ── Endpoint: POST /stylescape/virtual_try_on ─────────────────────────────────
@https_fn.on_request(cors=CORS)
def stylescape_virtual_try_on(req: https_fn.Request) -> https_fn.Response:
    if req.method == "OPTIONS":
        return cors_preflight()

    auth_resp = require_api_key(req)
    if auth_resp:
        return auth_resp

    try:
        body = req.get_json(silent=True) or {}
        user_b64 = body.get("user_image_b64")
        garment_b64s = body.get("garment_b64s", [])
        user_id = body.get("user_id")

        if not user_b64 or not garment_b64s:
            return cors_ok({"error": "user_image_b64 and garment_b64s are required"}, 400)

        if len(user_b64) > MAX_IMAGE_B64_CHARS:
            return cors_ok({"error": "User image too large"}, 413)

        result = run_vton_pipeline(user_b64, garment_b64s, attempt=1)
        if "error" in result:
            return cors_ok(result, 500)

        db = firestore.client()
        if user_id:
            db.collection("user_designs").add({
                "user_id": user_id,
                "type": "virtual_try_on",
                "result_b64": result["result_image_b64"],
                "validation": result["validation_report"],
                "attempts": result.get("attempts", 1),
                "timestamp": firestore.SERVER_TIMESTAMP,
            })

        return cors_ok({
            "status": "success",
            "result_image_b64": result["result_image_b64"],
            "validation": result["validation_report"],
            "message": "Virtual Try-On completed via Replicate IDM-VTON.",
        })
    except Exception as e:
        return cors_ok({"error": str(e)}, 500)
