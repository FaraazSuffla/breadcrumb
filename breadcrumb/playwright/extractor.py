"""Extract ElementFingerprint data from live Playwright elements.

This module is the bridge between Playwright's browser automation and
Breadcrumb's core fingerprinting system. It uses Playwright's evaluate()
API to run JavaScript in the browser context and capture rich element data.

All functions here accept Playwright Locator or ElementHandle objects and
return ElementFingerprint instances ready for storage and comparison.
"""

from __future__ import annotations

from typing import Any

from breadcrumb.core.fingerprint import BoundingBox, ElementFingerprint

# JavaScript snippet evaluated in the browser to extract element data.
# Returns a plain object with all fingerprint signals.
_EXTRACT_JS = """
(element) => {
    // Tag name
    const tag = element.tagName.toLowerCase();

    // Visible text (direct text content, trimmed)
    const text = (element.textContent || '').trim().substring(0, 500);

    // All attributes as {name: value} pairs
    const attributes = {};
    for (const attr of element.attributes) {
        attributes[attr.name] = attr.value;
    }

    // DOM path: ancestor tag names from <html> down to this element
    const domPath = [];
    let current = element;
    while (current && current.nodeType === Node.ELEMENT_NODE) {
        domPath.unshift(current.tagName.toLowerCase());
        current = current.parentElement;
    }

    // Sibling context: tag names of adjacent siblings (up to 3 each side)
    const siblings = [];
    const maxSiblings = 3;

    let prev = element.previousElementSibling;
    const prevTags = [];
    for (let i = 0; i < maxSiblings && prev; i++) {
        prevTags.unshift(prev.tagName.toLowerCase());
        prev = prev.previousElementSibling;
    }
    siblings.push(...prevTags);

    let next = element.nextElementSibling;
    for (let i = 0; i < maxSiblings && next; i++) {
        siblings.push(next.tagName.toLowerCase());
        next = next.nextElementSibling;
    }

    // Bounding box
    const rect = element.getBoundingClientRect();
    const bbox = {
        x: rect.x,
        y: rect.y,
        width: rect.width,
        height: rect.height,
    };

    return { tag, text, attributes, domPath, siblings, bbox };
}
"""

# Lightweight JS that returns minimal data for all elements on the page.
# Used to build candidate lists for healing.
_EXTRACT_ALL_JS = """
() => {
    const results = [];
    const elements = document.querySelectorAll('*');

    for (const element of elements) {
        // Skip non-visible and structural-only elements
        const tag = element.tagName.toLowerCase();
        if (['html', 'head', 'meta', 'link', 'style', 'script', 'noscript', 'br', 'wbr'].includes(tag)) {
            continue;
        }

        const rect = element.getBoundingClientRect();
        if (rect.width === 0 && rect.height === 0) {
            continue;
        }

        const text = (element.textContent || '').trim().substring(0, 500);

        const attributes = {};
        for (const attr of element.attributes) {
            attributes[attr.name] = attr.value;
        }

        const domPath = [];
        let current = element;
        while (current && current.nodeType === Node.ELEMENT_NODE) {
            domPath.unshift(current.tagName.toLowerCase());
            current = current.parentElement;
        }

        const siblings = [];
        const maxSiblings = 3;
        let prev = element.previousElementSibling;
        const prevTags = [];
        for (let i = 0; i < maxSiblings && prev; i++) {
            prevTags.unshift(prev.tagName.toLowerCase());
            prev = prev.previousElementSibling;
        }
        siblings.push(...prevTags);
        let next = element.nextElementSibling;
        for (let i = 0; i < maxSiblings && next; i++) {
            siblings.push(next.tagName.toLowerCase());
            next = next.nextElementSibling;
        }

        results.push({
            tag,
            text,
            attributes,
            domPath,
            siblings,
            bbox: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
        });
    }

    return results;
}
"""


def _raw_to_fingerprint(
    raw: dict[str, Any],
    locator: str = "",
    test_id: str = "",
) -> ElementFingerprint:
    """Convert raw JS extraction data into an ElementFingerprint."""
    attrs_dict: dict[str, str] = raw.get("attributes", {})
    attributes = frozenset(attrs_dict.items())

    dom_path = tuple(raw.get("domPath", ()))
    siblings = tuple(raw.get("siblings", ()))

    bbox_data = raw.get("bbox")
    bbox: BoundingBox | None = None
    if bbox_data is not None:
        bbox = BoundingBox(
            x=float(bbox_data.get("x", 0)),
            y=float(bbox_data.get("y", 0)),
            width=float(bbox_data.get("width", 0)),
            height=float(bbox_data.get("height", 0)),
        )

    return ElementFingerprint(
        tag=ElementFingerprint._normalize_tag(raw.get("tag", "")),
        text=ElementFingerprint._normalize_text(raw.get("text", "")),
        attributes=attributes,
        dom_path=dom_path,
        siblings=siblings,
        bbox=bbox,
        locator=locator,
        test_id=test_id,
    )


async def extract_fingerprint(
    locator: Any,
    locator_str: str = "",
    test_id: str = "",
) -> ElementFingerprint:
    """Extract a fingerprint from a Playwright Locator.

    Args:
        locator: A Playwright Locator pointing to a single element.
        locator_str: The original locator string (e.g. "#login-btn").
        test_id: The test identifier for storage keying.

    Returns:
        An ElementFingerprint capturing all signals from the live element.

    Raises:
        playwright.async_api.Error: If the locator doesn't resolve to an element.
    """
    raw: dict[str, Any] = await locator.evaluate(_EXTRACT_JS)
    return _raw_to_fingerprint(raw, locator=locator_str, test_id=test_id)


def extract_fingerprint_sync(
    locator: Any,
    locator_str: str = "",
    test_id: str = "",
) -> ElementFingerprint:
    """Synchronous version of extract_fingerprint.

    Args:
        locator: A Playwright Locator pointing to a single element.
        locator_str: The original locator string (e.g. "#login-btn").
        test_id: The test identifier for storage keying.

    Returns:
        An ElementFingerprint capturing all signals from the live element.
    """
    raw: dict[str, Any] = locator.evaluate(_EXTRACT_JS)
    return _raw_to_fingerprint(raw, locator=locator_str, test_id=test_id)


async def extract_all_candidates(
    page: Any,
) -> list[ElementFingerprint]:
    """Extract fingerprints for all visible elements on the page.

    Used during healing to build a candidate list. Filters out invisible
    elements and structural tags (html, head, script, etc.).

    Args:
        page: A Playwright Page object.

    Returns:
        List of ElementFingerprint instances for all visible elements.
    """
    raw_list: list[dict[str, Any]] = await page.evaluate(_EXTRACT_ALL_JS)
    return [_raw_to_fingerprint(raw) for raw in raw_list]


def extract_all_candidates_sync(
    page: Any,
) -> list[ElementFingerprint]:
    """Synchronous version of extract_all_candidates."""
    raw_list: list[dict[str, Any]] = page.evaluate(_EXTRACT_ALL_JS)
    return [_raw_to_fingerprint(raw) for raw in raw_list]
