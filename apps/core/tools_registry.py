from typing import Any, Dict, List


class PreferenceToolRegistry:
    """Simple tool registry for saving user preferences by domain."""

    def __init__(self, preference_store: Dict[str, Any] | None = None, default_domain: str = "fashion") -> None:
        self.preference_store = preference_store if preference_store is not None else {}
        self.default_domain = default_domain
        self.domain_options = ("fashion", "cinema", "general")

    def tool_schemas(self) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "save_preference",
                    "description": "Persist a user preference for the active domain.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "key": {"type": "string", "description": "Preference key, e.g. tone/style/genre"},
                            "value": {"description": "Preference value"},
                            "domain": {"type": "string", "enum": list(self.domain_options)},
                        },
                        "required": ["key", "value"],
                    },
                },
            }
        ]

    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if tool_name != "save_preference":
            return {"ok": False, "error": f"Unsupported tool: {tool_name}"}

        key = str(arguments.get("key", "")).strip()
        if not key:
            return {"ok": False, "error": "Missing required argument: key"}

        domain = str(arguments.get("domain") or self.default_domain).strip().lower()
        if domain not in self.domain_options:
            domain = self.default_domain

        raw_value = arguments.get("value")
        value = raw_value if isinstance(raw_value, (dict, list, int, float, bool)) else str(raw_value).strip()

        by_domain = self.preference_store.setdefault("saved_preferences", {})
        domain_store = by_domain.setdefault(domain, {})
        domain_store[key] = value

        return {
            "ok": True,
            "tool": "save_preference",
            "domain": domain,
            "saved": {key: value},
            "all_preferences": domain_store,
        }
