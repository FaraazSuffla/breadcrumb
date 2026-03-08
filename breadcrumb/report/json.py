"""JSON report for Breadcrumb healing statistics."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from breadcrumb.core.storage import FingerprintStore


def _table_exists(store: FingerprintStore, name: str) -> bool:
    """Check whether a table exists in the SQLite database."""
    conn = store._get_conn()
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return row is not None


class ReportJSON:
    """Render a JSON report from the Breadcrumb database."""

    def render(self, store: FingerprintStore, days: int = 30) -> dict[str, Any]:
        """Build and return a report dict."""
        conn = store._get_conn()
        now = time.time()
        cutoff = now - days * 86400

        has_test_runs = _table_exists(store, "test_runs")
        has_quarantine = _table_exists(store, "quarantine")

        # --- Counts ---
        if has_test_runs:
            total = _scalar(
                conn,
                "SELECT COUNT(DISTINCT test_id) FROM test_runs WHERE timestamp >= ?",
                (cutoff,),
            )
        else:
            total = _scalar(
                conn,
                "SELECT COUNT(DISTINCT test_id) FROM healing_events WHERE timestamp >= ?",
                (cutoff,),
            )

        healed = _scalar(
            conn,
            "SELECT COUNT(DISTINCT test_id) FROM healing_events WHERE timestamp >= ?",
            (cutoff,),
        )

        if has_quarantine:
            flaky = _scalar(conn, "SELECT COUNT(*) FROM quarantine")
        else:
            flaky = 0

        if has_test_runs:
            failing_rows = conn.execute(
                """
                SELECT test_id FROM test_runs t1
                WHERE timestamp >= ?
                  AND timestamp = (
                      SELECT MAX(t2.timestamp) FROM test_runs t2
                      WHERE t2.test_id = t1.test_id AND t2.timestamp >= ?
                  )
                  AND status = 'failed'
                GROUP BY test_id
                """,
                (cutoff, cutoff),
            ).fetchall()
            failing = len(failing_rows)
        else:
            failing = 0

        # Stable
        healed_ids = {
            r[0]
            for r in conn.execute(
                "SELECT DISTINCT test_id FROM healing_events WHERE timestamp >= ?",
                (cutoff,),
            ).fetchall()
        }
        failing_ids: set[str] = set()
        if has_test_runs:
            failing_ids = {
                r[0]
                for r in conn.execute(
                    """
                    SELECT test_id FROM test_runs t1
                    WHERE timestamp >= ?
                      AND timestamp = (
                          SELECT MAX(t2.timestamp) FROM test_runs t2
                          WHERE t2.test_id = t1.test_id AND t2.timestamp >= ?
                      )
                      AND status = 'failed'
                    GROUP BY test_id
                    """,
                    (cutoff, cutoff),
                ).fetchall()
            }
        flaky_ids: set[str] = set()
        if has_quarantine:
            flaky_ids = {r[0] for r in conn.execute("SELECT test_id FROM quarantine").fetchall()}

        stable = max(0, total - len(healed_ids | failing_ids | flaky_ids))

        # --- Healing events ---
        event_rows = conn.execute(
            """
            SELECT timestamp, test_id, locator, confidence,
                   original_json, healed_json
            FROM healing_events WHERE timestamp >= ?
            ORDER BY timestamp DESC
            """,
            (cutoff,),
        ).fetchall()
        healing_events: list[dict[str, Any]] = []
        for r in event_rows:
            healing_events.append(
                {
                    "timestamp": r[0],
                    "test_id": r[1],
                    "locator": r[2],
                    "confidence": r[3],
                    "original": json.loads(r[4]),
                    "healed": json.loads(r[5]),
                }
            )

        # --- Top locators ---
        top_rows = conn.execute(
            """
            SELECT test_id, locator, COUNT(*) as cnt,
                   AVG(confidence) as avg_conf
            FROM healing_events WHERE timestamp >= ?
            GROUP BY test_id, locator ORDER BY cnt DESC LIMIT 5
            """,
            (cutoff,),
        ).fetchall()
        top_locators: list[dict[str, Any]] = []
        for r in top_rows:
            top_locators.append(
                {
                    "test_id": r[0],
                    "locator": r[1],
                    "count": r[2],
                    "avg_confidence": round(r[3], 4),
                }
            )

        # --- Flaky tests ---
        flaky_tests: list[dict[str, Any]] = []
        if has_quarantine and has_test_runs:
            quarantined = conn.execute("SELECT test_id, reason FROM quarantine").fetchall()
            for q in quarantined:
                q_id = q[0]
                q_reason = q[1]
                runs = conn.execute(
                    "SELECT status FROM test_runs WHERE test_id = ? AND timestamp >= ? ORDER BY timestamp ASC",
                    (q_id, cutoff),
                ).fetchall()
                fliprate = _compute_fliprate(runs)
                flaky_tests.append(
                    {
                        "test_id": q_id,
                        "reason": q_reason,
                        "fliprate": round(fliprate, 4),
                    }
                )
        elif has_quarantine:
            quarantined = conn.execute("SELECT test_id, reason FROM quarantine").fetchall()
            for q in quarantined:
                flaky_tests.append(
                    {
                        "test_id": q[0],
                        "reason": q[1],
                        "fliprate": 0.0,
                    }
                )

        return {
            "generated_at": now,
            "period_days": days,
            "summary": {
                "total": total,
                "stable": stable,
                "healed": healed,
                "flaky": flaky,
                "failing": failing,
            },
            "healing_events": healing_events,
            "flaky_tests": flaky_tests,
            "top_locators": top_locators,
        }

    def export(self, store: FingerprintStore, path: str | Path, days: int = 30) -> None:
        """Write the JSON report to a file."""
        data = self.render(store, days)
        Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")


def _scalar(conn: object, sql: str, params: tuple[object, ...] = ()) -> int:
    """Execute a query returning a single int."""
    row = conn.execute(sql, params).fetchone()  # type: ignore[union-attr]
    return int(row[0]) if row else 0


def _compute_fliprate(runs: list[object]) -> float:
    """Compute the flip rate: fraction of adjacent status changes."""
    if len(runs) < 2:
        return 0.0
    flips = sum(
        1
        for i in range(1, len(runs))
        if runs[i][0] != runs[i - 1][0]  # type: ignore[index]
    )
    return flips / (len(runs) - 1)
