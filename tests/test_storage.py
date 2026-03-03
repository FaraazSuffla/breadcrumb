"""Tests for breadcrumb.core.storage."""

import time
from pathlib import Path

import pytest

from breadcrumb.core.fingerprint import BoundingBox, ElementFingerprint
from breadcrumb.core.storage import FingerprintStore, HealingEvent


@pytest.fixture
def store(tmp_path: Path) -> FingerprintStore:
    """Create a FingerprintStore with a temporary database."""
    db_path = tmp_path / "test.breadcrumb.db"
    s = FingerprintStore(db_path)
    yield s
    s.close()


@pytest.fixture
def sample_fp() -> ElementFingerprint:
    """A sample fingerprint with all fields populated."""
    return ElementFingerprint(
        tag="button",
        text="submit",
        attributes=frozenset({("id", "submit-btn"), ("class", "btn primary")}),
        dom_path=("html", "body", "form", "button"),
        siblings=("input", "label"),
        bbox=BoundingBox(x=100, y=200, width=80, height=40),
        locator="#submit-btn",
        test_id="test_submit",
    )


# ---------------------------------------------------------------------------
# Database creation
# ---------------------------------------------------------------------------


class TestDatabaseCreation:
    def test_db_file_created(self, store: FingerprintStore) -> None:
        assert store.db_path.exists()

    def test_schema_version(self, store: FingerprintStore) -> None:
        conn = store._get_conn()
        row = conn.execute(
            "SELECT value FROM schema_meta WHERE key = 'schema_version'"
        ).fetchone()
        assert row is not None
        assert row["value"] == "1"

    def test_empty_stats(self, store: FingerprintStore) -> None:
        stats = store.stats()
        assert stats["fingerprints"] == 0
        assert stats["healing_events"] == 0


# ---------------------------------------------------------------------------
# Fingerprint CRUD
# ---------------------------------------------------------------------------


class TestFingerprintCRUD:
    def test_save_and_load(
        self, store: FingerprintStore, sample_fp: ElementFingerprint
    ) -> None:
        store.save_fingerprint(sample_fp)
        loaded = store.load_fingerprint("test_submit", "#submit-btn")
        assert loaded is not None
        assert loaded.tag == "button"
        assert loaded.text == "submit"
        assert loaded.locator == "#submit-btn"
        assert loaded.test_id == "test_submit"

    def test_load_nonexistent(self, store: FingerprintStore) -> None:
        assert store.load_fingerprint("nope", "nope") is None

    def test_save_updates_existing(
        self, store: FingerprintStore, sample_fp: ElementFingerprint
    ) -> None:
        store.save_fingerprint(sample_fp)

        updated = ElementFingerprint(
            tag="button",
            text="send",
            attributes=frozenset({("id", "submit-btn")}),
            dom_path=("html", "body", "form", "button"),
            siblings=("input",),
            locator="#submit-btn",
            test_id="test_submit",
        )
        store.save_fingerprint(updated)

        loaded = store.load_fingerprint("test_submit", "#submit-btn")
        assert loaded is not None
        assert loaded.text == "send"
        assert store.stats()["fingerprints"] == 1

    def test_save_without_test_id_raises(self, store: FingerprintStore) -> None:
        fp = ElementFingerprint(
            tag="div", text="", attributes=frozenset(),
            dom_path=(), siblings=(), locator="#x",
        )
        with pytest.raises(ValueError, match="test_id"):
            store.save_fingerprint(fp)

    def test_save_without_locator_raises(self, store: FingerprintStore) -> None:
        fp = ElementFingerprint(
            tag="div", text="", attributes=frozenset(),
            dom_path=(), siblings=(), test_id="test_x",
        )
        with pytest.raises(ValueError, match="locator"):
            store.save_fingerprint(fp)

    def test_delete_fingerprint(
        self, store: FingerprintStore, sample_fp: ElementFingerprint
    ) -> None:
        store.save_fingerprint(sample_fp)
        assert store.delete_fingerprint("test_submit", "#submit-btn") is True
        assert store.load_fingerprint("test_submit", "#submit-btn") is None

    def test_delete_nonexistent(self, store: FingerprintStore) -> None:
        assert store.delete_fingerprint("nope", "nope") is False

    def test_get_all_fingerprints(
        self, store: FingerprintStore, sample_fp: ElementFingerprint
    ) -> None:
        store.save_fingerprint(sample_fp)

        fp2 = ElementFingerprint(
            tag="input", text="", attributes=frozenset(),
            dom_path=(), siblings=(),
            locator=".email", test_id="test_login",
        )
        store.save_fingerprint(fp2)

        all_fps = store.get_all_fingerprints()
        assert len(all_fps) == 2

    def test_clear(
        self, store: FingerprintStore, sample_fp: ElementFingerprint
    ) -> None:
        store.save_fingerprint(sample_fp)
        store.clear()
        assert store.stats()["fingerprints"] == 0


# ---------------------------------------------------------------------------
# Healing events
# ---------------------------------------------------------------------------


class TestHealingEvents:
    def _make_event(self, test_id: str = "test_login", locator: str = "#btn") -> HealingEvent:
        return HealingEvent(
            test_id=test_id,
            locator=locator,
            confidence=0.87,
            original_fingerprint={"tag": "button", "text": "login"},
            healed_fingerprint={"tag": "button", "text": "sign in"},
            timestamp=time.time(),
        )

    def test_record_and_query(self, store: FingerprintStore) -> None:
        event = self._make_event()
        store.record_healing(event)

        events = store.get_healing_events()
        assert len(events) == 1
        assert events[0].test_id == "test_login"
        assert events[0].confidence == 0.87

    def test_filter_by_test_id(self, store: FingerprintStore) -> None:
        store.record_healing(self._make_event(test_id="test_a"))
        store.record_healing(self._make_event(test_id="test_b"))

        events = store.get_healing_events(test_id="test_a")
        assert len(events) == 1
        assert events[0].test_id == "test_a"

    def test_filter_by_locator(self, store: FingerprintStore) -> None:
        store.record_healing(self._make_event(locator="#btn1"))
        store.record_healing(self._make_event(locator="#btn2"))

        events = store.get_healing_events(locator="#btn1")
        assert len(events) == 1
        assert events[0].locator == "#btn1"

    def test_filter_by_both(self, store: FingerprintStore) -> None:
        store.record_healing(self._make_event(test_id="a", locator="#x"))
        store.record_healing(self._make_event(test_id="a", locator="#y"))
        store.record_healing(self._make_event(test_id="b", locator="#x"))

        events = store.get_healing_events(test_id="a", locator="#x")
        assert len(events) == 1

    def test_ordered_by_timestamp_desc(self, store: FingerprintStore) -> None:
        e1 = HealingEvent(
            test_id="t", locator="#a", confidence=0.8,
            original_fingerprint={}, healed_fingerprint={},
            timestamp=1000.0,
        )
        e2 = HealingEvent(
            test_id="t", locator="#a", confidence=0.9,
            original_fingerprint={}, healed_fingerprint={},
            timestamp=2000.0,
        )
        store.record_healing(e1)
        store.record_healing(e2)

        events = store.get_healing_events()
        assert events[0].timestamp > events[1].timestamp

    def test_stats_counts_events(self, store: FingerprintStore) -> None:
        store.record_healing(self._make_event())
        store.record_healing(self._make_event())
        assert store.stats()["healing_events"] == 2

    def test_clear_removes_events(self, store: FingerprintStore) -> None:
        store.record_healing(self._make_event())
        store.clear()
        assert store.stats()["healing_events"] == 0
