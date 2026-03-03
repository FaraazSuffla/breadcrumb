"""Tests for breadcrumb.core.healer."""

from pathlib import Path

import pytest

from breadcrumb.core.fingerprint import BoundingBox, ElementFingerprint
from breadcrumb.core.healer import Healer
from breadcrumb.core.storage import FingerprintStore


@pytest.fixture
def store(tmp_path: Path) -> FingerprintStore:
    db_path = tmp_path / "test.breadcrumb.db"
    s = FingerprintStore(db_path)
    yield s
    s.close()


@pytest.fixture
def healer(store: FingerprintStore) -> Healer:
    return Healer(store=store, threshold=0.5)


def _make_fp(
    tag: str = "button",
    text: str = "submit",
    attrs: dict[str, str] | None = None,
    dom_path: tuple[str, ...] = ("html", "body", "form", "button"),
    siblings: tuple[str, ...] = ("input", "label"),
    bbox: BoundingBox | None = None,
    locator: str = "#submit-btn",
    test_id: str = "test_submit",
) -> ElementFingerprint:
    if attrs is None:
        attrs = {"id": "submit-btn", "class": "btn primary"}
    if bbox is None:
        bbox = BoundingBox(x=100, y=200, width=80, height=40)
    return ElementFingerprint(
        tag=tag,
        text=text,
        attributes=frozenset(attrs.items()),
        dom_path=dom_path,
        siblings=siblings,
        bbox=bbox,
        locator=locator,
        test_id=test_id,
    )


class TestHealerSave:
    def test_save_stores_fingerprint(self, healer: Healer) -> None:
        fp = _make_fp()
        healer.save(fp)
        loaded = healer.store.load_fingerprint("test_submit", "#submit-btn")
        assert loaded is not None
        assert loaded.tag == "button"


class TestHealSuccess:
    def test_exact_match(self, healer: Healer) -> None:
        stored = _make_fp()
        healer.save(stored)
        candidate = _make_fp(locator="", test_id="")
        result = healer.heal("test_submit", "#submit-btn", [candidate])
        assert result.healed is True
        assert result.score is not None
        assert result.score.total > 0.95

    def test_id_renamed(self, healer: Healer) -> None:
        """Blueprint scenario: #login-btn renamed to .auth-button."""
        stored = _make_fp(
            tag="button", text="sign in",
            attrs={"id": "login-btn", "class": "btn primary"},
            locator="#login-btn", test_id="test_login",
        )
        healer.save(stored)
        candidate = _make_fp(
            tag="button", text="sign in",
            attrs={"class": "auth-button"},
            dom_path=("html", "body", "form", "button"),
            siblings=("input", "label"),
            locator="", test_id="",
        )
        result = healer.heal("test_login", "#login-btn", [candidate])
        assert result.healed is True
        assert result.score is not None
        assert result.score.total > 0.5

    def test_text_changed(self, healer: Healer) -> None:
        stored = _make_fp(text="submit")
        healer.save(stored)
        candidate = _make_fp(text="send", locator="", test_id="")
        result = healer.heal("test_submit", "#submit-btn", [candidate])
        assert result.healed is True
        assert result.score is not None
        assert result.score.total > 0.7

    def test_picks_best_from_multiple(self, healer: Healer) -> None:
        stored = _make_fp()
        healer.save(stored)
        good = _make_fp(text="submit", locator="", test_id="")
        bad = _make_fp(tag="div", text="unrelated", attrs={}, locator="", test_id="")
        result = healer.heal("test_submit", "#submit-btn", [bad, good])
        assert result.healed is True
        assert result.candidate is not None
        assert result.candidate.tag == "button"

    def test_healing_records_event(self, healer: Healer) -> None:
        stored = _make_fp()
        healer.save(stored)
        candidate = _make_fp(locator="", test_id="")
        healer.heal("test_submit", "#submit-btn", [candidate])
        events = healer.store.get_healing_events()
        assert len(events) == 1
        assert events[0].test_id == "test_submit"
        assert events[0].confidence > 0.9

    def test_healing_updates_stored_fingerprint(self, healer: Healer) -> None:
        stored = _make_fp(text="submit")
        healer.save(stored)
        candidate = _make_fp(text="send", locator="", test_id="")
        healer.heal("test_submit", "#submit-btn", [candidate])
        updated = healer.store.load_fingerprint("test_submit", "#submit-btn")
        assert updated is not None
        assert updated.text == "send"


class TestHealFailure:
    def test_no_stored_fingerprint(self, healer: Healer) -> None:
        candidate = _make_fp(locator="", test_id="")
        result = healer.heal("test_unknown", "#nope", [candidate])
        assert result.healed is False
        assert result.candidate is None

    def test_no_candidates(self, healer: Healer) -> None:
        stored = _make_fp()
        healer.save(stored)
        result = healer.heal("test_submit", "#submit-btn", [])
        assert result.healed is False

    def test_below_threshold(self, healer: Healer) -> None:
        stored = _make_fp()
        healer.save(stored)
        terrible = _make_fp(
            tag="span", text="copyright 2026",
            attrs={"class": "footer-text"},
            dom_path=("html", "body", "footer", "span"),
            siblings=("a",),
            bbox=BoundingBox(x=0, y=900, width=200, height=20),
            locator="", test_id="",
        )
        result = healer.heal("test_submit", "#submit-btn", [terrible])
        assert result.healed is False
        assert result.score is not None
        assert result.score.total < 0.5

    def test_below_threshold_no_event(self, healer: Healer) -> None:
        stored = _make_fp()
        healer.save(stored)
        terrible = _make_fp(
            tag="span", text="nope", attrs={},
            dom_path=("html",), siblings=(),
            bbox=BoundingBox(x=0, y=900, width=10, height=10),
            locator="", test_id="",
        )
        healer.heal("test_submit", "#submit-btn", [terrible])
        assert len(healer.store.get_healing_events()) == 0


class TestHealAllScores:
    def test_all_scores_sorted(self, healer: Healer) -> None:
        stored = _make_fp()
        healer.save(stored)
        c1 = _make_fp(text="submit", locator="", test_id="")
        c2 = _make_fp(tag="div", text="other", attrs={}, locator="", test_id="")
        result = healer.heal("test_submit", "#submit-btn", [c2, c1])
        assert len(result.all_scores) == 2
        assert result.all_scores[0][1].total >= result.all_scores[1][1].total


class TestCustomThreshold:
    def test_high_threshold_rejects(self, store: FingerprintStore) -> None:
        healer = Healer(store=store, threshold=0.99)
        stored = _make_fp()
        healer.save(stored)
        candidate = _make_fp(text="send", locator="", test_id="")
        result = healer.heal("test_submit", "#submit-btn", [candidate])
        assert result.healed is False

    def test_low_threshold_accepts(self, store: FingerprintStore) -> None:
        healer = Healer(store=store, threshold=0.1)
        stored = _make_fp()
        healer.save(stored)
        weak = _make_fp(
            tag="button", text="cancel", attrs={"class": "secondary"},
            dom_path=("html", "body", "div", "button"),
            siblings=(), locator="", test_id="",
        )
        result = healer.heal("test_submit", "#submit-btn", [weak])
        assert result.healed is True
