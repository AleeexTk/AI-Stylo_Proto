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
    # creative preferences (optional extension, backward compatible)
    creativity_level: float = 0.5
    tone_preference: str = "balanced"
    preferred_aesthetics: List[str] = field(default_factory=list)
    # DNA / Anthropometry
    gender: str = "male"
    body_type: str = "rectangular"
    measurements: Dict[str, float] = field(default_factory=dict)
    meta_data: Dict[str, Any] = field(default_factory=dict)


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
class AssistantMessage:
    role: str
    content: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)

    @classmethod
    def from_raw(cls, raw_message: Dict[str, Any]) -> "AssistantMessage":
        role = raw_message.get("role", "assistant") if isinstance(raw_message, dict) else "assistant"
        content = raw_message.get("content", "") if isinstance(raw_message, dict) else ""
        raw_tool_calls = raw_message.get("tool_calls", []) if isinstance(raw_message, dict) else []

        tool_calls = [ToolCall.from_raw(call) for call in raw_tool_calls if isinstance(call, dict)]
        tool_calls = [call for call in tool_calls if call.name]

        return cls(role=role, content=content or "", tool_calls=tool_calls)


@dataclass
class AssistantResult:
    final_text: str = ""
    tool_outputs: List[ToolResult] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def reply(self) -> str:
        """Backward-compatible alias for legacy consumers."""
        return self.final_text

    @property
    def tool_results(self) -> List[Dict[str, Any]]:
        """Backward-compatible alias for legacy list[dict] tool results."""
        return [
            {"tool_name": out.tool_name, "arguments": out.arguments, "result": out.result, "call_id": out.call_id}
            for out in self.tool_outputs
        ]

    @classmethod
    def normalize_from_llm_response(
        cls,
        llm_response: Dict[str, Any],
        tool_outputs: Optional[List[ToolResult]] = None,
        notes: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "AssistantResult":
        """
        Explicit normalization schema for heterogeneous LLM responses.
        """
        message_payload = llm_response.get("message", {}) if isinstance(llm_response, dict) else {}
        final_text = ""
        if isinstance(message_payload, dict):
            final_text = message_payload.get("content", "") or ""

        if not final_text and isinstance(llm_response, dict):
            final_text = (
                llm_response.get("content")
                or llm_response.get("output_text")
                or ""
            )

        merged_metadata = dict(metadata or {})
        merged_metadata.setdefault("normalization", {
            "content_priority": [
                "message.content",
                "content",
                "output_text",
                "",
            ]
        })
        if isinstance(llm_response, dict):
            merged_metadata.setdefault("raw_response", llm_response)

        return cls(
            final_text=final_text,
            tool_outputs=list(tool_outputs or []),
            notes=list(notes or []),
            metadata=merged_metadata,
        )
