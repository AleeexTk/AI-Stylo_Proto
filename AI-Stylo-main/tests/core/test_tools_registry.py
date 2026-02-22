import json

from apps.core.tools_registry import PreferenceToolRegistry


def test_tool_schemas_are_valid_json_and_function_shape():
    registry = PreferenceToolRegistry(preference_store={})

    schemas = registry.tool_schemas()
    json.dumps(schemas)

    assert len(schemas) == 1
    tool = schemas[0]
    assert tool["type"] == "function"
    assert tool["function"]["name"] == "save_preference"
    assert tool["function"]["parameters"]["type"] == "object"


def test_tool_dispatch_persists_by_domain_and_returns_error_for_unknown_tool():
    profile_store = {}
    registry = PreferenceToolRegistry(preference_store=profile_store, default_domain="fashion")

    ok = registry.execute("save_preference", {"key": "genre", "value": "comedy", "domain": "cinema"})
    err = registry.execute("missing_tool", {"key": "genre", "value": "comedy"})

    assert ok["ok"] is True
    assert profile_store["saved_preferences"]["cinema"]["genre"] == "comedy"
    assert err["ok"] is False
    assert "Unsupported tool" in err["error"]
