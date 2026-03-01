import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional


class SQLitePreferenceStore:
    def __init__(self, db_path: Optional[str] = None) -> None:
        project_root = Path(__file__).resolve().parents[3]
        default_db = project_root / "data" / "memory.db"
        self.db_path = Path(db_path or os.getenv("AI_STYLO_DB_PATH", str(default_db)))
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
                CREATE TABLE IF NOT EXISTS user_preferences (
                    user_id TEXT NOT NULL,
                    pref_key TEXT NOT NULL,
                    pref_value_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, pref_key)
                )
                """
            )

    def get_preferences(self, user_id: str) -> Dict[str, Any]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT pref_key, pref_value_json FROM user_preferences WHERE user_id = ?",
                (user_id,),
            ).fetchall()

        return {row["pref_key"]: json.loads(row["pref_value_json"]) for row in rows}

    def set_preference(self, user_id: str, key: str, value: Any) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO user_preferences (user_id, pref_key, pref_value_json)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, pref_key) DO UPDATE SET
                    pref_value_json=excluded.pref_value_json,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (user_id, key, json.dumps(value, ensure_ascii=False)),
            )

    def upsert_preferences(self, user_id: str, preferences: Dict[str, Any]) -> None:
        for key, value in preferences.items():
            self.set_preference(user_id=user_id, key=key, value=value)

    def delete_preference(self, user_id: str, key: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM user_preferences WHERE user_id = ? AND pref_key = ?",
                (user_id, key),
            )

    def clear_preferences(self, user_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM user_preferences WHERE user_id = ?", (user_id,))
