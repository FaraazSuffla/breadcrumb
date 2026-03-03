"""SQLite storage layer for element fingerprints and healing events.

Design decisions (from blueprint):
    - SQLite with WAL mode: zero infrastructure, portable, fast concurrent reads.
    - Single .breadcrumb.db file per project, created automatically on first use.
    - Fingerprints keyed by (test_id, locator) -- each test+locator pair stores
      one canonical fingerprint that gets updated on passing runs.
    - Healing events are append-only: every heal is recorded for reporting.
    - Schema versioning via a metadata table for future migrations.
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from breadcrumb.core.fingerprint import ElementFingerprint

SCHEMA_VERSION = 1
DEFAULT_DB_PATH = ".breadcrumb.db"

_CREATE_TABLES_SQL = """\
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fingerprints (
    test_id TEXT NOT NULL,
    locator TEXT NOT NULL,
    fingerprint_json TEXT NOT NULL,
    updated_at REAL NOT NULL,
    PRIMARY KEY (test_id, locator)
);

CREATE TABLE IF NOT EXISTS healing_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    test_id TEXT NOT NULL,
    locator TEXT NOT NULL,
    confidence REAL NOT NULL,
    original_json TEXT NOT NULL,
    healed_json TEXT NOT NULL,
    timestamp REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_healing_test
    ON healing_events (test_id);

CREATE INDEX IF NOT EXISTS idx_healing_locator
    ON healing_events (test_id, locator);
"""


@dataclass
class HealingEvent:
    """Record of a single healing occurrence."""

    test_id: str
    locator: str
    confidence: float
    original_fingerprint: dict[str, Any]
    healed_fingerprint: dict[str, Any]
    timestamp: float


class FingerprintStore:
    """SQLite-backed storage for fingerprints and healing events.

    Usage::

        store = FingerprintStore()          # Uses .breadcrumb.db in cwd
        store = FingerprintStore("path/to/db.sqlite")
        store.save_fingerprint(fingerprint)
        fp = store.load_fingerprint("test_login", "#login-btn")

    The database is created automatically on first access.
    """

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self._db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None
        self._ensure_db()

    @property
    def db_path(self) -> Path:
        """Return the path to the database file."""
        return self._db_path

    def _get_conn(self) -> sqlite3.Connection:
        """Get or create the database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self._db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def _ensure_db(self) -> None:
        """Create tables if they don't exist."""
        conn = self._get_conn()
        conn.executescript(_CREATE_TABLES_SQL)

        row = conn.execute(
            "SELECT value FROM schema_meta WHERE key = 'schema_version'",
        ).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO schema_meta (key, value) VALUES ('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )
            conn.commit()

    def save_fingerprint(self, fingerprint: ElementFingerprint) -> None:
        """Save or update a fingerprint for a (test_id, locator) pair.

        Called on passing test runs to keep the fingerprint database current.

        Raises:
            ValueError: If test_id or locator is empty.
        """
        if not fingerprint.test_id:
            msg = "Fingerprint must have a test_id to be stored."
            raise ValueError(msg)
        if not fingerprint.locator:
            msg = "Fingerprint must have a locator to be stored."
            raise ValueError(msg)

        conn = self._get_conn()
        conn.execute(
            "INSERT INTO fingerprints (test_id, locator, fingerprint_json, updated_at) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT (test_id, locator) "
            "DO UPDATE SET fingerprint_json = excluded.fingerprint_json, "
            "             updated_at = excluded.updated_at",
            (
                fingerprint.test_id,
                fingerprint.locator,
                json.dumps(fingerprint.to_dict()),
                time.time(),
            ),
        )
        conn.commit()

    def load_fingerprint(self, test_id: str, locator: str) -> ElementFingerprint | None:
        """Load a stored fingerprint for a (test_id, locator) pair.

        Returns None if not found.
        """
        conn = self._get_conn()
        row = conn.execute(
            "SELECT fingerprint_json FROM fingerprints WHERE test_id = ? AND locator = ?",
            (test_id, locator),
        ).fetchone()

        if row is None:
            return None

        data: dict[str, Any] = json.loads(row[0])  # type: ignore[index]
        return ElementFingerprint.from_dict(data)

    def record_healing(self, event: HealingEvent) -> None:
        """Record a healing event. Append-only for reporting."""
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO healing_events "
            "(test_id, locator, confidence, original_json, healed_json, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                event.test_id,
                event.locator,
                event.confidence,
                json.dumps(event.original_fingerprint),
                json.dumps(event.healed_fingerprint),
                event.timestamp,
            ),
        )
        conn.commit()

    def get_healing_events(
        self,
        test_id: str | None = None,
        locator: str | None = None,
    ) -> list[HealingEvent]:
        """Query healing events, optionally filtered by test and/or locator.

        Returns list ordered by timestamp descending.
        """
        conn = self._get_conn()
        query = "SELECT * FROM healing_events"
        params: list[str] = []
        conditions: list[str] = []

        if test_id is not None:
            conditions.append("test_id = ?")
            params.append(test_id)
        if locator is not None:
            conditions.append("locator = ?")
            params.append(locator)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY timestamp DESC"

        rows = conn.execute(query, params).fetchall()
        return [
            HealingEvent(
                test_id=r["test_id"],  # type: ignore[index]
                locator=r["locator"],  # type: ignore[index]
                confidence=r["confidence"],  # type: ignore[index]
                original_fingerprint=json.loads(r["original_json"]),  # type: ignore[index]
                healed_fingerprint=json.loads(r["healed_json"]),  # type: ignore[index]
                timestamp=r["timestamp"],  # type: ignore[index]
            )
            for r in rows
        ]

    def get_all_fingerprints(self) -> list[ElementFingerprint]:
        """Load all stored fingerprints."""
        conn = self._get_conn()
        rows = conn.execute("SELECT fingerprint_json FROM fingerprints").fetchall()
        return [
            ElementFingerprint.from_dict(json.loads(r[0]))  # type: ignore[index]
            for r in rows
        ]

    def delete_fingerprint(self, test_id: str, locator: str) -> bool:
        """Delete a stored fingerprint. Returns True if found and deleted."""
        conn = self._get_conn()
        cursor = conn.execute(
            "DELETE FROM fingerprints WHERE test_id = ? AND locator = ?",
            (test_id, locator),
        )
        conn.commit()
        return cursor.rowcount > 0

    def clear(self) -> None:
        """Delete all fingerprints and healing events."""
        conn = self._get_conn()
        conn.execute("DELETE FROM fingerprints")
        conn.execute("DELETE FROM healing_events")
        conn.commit()

    def stats(self) -> dict[str, int]:
        """Return counts of fingerprints and healing events."""
        conn = self._get_conn()
        fp_row = conn.execute("SELECT COUNT(*) FROM fingerprints").fetchone()
        he_row = conn.execute("SELECT COUNT(*) FROM healing_events").fetchone()
        fp_count: int = fp_row[0] if fp_row is not None else 0  # type: ignore[index]
        he_count: int = he_row[0] if he_row is not None else 0  # type: ignore[index]
        return {"fingerprints": fp_count, "healing_events": he_count}

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
