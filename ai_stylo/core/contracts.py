from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

@dataclass
class Item:
    id: str
    title: str
    brand: str
    price: float
    image: str
    description: str = ""
    tags: List[str] = field(default_factory=list)
    category: str = ""
    old_price: Optional[float] = None
    luxury_index: float = 0.0

@dataclass
class Profile:
    user_id: str
    theme_color: str = "#4A90E2"
    style_preset: str = "casual"
    budget_min: float = 50.0
    budget_max: float = 600.0
    affinities: Dict[str, float] = field(default_factory=dict)
    counters: Dict[str, int] = field(default_factory=dict)
    skills: Dict[str, Any] = field(default_factory=dict)
    seen_events: int = 0
    similarity_history: List[float] = field(default_factory=list)
    creativity_level: float = 0.5
    tone_preference: str = "balanced"
    preferred_aesthetics: List[str] = field(default_factory=list)

@dataclass
class Outfit:
    slots: Dict[str, Optional[Item]]
    total_price: float
    reasons: List[str] = field(default_factory=list)
    discounted_amount: float = 0.0

@dataclass
class Event:
    ts: str
    type: str
    payload: Dict[str, Any]

@dataclass
class ToolCall:
    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    call_id: Optional[str] = None

    @classmethod
    def from_raw(cls, raw_call: Dict[str, Any]) -> "ToolCall":
        function_payload = raw_call.get("function", {}) if isinstance(raw_call, dict) else {}
        tool_name = function_payload.get("name") or raw_call.get("name") or ""
        raw_arguments = function_payload.get("arguments", raw_call.get("arguments", {}))

        if isinstance(raw_arguments, str):
            try:
                import json
                arguments = json.loads(raw_arguments)
            except Exception:
                arguments = {}
        elif isinstance(raw_arguments, dict):
            arguments = raw_arguments
        else:
            arguments = {}

        return cls(
            name=tool_name,
            arguments=arguments,
            call_id=raw_call.get("id") if isinstance(raw_call, dict) else None,
        )

@dataclass
class ToolResult:
    tool_name: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    result: Dict[str, Any] = field(default_factory=dict)
    call_id: Optional[str] = None

@dataclass
class AssistantResult:
    final_text: str = ""
    tool_outputs: List[ToolResult] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
