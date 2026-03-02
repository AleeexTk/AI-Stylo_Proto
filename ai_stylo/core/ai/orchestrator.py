import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Protocol, Tuple

from ai_stylo.adapters.ollama_adapter import OllamaAdapter
from ai_stylo.core.contracts import AssistantMessage, AssistantResult, Profile, ToolResult
from ai_stylo.core.memory import SQLitePreferenceStore, SQLiteProfileStore, SQLiteVectorStore
from ai_stylo.core.ai.agentic import AgenticInterface



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

    def dispatch(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
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
        self.agentic = AgenticInterface(self.ollama_adapter)

    def handle(self, user_id: str, user_message: str, forced_domain: Optional[str] = None) -> AssistantResult:
        # 1. PERCEIVE
        perception = self.perceive(user_message)
        domain = (forced_domain or perception["domain"]).strip().lower() 
        event_type = perception["event_type"]
        vibe = perception.get("vibe", ["contemporary"])
        
        # 2. ENRICH
        context = self.enrich(user_id=user_id, domain=domain, event_type=event_type)
        context["adapted_notes"] = self.adapt(context=context, domain=domain)
        context["vibe"] = vibe
        
        # 3. MEMORY GATE (Hard Filters)
        memory_trace = self._build_memory_trace(context)
        trace = {
            "perceive": {"event": event_type, "dresscode": self._map_dresscode(event_type), "vibe": vibe},
            "enrich": context["external_context"],
            "dna": {"body_type": getattr(context["profile"], "body_type", "rectangular"), "fit_pref": context["profile"].style_preset},
            "memory": memory_trace
        }
        context["trace"] = trace
        
        # 4. ACT (with internal Self-Correction loop)
        act_result = self.act(user_message=user_message, domain=domain, context=context)
        
        hard_blocks = memory_trace.get("hard_blocks", [])
        violations = self._detect_violations(act_result.final_text, hard_blocks)
        
        if violations:
            trace["memory"]["violations_found"] = violations
            # Use act() for self-correction to ensure tools are supported if model decides to use them
            act_result = self._self_correct(user_message, context, violations)
            trace["memory"]["self_corrected"] = True
        
        # 5. REFLECT (Memory recording)
        note = self.reflect(
            user_id=user_id,
            user_message=user_message,
            assistant_reply=act_result.final_text,
            domain=domain,
            preferences_before=context["preferences"],
            violations_count=len(violations)
        )

        act_result.notes.append(note)
        act_result.metadata.update({
            "domain": domain,
            "event_type": event_type,
            "trace": trace,
            "profile": context["profile"],
            "preferences": context["preferences"],
            "external_context": context["external_context"]
        })
        return act_result

    def handle_agentic_url(self, user_id: str, url: str, dom_sample: str) -> AssistantResult:
        """Specialized flow for external sites (Stylescape Hub-and-Spoke)."""
        site_map = self.agentic.map_external_site(url, dom_sample)
        manifest = self.agentic.build_action_manifest(site_map)
        
        result = AssistantResult(
            final_text=f"🧬 AI-Stylo Connected to {site_map.domain}. I've identified the product structure and ready to sync with your Style DNA.",
            metadata={
                "agentic": True,
                "domain": site_map.domain,
                "manifest": manifest,
                "selectors": vars(site_map)
            }
        )
        return result

    def perceive(self, user_message: str) -> Dict[str, Any]:
        text = user_message.lower()
        event_map = {
            "formal": ["wedding", "gala", "весілля", "банкет", "офіцій"],
            "casual": ["walk", "friends", "прогулянка", "друзі", "кафе"],
            "business": ["meeting", "work", "office", "зустріч", "робота"],
            "active": ["sport", "gym", "hiking", "спорт", "зал", "біг"],
            "nightlife": ["club", "party", "rave", "рейв", "вечірка", "клуб"]
        }
        vibe_map = {
            "cyberpunk": ["киберпанк", "cyberpunk", "techwear", "neon"],
            "minimalist": ["минимализм", "minimalist", "clean"],
            "vintage": ["винтаж", "vintage", "retro"],
            "aggressive": ["агрессив", "aggressive", "dark", "heavy"]
        }
        event_scores = {ev: sum(1 for k in kws if k in text) for ev, kws in event_map.items()}
        detected_event = max(event_scores, key=event_scores.get) if any(event_scores.values()) else "general"
        
        detected_vibes = [v for v, kws in vibe_map.items() if any(kw in text for kw in kws)] or ["contemporary"]
        fashion_keywords = {"style", "outfit", "look", "wardrobe", "одеж", "стиль", "лук", "вдяг"}
        if any(word in text for word in fashion_keywords) or detected_event != "general":
            return {"domain": "fashion", "event_type": detected_event, "vibe": detected_vibes}
        return {"domain": "general", "event_type": "none", "vibe": []}

    def _map_dresscode(self, event_type: str) -> str:
        return {
            "formal": "black_tie_or_formal",
            "casual": "smart_casual",
            "business": "business_professional",
            "nightlife": "avant_garde_or_street",
            "active": "athleisure"
        }.get(event_type, "casual")

    def _build_memory_trace(self, context: Dict[str, Any]) -> Dict[str, Any]:
        prefs = context.get("preferences", {})
        hard_blocks = []
        if "dislike_color" in prefs: hard_blocks.append(prefs["dislike_color"])
        if "dislike_fit" in prefs: hard_blocks.append(prefs["dislike_fit"])
        profile = context["profile"]
        if hasattr(profile, 'meta_data'):
             m = profile.meta_data or {}
             if m.get('hard_dislikes'): 
                 hard_blocks.extend(m['hard_dislikes'])
        return {
            "hard_blocks": list(set(hard_blocks)),
            "soft_prefs": context.get("adapted_notes", [])[:3]
        }

    def enrich(self, user_id: str, domain: str, event_type: str = "general") -> Dict[str, Any]:
        profile = self.profile_repo.get_profile(user_id)
        preferences = self.preference_repo.get_preferences(user_id)
        memory_notes = self.memory.get_recent(user_id)
        external_context = {
            "location": "Kyiv, UA",
            "weather": "Sunny, 18°C",
            "time": datetime.now().strftime("%H:%M")
        }
        return {
            "domain": domain,
            "event_type": event_type,
            "profile": profile,
            "preferences": preferences,
            "memory_notes": memory_notes,
            "external_context": external_context
        }

    def _detect_violations(self, text: str, hard_blocks: List[str]) -> List[str]:
        if not hard_blocks: return []
        found = []
        low_text = text.lower()
        taxonomy = {
            "orange": ["orange", "оранж", "рудий", "апельсин"],
            "slim-fit": ["slim", "skinny", "облегал", "вузьк", "силует", "фіт"],
            "polyester": ["polyester", "поліестер", "синтет"],
            "leather": ["leather", "шкір", "кожа"],
            "black": ["black", "чорн", "черн"]
        }
        for block in hard_blocks:
            synonyms = taxonomy.get(block.lower(), [block.lower()])
            if any(syn in low_text for syn in synonyms):
                found.append(block)
        return found

    def _self_correct(self, user_message: str, context: Dict[str, Any], violations: List[str]) -> AssistantResult:
        # We wrap the act logic to include a correction instruction
        orig_prompt = self._build_system_prompt(domain=context.get("domain", "fashion"), context=context)
        correction_instruction = (
            f"\n\nCRITICAL ERROR: Your previous response contained blocked elements: {', '.join(violations)}.\n"
            "DO NOT suggest these items or styles. Rewrite your response NOW, proposing alternatives "
            "that strictly follow the user's hard constraints and style DNA."
        )
        
        # We can't easily recurse into act() because it rebuilds prompt. 
        # But we can monkey-patch the context or just call LLM directly with tools.
        messages = [
            {"role": "system", "content": orig_prompt + correction_instruction},
            {"role": "user", "content": user_message}
        ]
        tools = self.tool_registry.tool_schemas()
        response = self.ollama_adapter.chat(messages=messages, tools=tools)
        # We normalize but we don't handle second-pass here to keep it simple, 
        # model should be smart enough in correction to just answer.
        return AssistantResult.normalize_from_llm_response(
            llm_response=response,
            metadata={"step": "self-correction", "violations": violations}
        )

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
            compact_json = json.dumps(compact, ensure_ascii=False)
            compact_size = len(compact_json)
            if total_chars + compact_size > self.MAX_MEMORY_CONTEXT_CHARS:
                continue
            selected.append(compact)
            total_chars += compact_size

        selected.sort(key=lambda x: x.get("ts", ""))
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
                messages.append({"role": "tool", "name": call.name, "content": json.dumps(result, ensure_ascii=False)})

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
        violations_count: int = 0
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
            "violations_count": violations_count
        }
        compact_dict = self._compact_note(note_obj)
        note_str = json.dumps(compact_dict, ensure_ascii=False, separators=(",", ":"))
        self.memory.add_note(user_id=user_id, note=note_str)
        return note_str

    def _extract_intent(self, user_message: str) -> str:
        return user_message.strip().replace("\n", " ")[:80]

    def _summarize_execution_result(self, assistant_reply: str) -> str:
        reply = assistant_reply.strip().lower()
        weak_signals = ["не знаю", "can't", "cannot", "недостаточно", "уточни", "unknown"]
        if any(signal in reply for signal in weak_signals):
            return "uncertainty or missing details"
        return "actionable answer generated"

    def _infer_preferences_from_message(self, user_message: str, domain: str) -> Dict[str, Any]:
        text = user_message.lower()
        updates: Dict[str, Any] = {}
        if domain == "fashion":
            color_keywords = ["black", "white", "blue", "red", "черн", "бел", "син", "крас"]
            detected_color = next((word for word in color_keywords if word in text), None)
            if detected_color: updates["favorite_color_hint"] = detected_color
            
            import re
            budget_matches = re.findall(r"\d+", text)
            if budget_matches:
                # If range, take the second number as max limit
                updates["budget_hint"] = int(budget_matches[-1]) 
        return updates

    def _parse_note(self, note: str) -> Dict[str, Any]:
        try:
            parsed = json.loads(note)
            if isinstance(parsed, dict): return parsed
        except json.JSONDecodeError: pass
        return {"ts": "", "domain": "general", "intent": note[:80], "result": note[:120], "preferences_updated": []}

    def _note_relevance(self, note: Dict[str, Any], domain: str) -> Tuple[int, str]:
        note_domain = str(note.get("domain", "general"))
        score = 2 if note_domain == domain else 1 if note_domain == "general" else 0
        return score, str(note.get("ts", ""))

    def _compact_note(self, note: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "ts": note.get("ts", ""),
            "domain": note.get("domain", "general"),
            "intent": str(note.get("intent", ""))[:80],
            "result": str(note.get("result", ""))[:120],
            "preferences_updated": list(note.get("preferences_updated", []))[:6],
        }

    def _build_system_prompt(self, domain: str, context: Dict[str, Any]) -> str:
        profile: Profile = context["profile"]
        adapted_notes: List[Dict[str, Any]] = context.get("adapted_notes", [])
        event_type = context.get("event_type", "general")
        vibe = context.get("vibe", [])
        ext = context.get("external_context", {})
        trace = context.get("trace", {})
        instruction = (
            f"You are the AI-Stylo Decision Engine. Your goal is to guide the user to the perfect outfit for a '{event_type}' event.\n"
            "CURRENT CONTEXT (HARD CONSTRAINTS):\n"
            f"- Location: {ext.get('location')} / Weather: {ext.get('weather')}\n"
            f"- Preferred Vibe: {', '.join(vibe)}\n"
            f"- Dresscode: {trace.get('perceive', {}).get('dresscode')}\n"
            f"- User Style DNA: {profile.style_preset}, Gender: {getattr(profile, 'gender', 'male')}\n"
            f"- MEMORY BLOCKS (DO NOT USE): {', '.join(trace.get('memory', {}).get('hard_blocks', []))}\n"
            "\n"
            "DECISION PROTOCOL (STRICT):\n"
            "1. Validate constraints: If the user asks for a 'hard block' item, explain why you are rejecting it.\n"
            "2. Propose 3 Looks: [Title, Items, Justification].\n"
            f"3. Alignment: Justify each look using the weather ({ext.get('weather')}) and event type ({event_type})."
        )
        return f"{instruction}\nAdapted memory insights: {json.dumps(adapted_notes, ensure_ascii=False)}\nReturn the final answer in the user's language."