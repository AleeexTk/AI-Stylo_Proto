import json
import os
import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from apps.core.contracts import Profile


class SQLiteProfileStore:
    def __init__(self, db_path: Optional[str] = None, bootstrap_path: Optional[str] = None) -> None:
        project_root = Path(__file__).resolve().parents[3]
        default_db = project_root / "data" / "memory.db"
        default_bootstrap = project_root / "configs" / "sergii_profile.yaml"

        self.db_path = Path(db_path or os.getenv("AI_STYLO_DB_PATH", str(default_db)))
        self.bootstrap_path = Path(bootstrap_path or str(default_bootstrap))
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_profile (
                    user_id TEXT PRIMARY KEY,
                    theme_color TEXT NOT NULL,
                    style_preset TEXT NOT NULL,
                    budget_min REAL NOT NULL,
                    budget_max REAL NOT NULL,
                    affinities_json TEXT NOT NULL,
                    counters_json TEXT NOT NULL,
                    skills_json TEXT NOT NULL,
                    seen_events INTEGER NOT NULL,
                    similarity_history_json TEXT NOT NULL,
                    creativity_level REAL NOT NULL,
                    tone_preference TEXT NOT NULL,
                    preferred_aesthetics_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def _bootstrap_payload(self, user_id: str) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"user_id": user_id}
        if not self.bootstrap_path.exists():
            return payload

        with self.bootstrap_path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

        for field_name in Profile.__dataclass_fields__.keys():
            if field_name == "user_id":
                continue
            if field_name in raw:
                payload[field_name] = raw[field_name]

        return payload

    def get_profile(self, user_id: str) -> Profile:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM user_profile WHERE user_id = ?", (user_id,)).fetchone()

        if row is None:
            bootstrap = self._bootstrap_payload(user_id)
            profile = Profile(**bootstrap)
            self.upsert_profile(profile)
            return profile

        return Profile(
            user_id=row["user_id"],
            theme_color=row["theme_color"],
            style_preset=row["style_preset"],
            budget_min=row["budget_min"],
            budget_max=row["budget_max"],
            affinities=json.loads(row["affinities_json"]),
            counters=json.loads(row["counters_json"]),
            skills=json.loads(row["skills_json"]),
            seen_events=row["seen_events"],
            similarity_history=json.loads(row["similarity_history_json"]),
            creativity_level=row["creativity_level"],
            tone_preference=row["tone_preference"],
            preferred_aesthetics=json.loads(row["preferred_aesthetics_json"]),
        )

    def upsert_profile(self, profile: Profile) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO user_profile (
                    user_id, theme_color, style_preset, budget_min, budget_max,
                    affinities_json, counters_json, skills_json, seen_events,
                    similarity_history_json, creativity_level, tone_preference,
                    preferred_aesthetics_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    theme_color=excluded.theme_color,
                    style_preset=excluded.style_preset,
                    budget_min=excluded.budget_min,
                    budget_max=excluded.budget_max,
                    affinities_json=excluded.affinities_json,
                    counters_json=excluded.counters_json,
                    skills_json=excluded.skills_json,
                    seen_events=excluded.seen_events,
                    similarity_history_json=excluded.similarity_history_json,
                    creativity_level=excluded.creativity_level,
                    tone_preference=excluded.tone_preference,
                    preferred_aesthetics_json=excluded.preferred_aesthetics_json,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    profile.user_id,
                    profile.theme_color,
                    profile.style_preset,
                    profile.budget_min,
                    profile.budget_max,
                    json.dumps(profile.affinities, ensure_ascii=False),
                    json.dumps(profile.counters, ensure_ascii=False),
                    json.dumps(profile.skills, ensure_ascii=False),
                    profile.seen_events,
                    json.dumps(profile.similarity_history, ensure_ascii=False),
                    profile.creativity_level,
                    profile.tone_preference,
                    json.dumps(profile.preferred_aesthetics, ensure_ascii=False),
                ),
            )

    def update_profile_fields(self, user_id: str, updates: Dict[str, Any]) -> Profile:
        current = asdict(self.get_profile(user_id))
        current.update(updates)
        current["user_id"] = user_id
        profile = Profile(**current)
        self.upsert_profile(profile)
        return profile

    def delete_profile(self, user_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM user_profile WHERE user_id = ?", (user_id,))
