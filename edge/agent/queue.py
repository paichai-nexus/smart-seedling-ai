from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


@dataclass(frozen=True)
class QueuedCapture:
    id: int
    image_path: str
    sha256: str
    metadata: dict
    attempts: int


class CaptureQueue:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS capture_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    image_path TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('pending', 'sent')) DEFAULT 'pending',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    next_attempt_at TEXT NOT NULL,
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    sent_at TEXT,
                    UNIQUE(sha256, metadata_json)
                );
                CREATE INDEX IF NOT EXISTS capture_queue_due
                ON capture_queue(status, next_attempt_at);
                """
            )

    def enqueue(self, image_path: str | Path, metadata: dict, now: datetime) -> int:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must include a timezone offset")
        path = Path(image_path)
        if not path.is_file():
            raise ValueError("capture image does not exist")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        metadata_json = json.dumps(metadata, sort_keys=True, separators=(",", ":"))
        queued_at = now.astimezone(timezone.utc).isoformat()
        with self.connect() as connection:
            cursor = connection.execute(
                """INSERT INTO capture_queue(
                       image_path, sha256, metadata_json, next_attempt_at, created_at
                   ) VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(sha256, metadata_json) DO NOTHING""",
                (str(path), digest, metadata_json, queued_at, queued_at),
            )
            if cursor.lastrowid:
                return cursor.lastrowid
            row = connection.execute(
                "SELECT id FROM capture_queue WHERE sha256 = ? AND metadata_json = ?",
                (digest, metadata_json),
            ).fetchone()
            return row["id"]

    def due(self, now: datetime, limit: int = 20) -> list[QueuedCapture]:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must include a timezone offset")
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT id, image_path, sha256, metadata_json, attempts
                   FROM capture_queue
                   WHERE status = 'pending' AND next_attempt_at <= ?
                   ORDER BY created_at, id LIMIT ?""",
                (now.astimezone(timezone.utc).isoformat(), limit),
            ).fetchall()
        return [
            QueuedCapture(
                id=row["id"],
                image_path=row["image_path"],
                sha256=row["sha256"],
                metadata=json.loads(row["metadata_json"]),
                attempts=row["attempts"],
            )
            for row in rows
        ]

    def mark_sent(self, capture_id: int, sent_at: datetime) -> None:
        self._require_aware(sent_at)
        with self.connect() as connection:
            connection.execute(
                """UPDATE capture_queue SET status = 'sent', sent_at = ?, last_error = NULL
                   WHERE id = ?""",
                (sent_at.astimezone(timezone.utc).isoformat(), capture_id),
            )

    def mark_failed(self, capture_id: int, error: str, failed_at: datetime) -> datetime:
        self._require_aware(failed_at)
        with self.connect() as connection:
            row = connection.execute(
                "SELECT attempts FROM capture_queue WHERE id = ?", (capture_id,)
            ).fetchone()
            if row is None:
                raise ValueError("capture queue item not found")
            attempts = row["attempts"] + 1
            delay_seconds = min(30 * (2 ** (attempts - 1)), 3600)
            retry_at = failed_at.astimezone(timezone.utc) + timedelta(seconds=delay_seconds)
            connection.execute(
                """UPDATE capture_queue
                   SET attempts = ?, next_attempt_at = ?, last_error = ? WHERE id = ?""",
                (attempts, retry_at.isoformat(), error[:1000], capture_id),
            )
        return retry_at

    def pending_count(self) -> int:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM capture_queue WHERE status = 'pending'"
            ).fetchone()
        return row["count"]

    @staticmethod
    def _require_aware(value: datetime) -> None:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone offset")
