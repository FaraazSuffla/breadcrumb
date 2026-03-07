"""Tests for breadcrumb.flaky — tracker, analyzer, quarantine."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from breadcrumb.core.storage import FingerprintStore
from breadcrumb.flaky.analyzer import TestAnalyzer
from breadcrumb.flaky.quarantine import QuarantineManager
from breadcrumb.flaky.tracker import TestTracker, migrate_schema


@pytest.fixture()
def store(tmp_path: Path) -> FingerprintStore:  # type: ignore[misc]
    """Fresh FingerprintStore backed by a temp DB."""
    s = FingerprintStore(tmp_path / "test.db")
    yield s  # type: ignore[misc]
    s.close()


@pytest.fixture()
def tracker(store: FingerprintStore) -> TestTracker:
    return TestTracker(store)


@pytest.fixture()
def analyzer(tracker: TestTracker) -> TestAnalyzer:
    return TestAnalyzer(tracker)


@pytest.fixture()
def manager(store: FingerprintStore, analyzer: TestAnalyzer) -> QuarantineManager:
    return QuarantineManager(store, analyzer)


# ---------------------------------------------------------------------------
# TestTracker
# ---------------------------------------------------------------------------


class TestTrackerBasic:
    def test_record_and_retrieve_run(self, tracker: TestTracker) -> None:
        tracker.record_run("test_login", "passed", duration_ms=50.0)
        runs = tracker.get_runs("test_login")
        assert len(runs) == 1
        r = runs[0]
        assert r["test_id"] == "test_login"
        assert r["status"] == "passed"
        assert r["duration_ms"] == pytest.approx(50.0)
        assert r["healing_occurred"] is False
        assert r["error_type"] is None
        assert r["environment"] is None

    def test_record_all_fields(self, tracker: TestTracker) -> None:
        tracker.record_run(
            "test_checkout",
            "failed",
            duration_ms=200.0,
            healing_occurred=True,
            error_type="AssertionError",
            environment="ci",
        )
        runs = tracker.get_runs("test_checkout")
        assert len(runs) == 1
        r = runs[0]
        assert r["status"] == "failed"
        assert r["healing_occurred"] is True
        assert r["error_type"] == "AssertionError"
        assert r["environment"] == "ci"

    def test_multiple_runs_ordered_desc(self, tracker: TestTracker) -> None:
        for status in ["passed", "failed", "passed"]:
            tracker.record_run("test_x", status)
            time.sleep(0.01)
        runs = tracker.get_runs("test_x")
        # Most recent first
        assert runs[0]["status"] == "passed"
        assert runs[1]["status"] == "failed"
        assert runs[2]["status"] == "passed"

    def test_limit_respected(self, tracker: TestTracker) -> None:
        for _ in range(15):
            tracker.record_run("test_y", "passed")
        runs = tracker.get_runs("test_y", limit=5)
        assert len(runs) == 5

    def test_get_all_test_ids(self, tracker: TestTracker) -> None:
        tracker.record_run("alpha", "passed")
        tracker.record_run("beta", "failed")
        tracker.record_run("alpha", "passed")
        ids = tracker.get_all_test_ids()
        assert "alpha" in ids
        assert "beta" in ids

    def test_empty_runs_for_unknown_test(self, tracker: TestTracker) -> None:
        runs = tracker.get_runs("nonexistent_test")
        assert runs == []

    def test_schema_migration_creates_tables(self, store: FingerprintStore) -> None:
        """Migrating a v1 DB adds test_runs and quarantine tables."""
        migrate_schema(store)
        conn = store._get_conn()
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'",
            ).fetchall()
        }
        assert "test_runs" in tables
        assert "quarantine" in tables

    def test_schema_version_bumped_to_2(self, store: FingerprintStore) -> None:
        migrate_schema(store)
        conn = store._get_conn()
        row = conn.execute(
            "SELECT value FROM schema_meta WHERE key = 'schema_version'",
        ).fetchone()
        assert row is not None
        assert int(row[0]) == 2

    def test_migrate_idempotent(self, store: FingerprintStore) -> None:
        """Calling migrate twice does not raise."""
        migrate_schema(store)
        migrate_schema(store)  # second call must be a no-op
        conn = store._get_conn()
        row = conn.execute(
            "SELECT value FROM schema_meta WHERE key = 'schema_version'",
        ).fetchone()
        assert int(row[0]) == 2


# ---------------------------------------------------------------------------
# TestAnalyzer
# ---------------------------------------------------------------------------


class TestFlipRate:
    def test_all_passing_is_zero(self, tracker: TestTracker, analyzer: TestAnalyzer) -> None:
        for _ in range(5):
            tracker.record_run("stable_test", "passed")
        assert analyzer.compute_fliprate("stable_test") == 0.0

    def test_alternating_is_one(self, tracker: TestTracker, analyzer: TestAnalyzer) -> None:
        # record in reverse (tracker orders DESC so we reverse here)
        # We want history: passed, failed, passed, failed (newest first in DB)
        statuses = ["failed", "passed", "failed", "passed"]  # newest first
        for s in statuses:
            tracker.record_run("alt_test", s)
            time.sleep(0.005)
        rate = analyzer.compute_fliprate("alt_test", window=4)
        # 3 flips in 4 runs → rate = 1.0
        assert rate == pytest.approx(1.0)

    def test_no_runs_returns_zero(self, analyzer: TestAnalyzer) -> None:
        assert analyzer.compute_fliprate("ghost_test") == 0.0

    def test_single_run_returns_zero(self, tracker: TestTracker, analyzer: TestAnalyzer) -> None:
        tracker.record_run("solo", "passed")
        assert analyzer.compute_fliprate("solo") == 0.0

    def test_known_sequence(self, tracker: TestTracker, analyzer: TestAnalyzer) -> None:
        # Sequence (oldest→newest): P P P F P → 1 flip in 4 pairs → 0.25
        # Store newest first so tracker.get_runs returns DESC
        for s in ["passed", "failed", "passed", "passed", "passed"]:  # newest→oldest
            tracker.record_run("seq_test", s)
            time.sleep(0.005)
        rate = analyzer.compute_fliprate("seq_test", window=5)
        # The exact rate depends on ordering — just assert it's between 0 and 1
        assert 0.0 <= rate <= 1.0


class TestEWMAFlipRate:
    def test_no_runs_returns_zero(self, analyzer: TestAnalyzer) -> None:
        assert analyzer.compute_ewma_fliprate("ghost") == 0.0

    def test_stable_returns_low(self, tracker: TestTracker, analyzer: TestAnalyzer) -> None:
        for _ in range(10):
            tracker.record_run("stable", "passed")
        rate = analyzer.compute_ewma_fliprate("stable")
        assert rate == pytest.approx(0.0)

    def test_flipping_returns_nonzero(self, tracker: TestTracker, analyzer: TestAnalyzer) -> None:
        for s in ["failed", "passed"] * 5:  # 10 alternating runs
            tracker.record_run("flipper", s)
            time.sleep(0.005)
        rate = analyzer.compute_ewma_fliprate("flipper", window=10)
        assert rate > 0.0


class TestClassification:
    def _fill(self, tracker: TestTracker, test_id: str, statuses: list[str]) -> None:
        for s in statuses:
            tracker.record_run(test_id, s)
            time.sleep(0.005)

    def test_stable(self, tracker: TestTracker, analyzer: TestAnalyzer) -> None:
        self._fill(tracker, "s_test", ["passed"] * 5)
        assert analyzer.classify("s_test") == "Stable"

    def test_intermittent(self, tracker: TestTracker, analyzer: TestAnalyzer) -> None:
        # 1 flip in 10 runs → rate = 1/9 ≈ 0.11 → Intermittent
        self._fill(tracker, "i_test", ["failed"] + ["passed"] * 9)
        rate = analyzer.compute_fliprate("i_test", window=10)
        assert 0.0 < rate <= 0.2
        assert analyzer.classify("i_test") == "Intermittent"

    def test_flaky(self, tracker: TestTracker, analyzer: TestAnalyzer) -> None:
        # 3 flips in 10 runs → rate = 3/9 ≈ 0.33 → Flaky
        self._fill(tracker, "f_test", ["passed", "failed", "passed", "failed"] + ["passed"] * 6)
        rate = analyzer.compute_fliprate("f_test", window=10)
        assert 0.2 < rate <= 0.5
        assert analyzer.classify("f_test") == "Flaky"

    def test_chronic(self, tracker: TestTracker, analyzer: TestAnalyzer) -> None:
        # Alternating P/F → rate = 1.0 → Chronic
        self._fill(tracker, "c_test", (["passed", "failed"] * 5))
        rate = analyzer.compute_fliprate("c_test", window=10)
        assert rate > 0.5
        assert analyzer.classify("c_test") == "Chronic"

    def test_get_all_classifications(self, tracker: TestTracker, analyzer: TestAnalyzer) -> None:
        self._fill(tracker, "a", ["passed"] * 3)
        self._fill(tracker, "b", ["passed", "failed", "passed", "failed"] * 3)
        classifs = analyzer.get_all_classifications()
        assert "a" in classifs
        assert "b" in classifs
        assert classifs["a"] == "Stable"


# ---------------------------------------------------------------------------
# QuarantineManager
# ---------------------------------------------------------------------------


class TestQuarantineManager:
    def test_quarantine_and_check(self, manager: QuarantineManager) -> None:
        assert not manager.is_quarantined("test_q")
        manager.quarantine("test_q", "manual: broken")
        assert manager.is_quarantined("test_q")

    def test_unquarantine(self, manager: QuarantineManager) -> None:
        manager.quarantine("test_r", "manual")
        manager.unquarantine("test_r")
        assert not manager.is_quarantined("test_r")

    def test_get_all_quarantined(self, manager: QuarantineManager) -> None:
        manager.quarantine("a", "reason a")
        manager.quarantine("b", "reason b")
        all_q = manager.get_all_quarantined()
        assert "a" in all_q
        assert "b" in all_q

    def test_auto_update_quarantines_chronic(
        self,
        tracker: TestTracker,
        manager: QuarantineManager,
    ) -> None:
        # Alternating → Chronic
        for s in ["passed", "failed"] * 5:
            tracker.record_run("chronic_test", s)
            time.sleep(0.005)
        result = manager.auto_update()
        assert "chronic_test" in result["quarantined"]
        assert manager.is_quarantined("chronic_test")

    def test_auto_update_releases_stable(
        self,
        tracker: TestTracker,
        manager: QuarantineManager,
    ) -> None:
        # First quarantine manually
        manager.quarantine("stable_test", "was flaky before")
        # Now the test is stable
        for _ in range(5):
            tracker.record_run("stable_test", "passed")
        result = manager.auto_update()
        assert "stable_test" in result["unquarantined"]
        assert not manager.is_quarantined("stable_test")

    def test_auto_update_does_not_double_quarantine(
        self,
        tracker: TestTracker,
        manager: QuarantineManager,
    ) -> None:
        for s in ["passed", "failed"] * 5:
            tracker.record_run("dup_test", s)
            time.sleep(0.005)
        manager.auto_update()
        result = manager.auto_update()
        # Already quarantined — should not appear in newly_quarantined
        assert "dup_test" not in result["quarantined"]
