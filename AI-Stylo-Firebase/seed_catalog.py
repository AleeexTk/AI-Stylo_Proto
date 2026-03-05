"""
AI-Stylo Catalog Seeder — Firestore with Embeddings
=====================================================
Reads global_market.json (or demo_catalog.json) and pushes items
to Firestore `catalog` collection WITH computed text embeddings.

The embeddings enable Firestore Vector Search for image-based recommendations.

Usage:
    python seed_catalog.py [--source ../../data/global_market.json]

Requirements:
    pip install firebase-admin google-generativeai
    Set GOOGLE_APPLICATION_CREDENTIALS to your serviceAccount.json path
    Set GEMINI_API_KEY to your Gemini API key

Firestore Index Required (run once via Firebase CLI):
    firebase firestore:indexes  →  add a vector index on 'embedding' field
"""

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path

import google.generativeai as genai
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.vector import Vector
from dotenv import load_dotenv

load_dotenv()

try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

# ── Config ────────────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).parent.parent
DEFAULT_CATALOG = ROOT_DIR / "data" / "global_market.json"
SERVICE_ACCOUNT = os.environ.get(
    "GOOGLE_APPLICATION_CREDENTIALS",
    str(Path(__file__).parent / "serviceAccount.json")
)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
EMBED_MODEL = "models/gemini-embedding-001"
OPENAI_EMBED_MODEL = "text-embedding-3-small"
BATCH_SIZE = 20   # Items per Firestore batch commit
EMBED_DELAY = 0.1  # Seconds between embedding API calls (rate limit)


# ── Firebase + Gemini Init ─────────────────────────────────────────────────────
def init_services():
    if not firebase_admin._apps:
        cred = credentials.Certificate(SERVICE_ACCOUNT)
        firebase_admin.initialize_app(cred)
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
    return firestore.client()


# ── Embedding ─────────────────────────────────────────────────────────────────
def build_embedding_text(item: dict) -> str:
    """Create a rich semantic text for embedding from a catalog item."""
    parts = []

    if name := item.get("name") or item.get("title"):
        parts.append(f"Product: {name}")
    if brand := item.get("brand") or item.get("designer"):
        parts.append(f"Brand: {brand}")
    if category := item.get("category") or item.get("type"):
        parts.append(f"Category: {category}")
    if color := item.get("color") or item.get("colors"):
        c = color if isinstance(color, str) else ", ".join(color)
        parts.append(f"Color: {c}")
    if material := item.get("material") or item.get("fabric"):
        parts.append(f"Material: {material}")
    if style := item.get("style") or item.get("style_tags"):
        s = style if isinstance(style, str) else ", ".join(style)
        parts.append(f"Style: {s}")
    if occasion := item.get("occasion"):
        parts.append(f"Occasion: {occasion}")
    if season := item.get("season"):
        parts.append(f"Season: {season}")
    if desc := item.get("description") or item.get("desc"):
        parts.append(f"Description: {desc[:200]}")

    return ". ".join(parts) if parts else str(item)

def embed_text(text: str) -> list[float]:
    # Priority 1: OpenAI (if key and package exist)
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
            print(f"      [WARN] OpenAI API failed ({e}). Proceeding to fallback.")

    # Priority 2: Gemini
    if GEMINI_API_KEY:
        try:
            response = genai.embed_content(
                model=EMBED_MODEL,
                content=text,
                task_type="retrieval_document",
                output_dimensionality=768
            )
            return response["embedding"]
        except Exception as e:
            print(f"      [WARN] Gemini API failed ({e}). Proceeding to fallback.")
            
    # Priority 3: Mock
    print(f"      [WARN] No working valid API. Using mock random 768-D vector.")
    return [random.uniform(-1.0, 1.0) for _ in range(768)]

# ── Seeder ────────────────────────────────────────────────────────────────────
def seed_catalog(db, source_path: Path, overwrite: bool = False):
    print(f"\n[SEED] Loading catalog from: {source_path}")

    if not source_path.exists():
        print(f"[SEED] ⚠ File not found: {source_path}")
        sys.exit(1)

    with open(source_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Support both list format and {"items": [...]} format
    items = data if isinstance(data, list) else data.get("items", [])
    print(f"[SEED] Found {len(items)} items to process")

    batch = db.batch()
    batch_count = 0
    success = 0
    skipped = 0
    errors = 0

    for idx, item in enumerate(items):
        item_id = str(item.get("id") or item.get("sku") or item.get("slug") or idx)
        ref = db.collection("catalog").document(item_id)

        # Skip if already exists and not overwriting
        if not overwrite and ref.get().exists:
            print(f"  [{idx+1}/{len(items)}] ⏭ Skip (exists): {item_id}")
            skipped += 1
            continue

        try:
            # Build rich text for embedding
            embed_text_str = build_embedding_text(item)
            print(f"  [{idx+1}/{len(items)}] 🔄 Embedding: {item.get('name', item_id)[:50]}")

            # Generate embedding
            vector = embed_text(embed_text_str)
            time.sleep(EMBED_DELAY)

            # Prepare Firestore doc
            doc_data = {
                **item,
                "embedding": Vector(vector),
                "embed_text": embed_text_str,
                "seeded_at": firestore.SERVER_TIMESTAMP,
            }

            batch.set(ref, doc_data, merge=True)
            batch_count += 1
            success += 1

            # Commit batch every BATCH_SIZE items
            if batch_count >= BATCH_SIZE:
                batch.commit()
                print(f"  [SEED] 📦 Batch committed ({batch_count} items)")
                batch = db.batch()
                batch_count = 0

        except Exception as e:
            print(f"  [SEED] ❌ Error on item {item_id}: {e}")
            errors += 1

    # Final batch commit
    if batch_count > 0:
        batch.commit()
        print(f"  [SEED] 📦 Final batch committed ({batch_count} items)")

    print(f"\n[SEED] ✅ Done!")
    print(f"  Seeded:  {success}")
    print(f"  Skipped: {skipped}")
    print(f"  Errors:  {errors}")
    print(f"  Total:   {len(items)}")
    print(f"\n[SEED] 🔥 Next step: Create Firestore vector index!")
    print(f"  Run: firebase firestore:indexes")
    print(f"  Or go to Firebase Console → Firestore → Indexes → Add vector index")
    print(f"  Collection: catalog | Field: embedding | Dimension: 768")


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Firestore catalog with embeddings")
    parser.add_argument("--source", type=str, default=str(DEFAULT_CATALOG), help="Path to catalog JSON file")
    parser.add_argument("--overwrite", action="store_true", help="Re-embed and overwrite existing items")
    args = parser.parse_args()

    if not GEMINI_API_KEY and not OPENAI_API_KEY:
        print("[SEED] ⚠ Neither GEMINI_API_KEY nor OPENAI_API_KEY is set. Will use mock vectors.")

    print("[SEED] Initializing Firebase + AI services...")
    db = init_services()
    seed_catalog(db, Path(args.source), overwrite=args.overwrite)
