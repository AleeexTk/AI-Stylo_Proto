import json
from pathlib import Path

import httpx

from apps.core.ai.orchestrator import PEAROrchestrator
from apps.core.memory import SQLitePreferenceStore, SQLiteProfileStore, SQLiteVectorStore
from apps.core.tools_registry import PreferenceToolRegistry


class StubOllamaAdapter:
    def __init__(self) -> None:
        self.calls = 0

    def chat(self, messages, tools=None, options=None):
        self.calls += 1
        if self.calls == 1:
            return {
                "message": {
                    "role": "assistant",
                    "content": "Сохраню предпочтение",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "function": {
                                "name": "save_preference",
                                "arguments": '{"key":"genre","value":"comedy","domain":"cinema"}',
                            },
                        }
                    ],
                }
            }

        return {"message": {"role": "assistant", "content": "Готово, предпочтение сохранено."}}


def test_orchestrator_dispatches_tool_and_adds_reflection_note(tmp_path: Path):
    db_path = tmp_path / "memory.db"
    orchestrator = PEAROrchestrator(
        ollama_adapter=StubOllamaAdapter(),
        tool_registry=PreferenceToolRegistry(preference_store={}),
        profile_repo=SQLiteProfileStore(db_path=str(db_path)),
        preference_repo=SQLitePreferenceStore(db_path=str(db_path)),
        memory=SQLiteVectorStore(db_path=str(db_path)),
    )

    result = orchestrator.handle(user_id="u1", user_message="Хочу комедию", forced_domain="cinema")

    assert result.final_text
    assert result.metadata["tool_call_count"] == 1
    assert result.tool_outputs[0].tool_name == "save_preference"
    assert any("preferences_updated" in json.loads(note) for note in result.notes)


def test_offline_mode_does_not_call_external_api(tmp_path: Path, monkeypatch):
    def fail_request(*args, **kwargs):
        raise AssertionError("External HTTP call was attempted in offline mode")

    monkeypatch.setattr(httpx.Client, "request", fail_request)

    db_path = tmp_path / "memory.db"
    orchestrator = PEAROrchestrator(
        ollama_adapter=StubOllamaAdapter(),
        tool_registry=PreferenceToolRegistry(preference_store={}),
        profile_repo=SQLiteProfileStore(db_path=str(db_path)),
        preference_repo=SQLitePreferenceStore(db_path=str(db_path)),
        memory=SQLiteVectorStore(db_path=str(db_path)),
    )

    result = orchestrator.handle(user_id="u2", user_message="Подбери лук в синем цвете", forced_domain="fashion")

    assert result.final_text
    assert result.metadata["tool_call_count"] == 1
