import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Protocol, Tuple

from apps.adapters.ollama_adapter import OllamaAdapter
from apps.core.contracts import AssistantMessage, AssistantResult, Profile, ToolResult
from apps.core.memory import SQLitePreferenceStore, SQLiteProfileStore, SQLiteVectorStore



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
    ADAPT_NOTES_LIMIT = 5
    MAX_MEMORY_CONTEXT_CHARS = 1200

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
        self.profile_repo = profile_repo or SQLiteProfileStore()
        self.preference_repo = preference_repo or SQLitePreferenceStore()
        self.memory = memory or SQLiteVectorStore()

    def handle(self, user_id: str, user_message: str, forced_domain: Optional[str] = None) -> AssistantResult:
        domain = (forced_domain or "").strip().lower() or self.perceive(user_message)
        context = self.enrich(user_id=user_id, domain=domain)
        adapted_notes = self.adapt(context=context, domain=domain)
        context["adapted_notes"] = adapted_notes
        act_result = self.act(user_message=user_message, domain=domain, context=context)
        note = self.reflect(
            user_id=user_id,
            user_message=user_message,
            assistant_reply=act_result.final_text,
            domain=domain,
            preferences_before=context["preferences"],
        )

        act_result.notes.append(note)
        act_result.metadata.update({
            "domain": domain,
            "profile": context["profile"],
            "preferences": context["preferences"],
        })
        return act_result

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

    def adapt(self, context: Dict[str, Any], domain: str) -> List[Dict[str, Any]]:
        notes = [self._parse_note(note) for note in context.get("memory_notes", [])]
        ranked_notes = sorted(
            notes,
            key=lambda note: self._note_relevance(note=note, domain=domain),
            reverse=True,
        )

        selected: List[Dict[str, Any]] = []
        total_chars = 0
        for note in ranked_notes:
            if len(selected) >= self.ADAPT_NOTES_LIMIT:
                break
            compact = self._compact_note(note)
            compact_size = len(compact)
            if total_chars + compact_size > self.MAX_MEMORY_CONTEXT_CHARS:
                continue
            selected.append(note)
            total_chars += compact_size

        selected.sort(key=lambda item: item.get("ts", ""))
        return selected

    def act(self, user_message: str, domain: str, context: Dict[str, Any]) -> AssistantResult:
        system_prompt = self._build_system_prompt(domain=domain, context=context)
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        tools = self.tool_registry.tool_schemas()
        first_response = self.ollama_adapter.chat(messages=messages, tools=tools)
        assistant_message = AssistantMessage.from_raw(first_response.get("message", {}))

        tool_results: List[ToolResult] = []
        if assistant_message.tool_calls:
            messages.append(
                {
                    "role": "assistant",
                    "content": assistant_message.content,
                    "tool_calls": [
                        {
                            "id": call.call_id,
                            "function": {"name": call.name, "arguments": json.dumps(call.arguments, ensure_ascii=False)},
                        }
                        for call in assistant_message.tool_calls
                    ],
                }
            )

            for call in assistant_message.tool_calls:
                result = self.tool_registry.execute(tool_name=call.name, arguments=call.arguments)
                tool_results.append(ToolResult(tool_name=call.name, arguments=call.arguments, result=result, call_id=call.call_id))
                messages.append(
                    {
                        "role": "tool",
                        "name": call.name,
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )

            second_response = self.ollama_adapter.chat(messages=messages, tools=tools)
            return AssistantResult.normalize_from_llm_response(
                llm_response=second_response,
                tool_outputs=tool_results,
                metadata={"step": "post-tools", "tool_call_count": len(tool_results)},
            )

        return AssistantResult.normalize_from_llm_response(
            llm_response=first_response,
            tool_outputs=tool_results,
            metadata={"step": "single-pass", "tool_call_count": 0},
        )

    def reflect(
        self,
        user_id: str,
        user_message: str,
        assistant_reply: str,
        domain: str,
        preferences_before: Dict[str, Any],
    ) -> str:
        inferred_preferences = self._infer_preferences_from_message(user_message=user_message, domain=domain)
        preferences_updated: List[str] = []

        if inferred_preferences and hasattr(self.preference_repo, "upsert_preferences"):
            self.preference_repo.upsert_preferences(user_id=user_id, preferences=inferred_preferences)
            preferences_updated = sorted(inferred_preferences.keys())

        note_obj = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "domain": domain,
            "intent": self._extract_intent(user_message=user_message),
            "result": self._summarize_execution_result(assistant_reply=assistant_reply),
            "preferences_updated": preferences_updated,
            "preferences_before_count": len(preferences_before),
        }
        note = self._compact_note(note_obj)
        self.memory.add_note(user_id=user_id, note=note)
        return note

    def _extract_intent(self, user_message: str) -> str:
        return user_message.strip().replace("\n", " ")[:80]

    def _summarize_execution_result(self, assistant_reply: str) -> str:
        reply = assistant_reply.strip().lower()
        weak_signals = ["не знаю", "can't", "cannot", "недостаточно", "уточни", "unknown"]
        if any(signal in reply for signal in weak_signals):
            return "what_didnt_work: uncertainty or missing details; what_worked: partial guidance"
        return "what_worked: actionable answer generated; what_didnt_work: not detected"

    def _infer_preferences_from_message(self, user_message: str, domain: str) -> Dict[str, Any]:
        text = user_message.lower()
        updates: Dict[str, Any] = {}

        if domain == "fashion":
            color_keywords = ["black", "white", "blue", "red", "черн", "бел", "син", "крас"]
            detected_color = next((word for word in color_keywords if word in text), None)
            if detected_color:
                updates["favorite_color_hint"] = detected_color

            budget_digits = "".join(ch for ch in text if ch.isdigit())
            if budget_digits:
                updates["budget_hint"] = int(budget_digits)

        if domain == "cinema":
            if any(word in text for word in ["комед", "comedy"]):
                updates["genre_hint"] = "comedy"
            if any(word in text for word in ["драм", "drama"]):
                updates["genre_hint"] = "drama"

        return updates

    def _parse_note(self, note: str) -> Dict[str, Any]:
        try:
            parsed = json.loads(note)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
        return {
            "ts": "",
            "domain": "general",
            "intent": note[:80],
            "result": note[:120],
            "preferences_updated": [],
        }

    def _note_relevance(self, note: Dict[str, Any], domain: str) -> Tuple[int, str]:
        note_domain = str(note.get("domain", "general"))
        score = 2 if note_domain == domain else 1 if note_domain == "general" else 0
        return score, str(note.get("ts", ""))

    def _compact_note(self, note: Dict[str, Any]) -> str:
        compact_note = {
            "ts": note.get("ts", ""),
            "domain": note.get("domain", "general"),
            "intent": str(note.get("intent", ""))[:80],
            "result": str(note.get("result", ""))[:120],
            "preferences_updated": list(note.get("preferences_updated", []))[:6],
        }
        return json.dumps(compact_note, ensure_ascii=False, separators=(",", ":"))

    def _build_system_prompt(self, domain: str, context: Dict[str, Any]) -> str:
        profile: Profile = context["profile"]
        preferences: Dict[str, Any] = context["preferences"]
        adapted_notes: List[Dict[str, Any]] = context.get("adapted_notes", [])

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
            f"Adapted memory notes: {json.dumps(adapted_notes, ensure_ascii=False)}\n"
            "Keep architecture single-agent and simple; do not introduce multi-agent meta-orchestration in MVP.\n"
            "When tools are available, call them when needed and ground your answer in tool outputs."
        )
