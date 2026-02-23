import hashlib
import json
from copy import deepcopy
from typing import Any, Dict, List, Optional


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()[:12]


def make_shotlist(input: Dict[str, Any]) -> Dict[str, Any]:
    topic = str(input.get("topic") or "Untitled concept")
    format_name = str(input.get("format") or "social")
    mood = str(input.get("mood") or "clean")
    count = int(input.get("count", 5))
    count = max(1, min(12, count))

    shots: List[Dict[str, Any]] = []
    for index in range(1, count + 1):
        shots.append(
            {
                "id": f"shot_{index}",
                "title": f"{topic} · shot {index}",
                "camera": "wide" if index % 3 == 1 else "medium" if index % 3 == 2 else "close-up",
                "duration_s": 3 + (index % 4),
                "intent": f"{mood} {format_name} narrative beat {index}",
            }
        )

    return {
        "ok": True,
        "tool": "make_shotlist",
        "input_fingerprint": _digest(input),
        "shotlist": {
            "topic": topic,
            "format": format_name,
            "mood": mood,
            "shots": shots,
        },
    }


def make_prompt_pack(input: Dict[str, Any]) -> Dict[str, Any]:
    subject = str(input.get("subject") or input.get("topic") or "fashion editorial")
    style = str(input.get("style") or "cinematic")
    lighting = str(input.get("lighting") or "soft daylight")
    aspect = str(input.get("aspect_ratio") or "4:5")

    base = f"{subject}, {style}, {lighting}, aspect ratio {aspect}"
    prompts = {
        "hero": f"{base}, hero frame, highly detailed",
        "detail": f"{base}, texture close-up, material realism",
        "alt": f"{base}, alternative composition, dynamic angle",
        "negative": "low quality, blurry, deformed hands, watermark, text",
    }

    return {
        "ok": True,
        "tool": "make_prompt_pack",
        "input_fingerprint": _digest(input),
        "prompt_pack": {
            "subject": subject,
            "style": style,
            "lighting": lighting,
            "aspect_ratio": aspect,
            "prompts": prompts,
        },
    }


def make_fashion_capsule(input: Dict[str, Any]) -> Dict[str, Any]:
    style = str(input.get("style") or "casual")
    season = str(input.get("season") or "all-season")
    budget = float(input.get("budget", 500.0))
    palette = input.get("palette") if isinstance(input.get("palette"), list) else ["black", "white", "denim"]
    colors = [str(color) for color in palette][:5]

    item_templates = [
        ("outerwear", 0.28),
        ("top", 0.16),
        ("bottom", 0.18),
        ("shoes", 0.22),
        ("accessory", 0.16),
    ]

    items: List[Dict[str, Any]] = []
    total = 0.0
    for idx, (slot, ratio) in enumerate(item_templates, start=1):
        price = round(max(20.0, budget * ratio), 2)
        total += price
        items.append(
            {
                "slot": slot,
                "name": f"{style} {slot}",
                "color": colors[(idx - 1) % len(colors)],
                "season": season,
                "price": price,
            }
        )

    return {
        "ok": True,
        "tool": "make_fashion_capsule",
        "input_fingerprint": _digest(input),
        "capsule": {
            "style": style,
            "season": season,
            "budget_requested": budget,
            "budget_allocated": round(total, 2),
            "palette": colors,
            "items": items,
        },
    }


def save_preference(input: Dict[str, Any], store: Dict[str, Any]) -> Dict[str, Any]:
    user_id = str(input.get("user_id") or "default")
    key = str(input.get("key") or "preference")
    value = input.get("value")

    next_store = deepcopy(store or {})
    user_preferences = dict(next_store.get(user_id, {}))
    user_preferences[key] = value
    next_store[user_id] = user_preferences

    return {
        "ok": True,
        "tool": "save_preference",
        "input_fingerprint": _digest(input),
        "saved": {"user_id": user_id, "key": key, "value": value},
        "store": next_store,
    }


TOOLS_SCHEMA: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "make_shotlist",
            "description": "Generate deterministic shot list JSON for a given creative brief.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "format": {"type": "string"},
                    "mood": {"type": "string"},
                    "count": {"type": "integer", "minimum": 1, "maximum": 12},
                },
                "required": ["topic"],
                "additionalProperties": True,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "make_prompt_pack",
            "description": "Generate deterministic prompt bundle JSON for image/video generation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "subject": {"type": "string"},
                    "topic": {"type": "string"},
                    "style": {"type": "string"},
                    "lighting": {"type": "string"},
                    "aspect_ratio": {"type": "string"},
                },
                "additionalProperties": True,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "make_fashion_capsule",
            "description": "Generate deterministic capsule wardrobe JSON by style/season/budget.",
            "parameters": {
                "type": "object",
                "properties": {
                    "style": {"type": "string"},
                    "season": {"type": "string"},
                    "budget": {"type": "number", "minimum": 0},
                    "palette": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                        "maxItems": 5,
                    },
                },
                "additionalProperties": True,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_preference",
            "description": "Persist user preference in deterministic in-memory store payload.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                    "key": {"type": "string"},
                    "value": {},
                },
                "required": ["user_id", "key", "value"],
                "additionalProperties": True,
            },
        },
    },
]


def dispatch(tool_name: str, args: Optional[Dict[str, Any]] = None, store: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = args if isinstance(args, dict) else {}
    state = store if isinstance(store, dict) else {}

    if tool_name == "make_shotlist":
        return make_shotlist(payload)
    if tool_name == "make_prompt_pack":
        return make_prompt_pack(payload)
    if tool_name == "make_fashion_capsule":
        return make_fashion_capsule(payload)
    if tool_name == "save_preference":
        return save_preference(payload, state)

    return {
        "ok": False,
        "error": f"Unknown tool '{tool_name}'",
        "available_tools": [schema["function"]["name"] for schema in TOOLS_SCHEMA],
    }


class LocalToolRegistry:
    def __init__(self) -> None:
        self._store: Dict[str, Any] = {}

    def tool_schemas(self) -> List[Dict[str, Any]]:
        return TOOLS_SCHEMA

    def dispatch(self, tool_name: str, args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        result = dispatch(tool_name=tool_name, args=args, store=self._store)
        if tool_name == "save_preference" and result.get("ok"):
            self._store = result.get("store", self._store)
        return result

    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        return self.dispatch(tool_name=tool_name, args=arguments)
