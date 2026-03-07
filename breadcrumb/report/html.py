"""HTML dashboard report for Breadcrumb healing statistics."""

from __future__ import annotations

import html
import time
from datetime import datetime, timezone
from pathlib import Path
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


_CSS = """\
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
       background: #f5f7fa; color: #333; padding: 2rem; }
h1 { margin-bottom: 1.5rem; color: #1a1a2e; }
h2 { margin: 1.5rem 0 0.75rem; color: #16213e; }
.cards { display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 1.5rem; }
.card { background: #fff; border-radius: 8px; padding: 1.25rem 1.5rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1); min-width: 140px; flex: 1; }
.card .label { font-size: 0.85rem; color: #666; text-transform: uppercase;
               letter-spacing: 0.05em; }
.card .value { font-size: 1.75rem; font-weight: 700; margin-top: 0.25rem; }
.card.stable .value { color: #27ae60; }
.card.healed .value { color: #2980b9; }
.card.flaky .value { color: #f39c12; }
.card.failing .value { color: #e74c3c; }
table { width: 100%; border-collapse: collapse; background: #fff;
        border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        margin-bottom: 1.5rem; }
th { background: #1a1a2e; color: #fff; text-align: left; padding: 0.75rem 1rem;
     font-weight: 600; font-size: 0.85rem; text-transform: uppercase;
     letter-spacing: 0.05em; }
td { padding: 0.6rem 1rem; border-bottom: 1px solid #eee; font-size: 0.9rem; }
tr:last-child td { border-bottom: none; }
tr:hover td { background: #f0f4ff; }
.empty { color: #999; font-style: italic; padding: 1rem; }
footer { margin-top: 2rem; color: #999; font-size: 0.8rem; }
"""


class ReportHTML:
    """Render an HTML dashboard from the Breadcrumb database."""

    def render(self, store: FingerprintStore, days: int = 30) -> str:
        """Build and return a complete HTML string."""
        conn = store._get_conn()
        cutoff = time.time() - days * 86400

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
            flaky_ids = {
                r[0]
                for r in conn.execute("SELECT test_id FROM quarantine").fetchall()
            }

        stable = max(0, total - len(healed_ids | failing_ids | flaky_ids))

        # --- Top healed locators ---
        top_locators = conn.execute(
            """
            SELECT test_id, locator, COUNT(*) as cnt, AVG(confidence) as avg_conf
            FROM healing_events WHERE timestamp >= ?
            GROUP BY test_id, locator ORDER BY cnt DESC LIMIT 5
            """,
            (cutoff,),
        ).fetchall()

        # --- Recent healing events ---
        recent_events = conn.execute(
            """
            SELECT timestamp, test_id, locator, confidence
            FROM healing_events WHERE timestamp >= ?
            ORDER BY timestamp DESC LIMIT 20
            """,
            (cutoff,),
        ).fetchall()

        # --- Flaky tests ---
        flaky_tests: list[tuple[str, float, str]] = []
        if has_quarantine and has_test_runs:
            quarantined = conn.execute(
                "SELECT test_id FROM quarantine"
            ).fetchall()
            for q in quarantined:
                q_id = q[0]
                runs = conn.execute(
                    "SELECT status FROM test_runs "
                    "WHERE test_id = ? AND timestamp >= ? "
                    "ORDER BY timestamp ASC",
                    (q_id, cutoff),
                ).fetchall()
                fliprate = _compute_fliprate(runs)
                classification = _classify_fliprate(fliprate)
                flaky_tests.append((q_id, fliprate, classification))

        # --- Build HTML ---
        now_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        parts: list[str] = []
        parts.append("<!DOCTYPE html>")
        parts.append('<html lang="en"><head><meta charset="utf-8">')
        parts.append(f"<title>Breadcrumb Report (last {days} days)</title>")
        parts.append(f"<style>{_CSS}</style>")
        parts.append("</head><body>")
        parts.append(f"<h1>Breadcrumb Test Health (last {days} days)</h1>")

        # Cards
        parts.append('<div class="cards">')
        parts.append(_card("Total", total, ""))
        parts.append(_card("Stable", stable, "stable"))
        parts.append(_card("Healed", healed, "healed"))
        parts.append(_card("Flaky", flaky, "flaky"))
        parts.append(_card("Failing", failing, "failing"))
        parts.append("</div>")

        # Top healed locators
        parts.append("<h2>Top Healed Locators</h2>")
        if top_locators:
            parts.append("<table><thead><tr>")
            parts.append(
                "<th>Test ID</th><th>Locator</th>"
                "<th>Count</th><th>Avg Confidence</th>"
            )
            parts.append("</tr></thead><tbody>")
            for r in top_locators:
                parts.append(
                    f"<tr><td>{_esc(r[0])}</td><td>{_esc(r[1])}</td>"
                    f"<td>{r[2]}</td><td>{r[3]:.2f}</td></tr>"
                )
            parts.append("</tbody></table>")
        else:
            parts.append('<p class="empty">No healing events in this period.</p>')

        # Recent healing events
        parts.append("<h2>Recent Healing Events</h2>")
        if recent_events:
            parts.append("<table><thead><tr>")
            parts.append(
                "<th>Timestamp</th><th>Test ID</th>"
                "<th>Locator</th><th>Confidence</th>"
            )
            parts.append("</tr></thead><tbody>")
            for r in recent_events:
                ts = datetime.fromtimestamp(
                    r[0], tz=timezone.utc
                ).strftime("%Y-%m-%d %H:%M:%S")
                parts.append(
                    f"<tr><td>{ts}</td><td>{_esc(r[1])}</td>"
                    f"<td>{_esc(r[2])}</td><td>{r[3]:.2f}</td></tr>"
                )
            parts.append("</tbody></table>")
        else:
            parts.append('<p class="empty">No healing events in this period.</p>')

        # Flaky tests
        if flaky_tests:
            parts.append("<h2>Flaky Tests</h2>")
            parts.append("<table><thead><tr>")
            parts.append(
                "<th>Test ID</th><th>Flip Rate</th><th>Classification</th>"
            )
            parts.append("</tr></thead><tbody>")
            for test_id, fliprate, classification in flaky_tests:
                parts.append(
                    f"<tr><td>{_esc(test_id)}</td><td>{fliprate:.2f}</td>"
                    f"<td>{_esc(classification)}</td></tr>"
                )
            parts.append("</tbody></table>")

        parts.append(f"<footer>Generated by Breadcrumb at {now_str}</footer>")
        parts.append("</body></html>")
        return "\n".join(parts)

    def export(
        self, store: FingerprintStore, path: str | Path, days: int = 30
    ) -> None:
        """Write the HTML report to a file."""
        content = self.render(store, days)
        Path(path).write_text(content, encoding="utf-8")


def _scalar(conn: object, sql: str, params: tuple[object, ...] = ()) -> int:
    """Execute a query returning a single int."""
    row = conn.execute(sql, params).fetchone()  # type: ignore[union-attr]
    return int(row[0]) if row else 0


def _esc(value: object) -> str:
    """HTML-escape a value."""
    return html.escape(str(value))


def _card(label: str, value: int, css_class: str) -> str:
    """Generate an HTML card div."""
    cls = f" {css_class}" if css_class else ""
    return (
        f'<div class="card{cls}">'
        f'<div class="label">{_esc(label)}</div>'
        f'<div class="value">{value}</div>'
        f"</div>"
    )


def _compute_fliprate(runs: list[object]) -> float:
    """Compute the flip rate: fraction of adjacent status changes."""
    if len(runs) < 2:
        return 0.0
    flips = sum(
        1 for i in range(1, len(runs))
        if runs[i][0] != runs[i - 1][0]  # type: ignore[index]
    )
    return flips / (len(runs) - 1)


def _classify_fliprate(fliprate: float) -> str:
    """Classify a test by its flip rate."""
    if fliprate >= 0.3:
        return "Flaky"
    if fliprate >= 0.1:
        return "Intermittent"
    return "Stable"
