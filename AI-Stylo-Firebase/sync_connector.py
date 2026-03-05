"""
AI-Stylo Local → Firebase Sync Connector
==========================================
Protocol bridge between the local SQLite core (ai_stylo_v1.db)
and the Firebase cloud (Firestore).

This is the ONLY file in AI-Stylo-Firebase that is allowed to
import from the parent project's ai_stylo/ package.

Usage:
    python sync_connector.py --user-id <USER_ID> [--catalog] [--dna]

Requirements:
    pip install firebase-admin
    Set GOOGLE_APPLICATION_CREDENTIALS env var to your serviceAccount.json path.

IMPORTANT: Never commit serviceAccount.json to git!
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# -- Allow importing from the parent project (only this file!) -----------
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

import firebase_admin
from firebase_admin import credentials, firestore

# -- Firebase Init --------------------------------------------------------
SERVICE_ACCOUNT = os.environ.get(
    "GOOGLE_APPLICATION_CREDENTIALS",
    str(Path(__file__).parent / "serviceAccount.json")
)
DB_PATH = ROOT_DIR / "ai_stylo_v1.db"
CATALOG_PATH = ROOT_DIR / "data" / "global_market.json"


def init_firebase():
    if not firebase_admin._apps:
        cred = credentials.Certificate(SERVICE_ACCOUNT)
        firebase_admin.initialize_app(cred)
    return firestore.client()


# -- Sync: Style DNA ------------------------------------------------------
def sync_user_dna(db: firestore.Client, user_id: str):
    """Reads user profile from SQLite and pushes to Firestore."""
    print(f"[SYNC] Connecting to local DB: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Adjust query to match your actual table schema
    cur.execute("SELECT * FROM user_profiles WHERE id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        print(f"[SYNC] ⚠ No local profile found for user_id={user_id}")
        return

    dna_data = dict(row)
    dna_data["synced_at"] = datetime.utcnow().isoformat()

    db.collection("style_dna").document(user_id).set(dna_data, merge=True)
    print(f"[SYNC] ✅ Style DNA synced for user '{user_id}'")


# -- Sync: Catalog --------------------------------------------------------
def sync_catalog(db: firestore.Client):
    """Reads global_market.json and pushes items to Firestore."""
    if not CATALOG_PATH.exists():
        print(f"[SYNC] ⚠ Catalog not found at {CATALOG_PATH}")
        return

    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    items = catalog if isinstance(catalog, list) else catalog.get("items", [])
    batch = db.batch()
    count = 0

    for item in items:
        item_id = item.get("id") or item.get("sku") or str(count)
        ref = db.collection("catalog").document(str(item_id))
        batch.set(ref, {**item, "synced_at": datetime.utcnow().isoformat()}, merge=True)
        count += 1

        if count % 500 == 0:  # Firestore batch limit
            batch.commit()
            batch = db.batch()

    batch.commit()
    print(f"[SYNC] ✅ Catalog synced: {count} items pushed to Firestore")


# -- CLI ------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI-Stylo Local → Firebase Sync Connector")
    parser.add_argument("--user-id", type=str, help="User ID to sync Style DNA for")
    parser.add_argument("--catalog", action="store_true", help="Sync the global market catalog")
    parser.add_argument("--dna", action="store_true", help="Sync user Style DNA")
    args = parser.parse_args()

    print("[SYNC] Initializing Firebase connection...")
    db = init_firebase()

    if args.catalog:
        sync_catalog(db)

    if args.dna and args.user_id:
        sync_user_dna(db, args.user_id)

    if not args.catalog and not args.dna:
        print("[SYNC] No action specified. Use --catalog or --dna --user-id <ID>")
        parser.print_help()
