import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional


class SQLiteVectorStore:
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
                CREATE TABLE IF NOT EXISTS session_notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    note TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_vectors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    namespace TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    vector_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, namespace, item_id)
                )
                """
            )

    # Session notes CRUD
    def get_recent(self, user_id: str, limit: int = 5) -> List[str]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT note FROM session_notes
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()

        return [row["note"] for row in reversed(rows)]

    def add_note(self, user_id: str, note: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO session_notes (user_id, note) VALUES (?, ?)",
                (user_id, note),
            )

    def delete_note(self, note_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM session_notes WHERE id = ?", (note_id,))

    # Minimal vector interface (sqlite-only)
    def upsert_vector(
        self,
        user_id: str,
        namespace: str,
        item_id: str,
        vector: List[float],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO memory_vectors (user_id, namespace, item_id, vector_json, metadata_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id, namespace, item_id) DO UPDATE SET
                    vector_json=excluded.vector_json,
                    metadata_json=excluded.metadata_json,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    user_id,
                    namespace,
                    item_id,
                    json.dumps(vector),
                    json.dumps(metadata or {}, ensure_ascii=False),
                ),
            )

    def get_vector(self, user_id: str, namespace: str, item_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT vector_json, metadata_json
                FROM memory_vectors
                WHERE user_id = ? AND namespace = ? AND item_id = ?
                """,
                (user_id, namespace, item_id),
            ).fetchone()

        if row is None:
            return None

        return {
            "vector": json.loads(row["vector_json"]),
            "metadata": json.loads(row["metadata_json"]),
        }

    def delete_vector(self, user_id: str, namespace: str, item_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM memory_vectors WHERE user_id = ? AND namespace = ? AND item_id = ?",
                (user_id, namespace, item_id),
            )
