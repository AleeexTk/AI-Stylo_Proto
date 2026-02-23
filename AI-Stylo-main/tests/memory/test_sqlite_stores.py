from pathlib import Path

from apps.core.memory import SQLitePreferenceStore, SQLiteProfileStore, SQLiteVectorStore


def test_preference_store_persists_and_updates_values(tmp_path: Path):
    store = SQLitePreferenceStore(db_path=str(tmp_path / "memory.db"))

    store.set_preference("u1", "tone", "concise")
    store.upsert_preferences("u1", {"genre": "comedy"})

    prefs = store.get_preferences("u1")
    assert prefs["tone"] == "concise"
    assert prefs["genre"] == "comedy"


def test_vector_store_notes_and_vectors_roundtrip(tmp_path: Path):
    store = SQLiteVectorStore(db_path=str(tmp_path / "memory.db"))

    store.add_note("u1", "note-1")
    store.add_note("u1", "note-2")
    notes = store.get_recent("u1", limit=2)

    store.upsert_vector("u1", "session", "item-1", [0.1, 0.2], {"tag": "x"})
    vector = store.get_vector("u1", "session", "item-1")

    assert notes == ["note-1", "note-2"]
    assert vector == {"vector": [0.1, 0.2], "metadata": {"tag": "x"}}


def test_profile_store_bootstraps_and_updates_profile(tmp_path: Path):
    bootstrap = tmp_path / "profile.yaml"
    bootstrap.write_text("style_preset: minimal\nbudget_min: 100\nbudget_max: 900\n", encoding="utf-8")

    store = SQLiteProfileStore(db_path=str(tmp_path / "memory.db"), bootstrap_path=str(bootstrap))
    profile = store.get_profile("u1")
    updated = store.update_profile_fields("u1", {"style_preset": "street"})

    assert profile.style_preset == "minimal"
    assert updated.style_preset == "street"
