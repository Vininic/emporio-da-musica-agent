import json
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT, state TEXT
);
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id TEXT, kind TEXT, summary TEXT,
    contact TEXT, created_at TEXT
);
"""


class Journal:
    def __init__(self, path: Path | None = None):
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path or ":memory:", check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.executescript(SCHEMA)
        self._lock = threading.Lock()

    def new_conversation(self, now: datetime) -> str:
        conversation_id = uuid.uuid4().hex
        self.save_state(conversation_id, {}, now)
        return conversation_id

    def save_state(self, conversation_id: str, state: dict, now: datetime) -> None:
        with self._lock:
            self._db.execute(
                """
                INSERT INTO conversations (id, created_at, updated_at, state) VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET updated_at = excluded.updated_at, state = excluded.state
                """,
                (conversation_id, now.isoformat(), now.isoformat(), json.dumps(state)),
            )
            self._db.commit()

    def load_state(self, conversation_id: str) -> dict | None:
        row = self._db.execute(
            "SELECT state FROM conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
        return json.loads(row["state"]) if row else None

    def open_ticket(
        self, conversation_id: str, kind: str, summary: str, contact: str | None, now: datetime
    ) -> int:
        with self._lock:
            cursor = self._db.execute(
                """
                INSERT INTO tickets (conversation_id, kind, summary, contact, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (conversation_id, kind, summary, contact, now.isoformat()),
            )
            self._db.commit()
            return cursor.lastrowid

    def tickets(self) -> list[dict]:
        return [dict(row) for row in self._db.execute("SELECT * FROM tickets ORDER BY id")]
