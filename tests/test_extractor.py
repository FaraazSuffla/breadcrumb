"""Tests for breadcrumb.playwright.extractor."""

from __future__ import annotations

from breadcrumb.core.fingerprint import BoundingBox
from breadcrumb.playwright.extractor import (
    _EXTRACT_ALL_JS,
    _EXTRACT_JS,
    _raw_to_fingerprint,
)


# ---------------------------------------------------------------------------
# _raw_to_fingerprint
# ---------------------------------------------------------------------------


class TestRawToFingerprint:
    def test_basic_conversion(self) -> None:
        raw = {
            "tag": "BUTTON",
            "text": "  Sign In  ",
            "attributes": {"id": "login-btn", "class": "btn primary"},
            "domPath": ["html", "body", "div", "form", "button"],
            "siblings": ["input", "label"],
            "bbox": {"x": 100, "y": 200, "width": 80, "height": 40},
        }
        fp = _raw_to_fingerprint(raw, locator="#login-btn", test_id="test_login")

        assert fp.tag == "button"
        assert fp.text == "sign in"
        assert ("id", "login-btn") in fp.attributes
        assert ("class", "btn primary") in fp.attributes
        assert fp.dom_path == ("html", "body", "div", "form", "button")
        assert fp.siblings == ("input", "label")
        assert fp.locator == "#login-btn"
        assert fp.test_id == "test_login"
        assert fp.bbox is not None
        assert fp.bbox.x == 100.0
        assert fp.bbox.width == 80.0

    def test_empty_attributes(self) -> None:
        raw = {"tag": "div", "text": "", "attributes": {}, "domPath": [], "siblings": []}
        fp = _raw_to_fingerprint(raw)
        assert fp.attributes == frozenset()

    def test_no_bbox(self) -> None:
        raw = {"tag": "span", "text": "hello", "attributes": {}, "domPath": [], "siblings": []}
        fp = _raw_to_fingerprint(raw)
        assert fp.bbox is None

    def test_bbox_with_zero_dimensions(self) -> None:
        raw = {
            "tag": "div",
            "text": "",
            "attributes": {},
            "domPath": [],
            "siblings": [],
            "bbox": {"x": 0, "y": 0, "width": 0, "height": 0},
        }
        fp = _raw_to_fingerprint(raw)
        assert fp.bbox is not None
        assert fp.bbox == BoundingBox(x=0, y=0, width=0, height=0)

    def test_default_locator_and_test_id(self) -> None:
        raw = {"tag": "a", "text": "link", "attributes": {}, "domPath": [], "siblings": []}
        fp = _raw_to_fingerprint(raw)
        assert fp.locator == ""
        assert fp.test_id == ""

    def test_missing_fields_default_gracefully(self) -> None:
        raw = {"tag": "input"}
        fp = _raw_to_fingerprint(raw)
        assert fp.tag == "input"
        assert fp.text == ""
        assert fp.attributes == frozenset()
        assert fp.dom_path == ()
        assert fp.siblings == ()
        assert fp.bbox is None

    def test_text_normalization(self) -> None:
        raw = {
            "tag": "button",
            "text": "  Click   Me\n  Now  ",
            "attributes": {},
            "domPath": [],
            "siblings": [],
        }
        fp = _raw_to_fingerprint(raw)
        assert fp.text == "click me now"

    def test_many_attributes(self) -> None:
        raw = {
            "tag": "input",
            "text": "",
            "attributes": {
                "type": "email",
                "name": "user_email",
                "placeholder": "Enter email",
                "data-testid": "email-input",
                "aria-label": "Email address",
                "required": "",
            },
            "domPath": ["html", "body", "form", "input"],
            "siblings": ["label"],
        }
        fp = _raw_to_fingerprint(raw)
        assert len(fp.attributes) == 6
        assert ("data-testid", "email-input") in fp.attributes
        assert ("aria-label", "Email address") in fp.attributes


# ---------------------------------------------------------------------------
# JS snippets (structural validation)
# ---------------------------------------------------------------------------


class TestJSSnippets:
    def test_extract_js_is_nonempty(self) -> None:
        assert len(_EXTRACT_JS) > 100

    def test_extract_js_contains_key_properties(self) -> None:
        assert "tagName" in _EXTRACT_JS
        assert "textContent" in _EXTRACT_JS
        assert "attributes" in _EXTRACT_JS
        assert "getBoundingClientRect" in _EXTRACT_JS
        assert "parentElement" in _EXTRACT_JS

    def test_extract_all_js_is_nonempty(self) -> None:
        assert len(_EXTRACT_ALL_JS) > 100

    def test_extract_all_js_filters_structural_tags(self) -> None:
        assert "script" in _EXTRACT_ALL_JS
        assert "style" in _EXTRACT_ALL_JS
        assert "meta" in _EXTRACT_ALL_JS
        assert "head" in _EXTRACT_ALL_JS
