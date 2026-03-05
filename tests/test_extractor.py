"""Tests for breadcrumb.playwright.extractor."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

from breadcrumb.core.fingerprint import BoundingBox
from breadcrumb.playwright.extractor import (
    _EXTRACT_ALL_JS,
    _EXTRACT_JS,
    _raw_to_fingerprint,
    extract_all_candidates_sync,
    extract_fingerprint,
    extract_fingerprint_sync,
)

# ---------------------------------------------------------------------------
# Shared raw data helpers
# ---------------------------------------------------------------------------

_RAW_BUTTON = {
    "tag": "BUTTON",
    "text": "Sign In",
    "attributes": {"id": "login-btn", "class": "btn"},
    "domPath": ["html", "body", "form", "button"],
    "siblings": ["input"],
    "bbox": {"x": 10, "y": 20, "width": 100, "height": 40},
}

_RAW_INPUT = {
    "tag": "input",
    "text": "",
    "attributes": {"type": "email", "name": "email"},
    "domPath": ["html", "body", "form", "input"],
    "siblings": ["button"],
    "bbox": {"x": 10, "y": 60, "width": 200, "height": 36},
}


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


# ---------------------------------------------------------------------------
# extract_fingerprint_sync
# ---------------------------------------------------------------------------


class TestExtractFingerprintSync:
    def test_calls_evaluate_with_js(self) -> None:
        locator = MagicMock()
        locator.evaluate.return_value = _RAW_BUTTON
        fp = extract_fingerprint_sync(locator, locator_str="#login-btn", test_id="t1")
        locator.evaluate.assert_called_once_with(_EXTRACT_JS)
        assert fp.tag == "button"
        assert fp.text == "sign in"
        assert fp.locator == "#login-btn"
        assert fp.test_id == "t1"

    def test_returns_fingerprint_with_bbox(self) -> None:
        locator = MagicMock()
        locator.evaluate.return_value = _RAW_BUTTON
        fp = extract_fingerprint_sync(locator)
        assert fp.bbox is not None
        assert fp.bbox.x == 10.0
        assert fp.bbox.width == 100.0

    def test_defaults_empty_locator_and_test_id(self) -> None:
        locator = MagicMock()
        locator.evaluate.return_value = {
            "tag": "a",
            "text": "link",
            "attributes": {},
            "domPath": [],
            "siblings": [],
        }
        fp = extract_fingerprint_sync(locator)
        assert fp.locator == ""
        assert fp.test_id == ""

    def test_input_element(self) -> None:
        locator = MagicMock()
        locator.evaluate.return_value = _RAW_INPUT
        fp = extract_fingerprint_sync(locator, locator_str=".email-field")
        assert fp.tag == "input"
        assert ("type", "email") in fp.attributes
        assert fp.locator == ".email-field"


# ---------------------------------------------------------------------------
# extract_all_candidates_sync
# ---------------------------------------------------------------------------


class TestExtractAllCandidatesSync:
    def test_returns_list_of_fingerprints(self) -> None:
        page = MagicMock()
        page.evaluate.return_value = [_RAW_BUTTON, _RAW_INPUT]
        candidates = extract_all_candidates_sync(page)
        assert len(candidates) == 2
        assert candidates[0].tag == "button"
        assert candidates[1].tag == "input"

    def test_calls_page_evaluate_with_js(self) -> None:
        page = MagicMock()
        page.evaluate.return_value = []
        extract_all_candidates_sync(page)
        page.evaluate.assert_called_once_with(_EXTRACT_ALL_JS)

    def test_returns_empty_list_when_no_elements(self) -> None:
        page = MagicMock()
        page.evaluate.return_value = []
        candidates = extract_all_candidates_sync(page)
        assert candidates == []

    def test_candidates_have_no_locator_or_test_id(self) -> None:
        page = MagicMock()
        page.evaluate.return_value = [_RAW_BUTTON]
        candidates = extract_all_candidates_sync(page)
        assert candidates[0].locator == ""
        assert candidates[0].test_id == ""

    def test_large_candidate_list(self) -> None:
        page = MagicMock()
        raw_elements = [
            {
                "tag": "div",
                "text": f"item {i}",
                "attributes": {"id": f"item-{i}"},
                "domPath": ["html", "body", "div"],
                "siblings": [],
                "bbox": {"x": 0, "y": i * 40, "width": 200, "height": 36},
            }
            for i in range(100)
        ]
        page.evaluate.return_value = raw_elements
        candidates = extract_all_candidates_sync(page)
        assert len(candidates) == 100
        assert candidates[42].text == "item 42"


# ---------------------------------------------------------------------------
# extract_fingerprint (async)
# ---------------------------------------------------------------------------


class TestExtractFingerprintAsync:
    def test_async_calls_evaluate(self) -> None:
        locator = MagicMock()
        locator.evaluate = AsyncMock(return_value=_RAW_BUTTON)

        async def run() -> None:
            fp = await extract_fingerprint(locator, locator_str="#login-btn", test_id="t1")
            assert fp.tag == "button"
            assert fp.locator == "#login-btn"
            assert fp.test_id == "t1"
            locator.evaluate.assert_awaited_once_with(_EXTRACT_JS)

        asyncio.run(run())

    def test_async_returns_correct_bbox(self) -> None:
        locator = MagicMock()
        locator.evaluate = AsyncMock(return_value=_RAW_BUTTON)

        async def run() -> None:
            fp = await extract_fingerprint(locator)
            assert fp.bbox is not None
            assert fp.bbox.y == 20.0

        asyncio.run(run())


# ---------------------------------------------------------------------------
# extract_all_candidates (async)
# ---------------------------------------------------------------------------


class TestExtractAllCandidatesAsync:
    def test_async_returns_list_of_fingerprints(self) -> None:
        from breadcrumb.playwright.extractor import extract_all_candidates

        page = MagicMock()
        page.evaluate = AsyncMock(return_value=[_RAW_BUTTON, _RAW_INPUT])

        async def run() -> None:
            candidates = await extract_all_candidates(page)
            assert len(candidates) == 2
            assert candidates[0].tag == "button"
            assert candidates[1].tag == "input"
            page.evaluate.assert_awaited_once_with(_EXTRACT_ALL_JS)

        asyncio.run(run())

    def test_async_returns_empty_list(self) -> None:
        from breadcrumb.playwright.extractor import extract_all_candidates

        page = MagicMock()
        page.evaluate = AsyncMock(return_value=[])

        async def run() -> None:
            candidates = await extract_all_candidates(page)
            assert candidates == []

        asyncio.run(run())
