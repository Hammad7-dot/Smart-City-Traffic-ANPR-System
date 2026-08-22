# implements FR6, rules.md #10 (schema.sql is source of truth), D-008 (dedupe)
"""SQLite persistence for vehicle crossing events."""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "database" / "schema.sql"
DEDUPE_WINDOW_SECONDS = 5


class EventStore:
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(SCHEMA_PATH.read_text())
        self.conn.commit()

    def _is_recent_duplicate(self, plate_number: str, event_timestamp: str) -> bool:
        if not plate_number:
            return False
        cutoff = (
            datetime.fromisoformat(event_timestamp) - timedelta(seconds=DEDUPE_WINDOW_SECONDS)
        ).isoformat()
        row = self.conn.execute(
            "SELECT 1 FROM vehicle_events WHERE plate_number = ? AND event_timestamp >= ? LIMIT 1",
            (plate_number, cutoff),
        ).fetchone()
        return row is not None

    def record_event(
        self,
        track_id: int,
        vehicle_type: str,
        plate_number: str | None,
        ocr_confidence: float,
        is_low_confidence: bool,
        frame_number: int,
        event_timestamp: str,
    ) -> bool:
        """Writes one row atomically. Returns False if skipped as a duplicate (D-008)."""
        if self._is_recent_duplicate(plate_number, event_timestamp):
            return False
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO vehicle_events
                    (track_id, vehicle_type, plate_number, ocr_confidence,
                     is_low_confidence, frame_number, event_timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    track_id,
                    vehicle_type,
                    plate_number,
                    ocr_confidence,
                    int(is_low_confidence),
                    frame_number,
                    event_timestamp,
                ),
            )
        return True

    def purge_older_than(self, days: int) -> int:
        """Deletes vehicle_events rows older than `days` (D-024 retention policy). Returns rows deleted."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        with self.conn:
            cur = self.conn.execute("DELETE FROM vehicle_events WHERE event_timestamp < ?", (cutoff,))
        return cur.rowcount

    def close(self):
        self.conn.close()
