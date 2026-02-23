"""Generate deterministic demo catalog for local MVP runs."""

from __future__ import annotations

import json
from pathlib import Path


DEMO_ITEMS = [
    {
        "id": "top_001",
        "name": "Oversized Hoodie",
        "brand": "UrbanPulse",
        "price": 1900,
        "image": "https://picsum.photos/id/1011/300/400",
        "description": "Black oversized hoodie, street casual, soft cotton",
        "category": "top",
    },
    {
        "id": "bottom_001",
        "name": "Wide Cargo Pants",
        "brand": "FieldMotion",
        "price": 2100,
        "image": "https://picsum.photos/id/103/300/400",
        "description": "Wide-leg cargo pants, urban comfort, neutral palette",
        "category": "bottom",
    },
    {
        "id": "shoes_001",
        "name": "Retro Sneakers",
        "brand": "NovaRun",
        "price": 2600,
        "image": "https://picsum.photos/id/21/300/400",
        "description": "Retro sneakers, white-grey, everyday city wear",
        "category": "shoes",
    },
    {
        "id": "accessory_001",
        "name": "Crossbody Bag",
        "brand": "ModeLite",
        "price": 1700,
        "image": "https://picsum.photos/id/433/300/400",
        "description": "Compact crossbody bag, minimalist, matte texture",
        "category": "accessory",
    },
]


if __name__ == "__main__":
    target = Path(__file__).resolve().parent.parent / "data" / "demo_catalog.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {"catalog_id": "demo_generated", "items": DEMO_ITEMS}
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Demo catalog created: {target}")
