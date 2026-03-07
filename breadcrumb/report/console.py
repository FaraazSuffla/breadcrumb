"""Console (plain-text) report for Breadcrumb healing statistics."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

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


class ReportConsole:
    """Render a plain-text health summary from the Breadcrumb database."""

    def render(self, store: FingerprintStore, days: int = 30) -> str:
        """Build and return the console report string."""
        conn = store._get_conn()
        cutoff = time.time() - days * 86400

        has_test_runs = _table_exists(store, "test_runs")
        has_quarantine = _table_exists(store, "quarantine")

        # --- Total tests ---
        if has_test_runs:
            row = conn.execute(
                "SELECT COUNT(DISTINCT test_id) FROM test_runs WHERE timestamp >= ?",
                (cutoff,),
            ).fetchone()
            total = row[0] if row else 0
        else:
            row = conn.execute(
                "SELECT COUNT(DISTINCT test_id) FROM healing_events WHERE timestamp >= ?",
                (cutoff,),
            ).fetchone()
            total = row[0] if row else 0

        # --- Healed tests ---
        row = conn.execute(
            "SELECT COUNT(DISTINCT test_id) FROM healing_events WHERE timestamp >= ?",
            (cutoff,),
        ).fetchone()
        healed = row[0] if row else 0

        # --- Flaky tests ---
        if has_quarantine:
            row = conn.execute("SELECT COUNT(*) FROM quarantine").fetchone()
            flaky = row[0] if row else 0
        else:
            flaky = 0

        # --- Failing tests ---
        if has_test_runs:
            # Tests whose most recent run in the window has status='failed'
            rows = conn.execute(
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
            failing = len(rows)
        else:
            failing = 0

        # --- Stable ---
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
            flaky_ids = {
                r[0]
                for r in conn.execute("SELECT test_id FROM quarantine").fetchall()
            }

        unstable = healed_ids | failing_ids | flaky_ids
        stable = max(0, total - len(unstable))

        # --- Percentages ---
        def pct(n: int) -> str:
            if total == 0:
                return "0.0%"
            return f"{n / total * 100:.1f}%"

        lines: list[str] = []
        lines.append(f"Test Health Summary (last {days} days)")
        lines.append(f"Total tests: {total}")
        lines.append(f"Stable: {stable} ({pct(stable)})")
        lines.append(f"Healed: {healed} ({pct(healed)})")
        lines.append(f"Flaky: {flaky} ({pct(flaky)})")
        lines.append(f"Failing: {failing} ({pct(failing)})")

        # --- Top healed locators ---
        top_rows = conn.execute(
            """
            SELECT test_id, locator, COUNT(*) as cnt, AVG(confidence) as avg_conf
            FROM healing_events
            WHERE timestamp >= ?
            GROUP BY test_id, locator
            ORDER BY cnt DESC
            LIMIT 5
            """,
            (cutoff,),
        ).fetchall()

        if top_rows:
            lines.append("")
            lines.append("Top healed locators:")
            for r in top_rows:
                locator_val = r[1]
                cnt = r[2]
                avg_conf = r[3]
                label = str(locator_val)
                lines.append(
                    f"  {label:<20s} healed {cnt}x  avg confidence: {avg_conf:.2f}"
                )

        # --- Flaky tests section ---
        if has_quarantine and has_test_runs:
            quarantined = conn.execute(
                "SELECT test_id, reason FROM quarantine"
            ).fetchall()
            if quarantined:
                lines.append("")
                lines.append("Flaky tests:")
                for q in quarantined:
                    q_test_id = q[0]
                    runs = conn.execute(
                        """
                        SELECT status FROM test_runs
                        WHERE test_id = ? AND timestamp >= ?
                        ORDER BY timestamp ASC
                        """,
                        (q_test_id, cutoff),
                    ).fetchall()
                    fliprate = _compute_fliprate(runs)
                    classification = _classify_fliprate(fliprate)
                    lines.append(
                        f"  {q_test_id:<20s} fliprate: {fliprate:.2f}"
                        f"  status: {classification}"
                    )

        return "\n".join(lines) + "\n"


def _compute_fliprate(runs: list[object]) -> float:
    """Compute the flip rate: fraction of adjacent status changes."""
    if len(runs) < 2:
        return 0.0
    flips = 0
    for i in range(1, len(runs)):
        if runs[i][0] != runs[i - 1][0]:  # type: ignore[index]
            flips += 1
    return flips / (len(runs) - 1)


def _classify_fliprate(fliprate: float) -> str:
    """Classify a test by its flip rate."""
    if fliprate >= 0.3:
        return "Flaky"
    if fliprate >= 0.1:
        return "Intermittent"
    return "Stable"
