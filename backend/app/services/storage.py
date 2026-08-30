import json
import sqlite3
from pathlib import Path
from typing import Optional

from app.models.domain import Conversation, HumanReview, Interaction

_DB_PATH = Path(__file__).resolve().parents[3] / "controlplane.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS interactions (
    id TEXT PRIMARY KEY,
    conversation_id TEXT,
    created_at TEXT,
    use_case TEXT,
    decision_action TEXT,
    payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    payload TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_interactions_created ON interactions(created_at);
"""


class Storage:
    """Thin synchronous SQLite wrapper. The prototype's write volume is low
    (demo-scale), so a single connection with WAL mode is sufficient and
    avoids the complexity of an async ORM or a second database."""

    def __init__(self, db_path: Path = _DB_PATH):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def save_interaction(self, interaction: Interaction) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO interactions
               (id, conversation_id, created_at, use_case, decision_action, payload)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                interaction.id,
                interaction.context.conversation_id,
                interaction.created_at.isoformat(),
                interaction.context.use_case.value,
                interaction.decision.action.value if interaction.decision else None,
                interaction.model_dump_json(),
            ),
        )
        self._conn.commit()

    def get_interaction(self, interaction_id: str) -> Optional[Interaction]:
        row = self._conn.execute(
            "SELECT payload FROM interactions WHERE id = ?", (interaction_id,)
        ).fetchone()
        return Interaction.model_validate_json(row[0]) if row else None

    def list_interactions(self, limit: int = 100) -> list[Interaction]:
        rows = self._conn.execute(
            "SELECT payload FROM interactions ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [Interaction.model_validate_json(r[0]) for r in rows]

    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        row = self._conn.execute(
            "SELECT payload FROM conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
        return Conversation.model_validate_json(row[0]) if row else None

    def save_conversation(self, conversation: Conversation) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO conversations (id, payload) VALUES (?, ?)",
            (conversation.id, conversation.model_dump_json()),
        )
        self._conn.commit()

    def clear(self) -> None:
        self._conn.execute("DELETE FROM interactions;")
        self._conn.execute("DELETE FROM conversations;")
        self._conn.commit()


_storage_instance: Optional[Storage] = None


def get_storage() -> Storage:
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = Storage()
    return _storage_instance
