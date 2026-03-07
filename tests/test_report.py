"""Minimal unit tests for breadcrumb.report module."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from breadcrumb.core.storage import FingerprintStore, HealingEvent
from breadcrumb.report import ReportConsole, ReportHTML, ReportJSON


@pytest.fixture()
def store(tmp_path: Path) -> FingerprintStore:
    """Create a temporary FingerprintStore and close it after use."""
    s = FingerprintStore(tmp_path / "test_report.db")
    yield s  # type: ignore[misc]
    s.close()


def _seed_healing_event(
    store: FingerprintStore,
    test_id: str = "test_login",
    locator: str = "#login-btn",
    confidence: float = 0.85,
) -> None:
    """Insert a healing event into the store."""
    store.record_healing(
        HealingEvent(
            test_id=test_id,
            locator=locator,
            confidence=confidence,
            original_fingerprint={"tag": "button", "id": "login-btn"},
            healed_fingerprint={"tag": "button", "id": "auth-button"},
            timestamp=time.time(),
        )
    )


def _create_v2_tables(store: FingerprintStore) -> None:
    """Create the test_runs and quarantine tables (v2 schema)."""
    conn = store._get_conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS test_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_id TEXT NOT NULL,
            status TEXT NOT NULL,
            duration_ms REAL,
            healing_occurred INTEGER DEFAULT 0,
            environment TEXT,
            timestamp REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS quarantine (
            test_id TEXT PRIMARY KEY,
            reason TEXT,
            quarantined_at REAL,
            auto_unquarantine INTEGER DEFAULT 0
        );
        """
    )
    conn.commit()


# ---- Console report ----


class TestReportConsole:
    def test_render_returns_string(self, store: FingerprintStore) -> None:
        report = ReportConsole()
        result = report.render(store)
        assert isinstance(result, str)

    def test_render_empty_db(self, store: FingerprintStore) -> None:
        result = ReportConsole().render(store)
        assert "Total tests: 0" in result
        assert "Stable: 0" in result
        assert "Healed: 0" in result

    def test_render_with_healing_events(self, store: FingerprintStore) -> None:
        _seed_healing_event(store)
        _seed_healing_event(store, locator=".submit-form", confidence=0.91)
        result = ReportConsole().render(store)
        assert "Total tests: 1" in result
        assert "Healed: 1" in result
        assert "Top healed locators:" in result
        assert "#login-btn" in result

    def test_render_with_v2_tables(self, store: FingerprintStore) -> None:
        _create_v2_tables(store)
        conn = store._get_conn()
        now = time.time()
        conn.execute(
            "INSERT INTO test_runs (test_id, status, duration_ms, timestamp) "
            "VALUES (?, ?, ?, ?)",
            ("test_stable", "passed", 100.0, now),
        )
        conn.execute(
            "INSERT INTO test_runs (test_id, status, duration_ms, timestamp) "
            "VALUES (?, ?, ?, ?)",
            ("test_fail", "failed", 200.0, now),
        )
        conn.execute(
            "INSERT INTO quarantine (test_id, reason, quarantined_at) "
            "VALUES (?, ?, ?)",
            ("test_flaky", "high fliprate", now),
        )
        # Add runs for the flaky test (pass/fail/pass/fail pattern)
        for i, status in enumerate(["failed", "passed", "failed", "passed"]):
            conn.execute(
                "INSERT INTO test_runs (test_id, status, duration_ms, timestamp) "
                "VALUES (?, ?, ?, ?)",
                ("test_flaky", status, 50.0, now + i),
            )
        conn.commit()

        result = ReportConsole().render(store)
        assert "Total tests: 3" in result
        assert "Failing: 1" in result
        assert "Flaky: 1" in result
        assert "Flaky tests:" in result
        assert "test_flaky" in result

    def test_render_custom_days(self, store: FingerprintStore) -> None:
        result = ReportConsole().render(store, days=7)
        assert "last 7 days" in result


# ---- HTML report ----


class TestReportHTML:
    def test_render_returns_html(self, store: FingerprintStore) -> None:
        result = ReportHTML().render(store)
        assert isinstance(result, str)
        assert "<!DOCTYPE html>" in result
        assert "</html>" in result

    def test_render_contains_summary(self, store: FingerprintStore) -> None:
        _seed_healing_event(store)
        result = ReportHTML().render(store)
        assert "Breadcrumb Test Health" in result
        assert "Total" in result
        assert "Healed" in result

    def test_export_creates_file(self, store: FingerprintStore, tmp_path: Path) -> None:
        out = tmp_path / "report.html"
        ReportHTML().export(store, out)
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content


# ---- JSON report ----


class TestReportJSON:
    def test_render_returns_dict(self, store: FingerprintStore) -> None:
        result = ReportJSON().render(store)
        assert isinstance(result, dict)
        assert "generated_at" in result
        assert "period_days" in result
        assert "summary" in result
        assert "healing_events" in result
        assert "flaky_tests" in result
        assert "top_locators" in result

    def test_render_summary_structure(self, store: FingerprintStore) -> None:
        result = ReportJSON().render(store)
        summary = result["summary"]
        for key in ("total", "stable", "healed", "flaky", "failing"):
            assert key in summary
            assert isinstance(summary[key], int)

    def test_render_with_events(self, store: FingerprintStore) -> None:
        _seed_healing_event(store)
        result = ReportJSON().render(store)
        assert result["summary"]["healed"] == 1
        assert len(result["healing_events"]) == 1
        assert len(result["top_locators"]) == 1

    def test_export_creates_valid_json(
        self, store: FingerprintStore, tmp_path: Path
    ) -> None:
        out = tmp_path / "report.json"
        ReportJSON().export(store, out)
        assert out.exists()
        data = json.loads(out.read_text(encoding="utf-8"))
        assert "summary" in data

    def test_render_custom_days(self, store: FingerprintStore) -> None:
        result = ReportJSON().render(store, days=7)
        assert result["period_days"] == 7
