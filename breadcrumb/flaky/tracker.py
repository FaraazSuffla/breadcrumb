"""Test execution history tracker.

Records pass/fail/duration/healing data per test run into the SQLite DB.
Extends the schema to v2 with test_runs and quarantine tables.
"""

from __future__ import annotations

import time
from typing import Any

from breadcrumb.core.storage import FingerprintStore

_V2_TABLES_SQL = """\
CREATE TABLE IF NOT EXISTS test_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    test_id TEXT NOT NULL,
    status TEXT NOT NULL,
    duration_ms REAL,
    healing_occurred INTEGER NOT NULL DEFAULT 0,
    error_type TEXT,
    environment TEXT,
    timestamp REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_test_runs_test_id ON test_runs (test_id);
CREATE INDEX IF NOT EXISTS idx_test_runs_timestamp ON test_runs (timestamp);

CREATE TABLE IF NOT EXISTS quarantine (
    test_id TEXT PRIMARY KEY,
    reason TEXT NOT NULL,
    quarantined_at REAL NOT NULL,
    auto_unquarantine INTEGER NOT NULL DEFAULT 1
);
"""


def migrate_schema(store: FingerprintStore) -> None:
    """Migrate a v1 DB to v2 by adding test_runs and quarantine tables.

    Safe to call multiple times — CREATE IF NOT EXISTS guards are used.
    """
    conn = store._get_conn()
    conn.executescript(_V2_TABLES_SQL)

    row = conn.execute(
        "SELECT value FROM schema_meta WHERE key = 'schema_version'",
    ).fetchone()
    current_version = int(row[0]) if row else 1

    if current_version < 2:
        conn.execute(
            "INSERT OR REPLACE INTO schema_meta (key, value) VALUES ('schema_version', '2')",
        )
        conn.commit()


class TestTracker:
    """Records test execution runs into the SQLite database.

    Usage::

        tracker = TestTracker(store)
        tracker.record_run("test_login", "passed", duration_ms=120.5)
        tracker.record_run("test_login", "failed", error_type="AssertionError")
        runs = tracker.get_runs("test_login")
    """

    def __init__(self, store: FingerprintStore) -> None:
        self._store = store
        migrate_schema(store)

    def record_run(
        self,
        test_id: str,
        status: str,
        duration_ms: float | None = None,
        healing_occurred: bool = False,
        error_type: str | None = None,
        environment: str | None = None,
    ) -> None:
        """Record a test execution result.

        Args:
            test_id: Unique test identifier (e.g. pytest node ID).
            status: One of 'passed', 'failed', 'error', 'skipped'.
            duration_ms: Test duration in milliseconds.
            healing_occurred: Whether self-healing was triggered.
            error_type: Exception class name if the test errored.
            environment: Optional environment tag (e.g. 'ci', 'local').
        """
        conn = self._store._get_conn()
        conn.execute(
            "INSERT INTO test_runs "
            "(test_id, status, duration_ms, healing_occurred, error_type, environment, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                test_id,
                status,
                duration_ms,
                1 if healing_occurred else 0,
                error_type,
                environment,
                time.time(),
            ),
        )
        conn.commit()

    def get_runs(self, test_id: str, limit: int = 100) -> list[dict[str, Any]]:
        """Return recent runs for a test, ordered by timestamp descending."""
        conn = self._store._get_conn()
        rows = conn.execute(
            "SELECT id, test_id, status, duration_ms, healing_occurred, "
            "error_type, environment, timestamp "
            "FROM test_runs WHERE test_id = ? ORDER BY timestamp DESC LIMIT ?",
            (test_id, limit),
        ).fetchall()
        return [
            {
                "id": r[0],
                "test_id": r[1],
                "status": r[2],
                "duration_ms": r[3],
                "healing_occurred": bool(r[4]),
                "error_type": r[5],
                "environment": r[6],
                "timestamp": r[7],
            }
            for r in rows
        ]

    def get_all_test_ids(self) -> list[str]:
        """Return distinct test_ids that have at least one recorded run."""
        conn = self._store._get_conn()
        rows = conn.execute(
            "SELECT DISTINCT test_id FROM test_runs ORDER BY test_id",
        ).fetchall()
        return [r[0] for r in rows]
