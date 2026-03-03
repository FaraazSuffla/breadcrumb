"""Tests for breadcrumb.core.fingerprint."""

import pytest

from breadcrumb.core.fingerprint import BoundingBox, ElementFingerprint


# ---------------------------------------------------------------------------
# BoundingBox
# ---------------------------------------------------------------------------


class TestBoundingBox:
    def test_center(self) -> None:
        bbox = BoundingBox(x=100, y=200, width=50, height=30)
        assert bbox.center == (125.0, 215.0)

    def test_center_at_origin(self) -> None:
        bbox = BoundingBox(x=0, y=0, width=100, height=100)
        assert bbox.center == (50.0, 50.0)

    def test_frozen(self) -> None:
        bbox = BoundingBox(x=0, y=0, width=10, height=10)
        with pytest.raises(AttributeError):
            bbox.x = 5  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ElementFingerprint — construction
# ---------------------------------------------------------------------------


class TestElementFingerprint:
    def test_basic_creation(self) -> None:
        fp = ElementFingerprint(
            tag="button",
            text="sign in",
            attributes=frozenset({("id", "login-btn"), ("class", "btn primary")}),
            dom_path=("html", "body", "div", "form", "button"),
            siblings=("input", "input"),
            bbox=BoundingBox(x=450, y=320, width=100, height=40),
            locator="#login-btn",
            test_id="test_login",
        )
        assert fp.tag == "button"
        assert fp.text == "sign in"
        assert ("id", "login-btn") in fp.attributes
        assert fp.dom_path[-1] == "button"
        assert fp.locator == "#login-btn"

    def test_frozen(self) -> None:
        fp = ElementFingerprint(
            tag="div", text="", attributes=frozenset(), dom_path=(), siblings=()
        )
        with pytest.raises(AttributeError):
            fp.tag = "span"  # type: ignore[misc]

    def test_defaults(self) -> None:
        fp = ElementFingerprint(
            tag="a", text="click", attributes=frozenset(), dom_path=(), siblings=()
        )
        assert fp.bbox is None
        assert fp.locator == ""
        assert fp.test_id == ""


# ---------------------------------------------------------------------------
# ElementFingerprint — normalization
# ---------------------------------------------------------------------------


class TestNormalization:
    def test_normalize_text_strips_and_lowercases(self) -> None:
        assert ElementFingerprint._normalize_text("  Sign In  ") == "sign in"

    def test_normalize_text_collapses_whitespace(self) -> None:
        assert ElementFingerprint._normalize_text("Sign   In\n Now") == "sign in now"

    def test_normalize_text_empty(self) -> None:
        assert ElementFingerprint._normalize_text(None) == ""
        assert ElementFingerprint._normalize_text("") == ""

    def test_normalize_tag(self) -> None:
        assert ElementFingerprint._normalize_tag("BUTTON") == "button"
        assert ElementFingerprint._normalize_tag("  Div  ") == "div"
        assert ElementFingerprint._normalize_tag(None) == ""


# ---------------------------------------------------------------------------
# ElementFingerprint — serialization roundtrip
# ---------------------------------------------------------------------------


class TestSerialization:
    def _make_fingerprint(self) -> ElementFingerprint:
        return ElementFingerprint(
            tag="button",
            text="submit",
            attributes=frozenset({("id", "submit-btn"), ("class", "btn")}),
            dom_path=("html", "body", "form", "button"),
            siblings=("input", "label"),
            bbox=BoundingBox(x=10, y=20, width=100, height=50),
            locator="#submit-btn",
            test_id="test_submit",
        )

    def test_to_dict(self) -> None:
        fp = self._make_fingerprint()
        d = fp.to_dict()
        assert d["tag"] == "button"
        assert d["text"] == "submit"
        assert d["locator"] == "#submit-btn"
        assert d["test_id"] == "test_submit"
        assert d["dom_path"] == ["html", "body", "form", "button"]
        assert d["siblings"] == ["input", "label"]
        assert d["bbox"]["x"] == 10
        assert isinstance(d["attributes"], list)

    def test_roundtrip(self) -> None:
        fp = self._make_fingerprint()
        d = fp.to_dict()
        restored = ElementFingerprint.from_dict(d)
        assert restored.tag == fp.tag
        assert restored.text == fp.text
        assert restored.attributes == fp.attributes
        assert restored.dom_path == fp.dom_path
        assert restored.siblings == fp.siblings
        assert restored.locator == fp.locator
        assert restored.test_id == fp.test_id
        assert restored.bbox is not None
        assert restored.bbox.x == 10

    def test_from_dict_with_dict_attributes(self) -> None:
        fp = ElementFingerprint.from_dict({
            "tag": "input",
            "text": "",
            "attributes": {"type": "email", "name": "user"},
            "dom_path": ["html", "body"],
            "siblings": [],
        })
        assert ("type", "email") in fp.attributes
        assert ("name", "user") in fp.attributes

    def test_from_dict_no_bbox(self) -> None:
        fp = ElementFingerprint.from_dict({"tag": "div"})
        assert fp.bbox is None

    def test_from_dict_normalizes(self) -> None:
        fp = ElementFingerprint.from_dict({
            "tag": "BUTTON",
            "text": "  Click Me  ",
        })
        assert fp.tag == "button"
        assert fp.text == "click me"

    def test_from_dict_minimal(self) -> None:
        fp = ElementFingerprint.from_dict({"tag": "span"})
        assert fp.tag == "span"
        assert fp.text == ""
        assert fp.attributes == frozenset()
        assert fp.dom_path == ()
        assert fp.siblings == ()
