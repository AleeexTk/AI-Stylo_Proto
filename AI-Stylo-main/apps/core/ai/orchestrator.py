import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Protocol, Tuple

from apps.adapters.ollama_adapter import OllamaAdapter
from apps.core.contracts import Profile


@dataclass
class AssistantResult:
    reply: str
    domain: str
    profile: Profile
    preferences: Dict[str, Any]
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    reflection_note: str = ""
    raw_response: Dict[str, Any] = field(default_factory=dict)


class ProfileRepository(Protocol):
    def get_profile(self, user_id: str) -> Profile:
        ...


class PreferenceRepository(Protocol):
    def get_preferences(self, user_id: str) -> Dict[str, Any]:
        ...


class SessionMemory(Protocol):
    def get_recent(self, user_id: str, limit: int = 5) -> List[str]:
        ...

    def add_note(self, user_id: str, note: str) -> None:
        ...


class ToolRegistry(Protocol):
    def tool_schemas(self) -> List[Dict[str, Any]]:
        ...

    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        ...


class InMemoryProfileRepository:
    def __init__(self) -> None:
        self._profiles: Dict[str, Profile] = {}

    def get_profile(self, user_id: str) -> Profile:
        if user_id not in self._profiles:
            self._profiles[user_id] = Profile(user_id=user_id)
        return self._profiles[user_id]


class InMemoryPreferenceRepository:
    def __init__(self) -> None:
        self._preferences: Dict[str, Dict[str, Any]] = {}

    def get_preferences(self, user_id: str) -> Dict[str, Any]:
        return self._preferences.get(user_id, {})


class InMemorySessionMemory:
    def __init__(self) -> None:
        self._notes: Dict[str, List[str]] = {}

    def get_recent(self, user_id: str, limit: int = 5) -> List[str]:
        return self._notes.get(user_id, [])[-limit:]

    def add_note(self, user_id: str, note: str) -> None:
        self._notes.setdefault(user_id, []).append(note)


class PEAROrchestrator:
    MAX_TOOL_ROUNDS = 4

    def __init__(
        self,
        ollama_adapter: OllamaAdapter,
        tool_registry: ToolRegistry,
        profile_repo: Optional[ProfileRepository] = None,
        preference_repo: Optional[PreferenceRepository] = None,
        memory: Optional[SessionMemory] = None,
    ) -> None:
        self.ollama_adapter = ollama_adapter
        self.tool_registry = tool_registry
        self.profile_repo = profile_repo or InMemoryProfileRepository()
        self.preference_repo = preference_repo or InMemoryPreferenceRepository()
        self.memory = memory or InMemorySessionMemory()

    def handle(self, user_id: str, user_message: str) -> AssistantResult:
        domain = self.perceive(user_message)
        context = self.enrich(user_id=user_id, domain=domain)
        act_result = self.act(user_message=user_message, domain=domain, context=context)
        note = self.reflect(
            user_id=user_id,
            user_message=user_message,
            assistant_reply=act_result["reply"],
            domain=domain,
        )

        return AssistantResult(
            reply=act_result["reply"],
            domain=domain,
            profile=context["profile"],
            preferences=context["preferences"],
            tool_results=act_result["tool_results"],
            reflection_note=note,
            raw_response=act_result["raw_response"],
        )

    def perceive(self, user_message: str) -> str:
        text = user_message.lower()
        fashion_keywords = {"style", "outfit", "look", "wardrobe", "одеж", "стиль", "лук"}
        cinema_keywords = {"movie", "film", "cinema", "series", "фильм", "кино", "сериал"}

        if any(word in text for word in fashion_keywords):
            return "fashion"
        if any(word in text for word in cinema_keywords):
            return "cinema"
        return "general"

    def enrich(self, user_id: str, domain: str) -> Dict[str, Any]:
        profile = self.profile_repo.get_profile(user_id)
        preferences = self.preference_repo.get_preferences(user_id)
        memory_notes = self.memory.get_recent(user_id)
        return {
            "domain": domain,
            "profile": profile,
            "preferences": preferences,
            "memory_notes": memory_notes,
        }

    def act(self, user_message: str, domain: str, context: Dict[str, Any]) -> Dict[str, Any]:
        system_prompt = self._build_system_prompt(domain=domain, context=context)
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        tools = self.tool_registry.tool_schemas()
        tool_results: List[Dict[str, Any]] = []
        latest_response = self.ollama_adapter.chat(messages=messages, tools=tools)

        for _ in range(self.MAX_TOOL_ROUNDS):
            assistant_message = latest_response.get("message", {})
            tool_calls = assistant_message.get("tool_calls", []) or []
            if not tool_calls:
                return {
                    "reply": assistant_message.get("content", ""),
                    "tool_results": tool_results,
                    "raw_response": latest_response,
                }

            messages.append(
                {
                    "role": "assistant",
                    "content": assistant_message.get("content", ""),
                    "tool_calls": tool_calls,
                }
            )

            for call in tool_calls:
                tool_name, arguments = self._extract_tool_call(call)
                result = self.tool_registry.execute(tool_name=tool_name, arguments=arguments)
                tool_results.append({"tool_name": tool_name, "arguments": arguments, "result": result})
                messages.append(
                    {
                        "role": "tool",
                        "name": tool_name,
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )

            latest_response = self.ollama_adapter.chat(messages=messages, tools=tools)

        return {
            "reply": latest_response.get("message", {}).get("content", ""),
            "tool_results": tool_results,
            "raw_response": latest_response,
        }

    def reflect(self, user_id: str, user_message: str, assistant_reply: str, domain: str) -> str:
        short_user = user_message.strip().replace("\n", " ")[:90]
        short_reply = assistant_reply.strip().replace("\n", " ")[:90]
        note = f"{datetime.now(timezone.utc).isoformat()} [{domain}] U:{short_user} | A:{short_reply}"
        self.memory.add_note(user_id=user_id, note=note)
        return note

    def _build_system_prompt(self, domain: str, context: Dict[str, Any]) -> str:
        profile: Profile = context["profile"]
        preferences: Dict[str, Any] = context["preferences"]
        memory_notes: List[str] = context["memory_notes"]

        domain_instruction = {
            "fashion": "You are a stylist assistant. Give practical and aesthetic wardrobe advice.",
            "cinema": "You are a cinema assistant. Recommend movies/series with concise justification.",
            "general": "You are a helpful assistant with clear and concise answers.",
        }.get(domain, "You are a helpful assistant.")

        return (
            f"{domain_instruction}\n"
            f"User profile: style_preset={profile.style_preset}, budget={profile.budget_min}-{profile.budget_max}, "
            f"theme_color={profile.theme_color}.\n"
            f"User preferences: {json.dumps(preferences, ensure_ascii=False)}\n"
            f"Recent memory notes: {json.dumps(memory_notes, ensure_ascii=False)}\n"
            "When tools are available, call them when needed and ground your answer in tool outputs."
        )

    @staticmethod
    def _extract_tool_call(call: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        function_payload = call.get("function", {}) if isinstance(call, dict) else {}
        tool_name = function_payload.get("name") or call.get("name")
        raw_arguments = function_payload.get("arguments", call.get("arguments", {}))

        if isinstance(raw_arguments, str):
            try:
                arguments = json.loads(raw_arguments)
            except json.JSONDecodeError:
                arguments = {}
        elif isinstance(raw_arguments, dict):
            arguments = raw_arguments
        else:
            arguments = {}

        if not tool_name:
            raise ValueError("Tool call is missing tool name.")

        return tool_name, arguments
