"""Element fingerprinting — captures a rich identity snapshot of DOM elements.

A fingerprint captures multiple signals about an element: tag name, text content,
attributes, DOM path, sibling context, and bounding box position. These signals
are used by the similarity scorer to re-identify elements after DOM changes.

Design decisions:
    - Pure dataclass, no Playwright dependency. Fingerprints can be created from
      any source (Playwright, raw HTML, test fixtures).
    - All fields are immutable (frozen=True) so fingerprints are hashable and safe
      to cache/store.
    - from_playwright_element() will live in the Playwright wrapper (Phase 2),
      keeping this module dependency-free.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BoundingBox:
    """Axis-aligned bounding box of an element's visual position."""

    x: float
    y: float
    width: float
    height: float

    @property
    def center(self) -> tuple[float, float]:
        """Return the center point of the bounding box."""
        return (self.x + self.width / 2, self.y + self.height / 2)


@dataclass(frozen=True)
class ElementFingerprint:
    """Rich identity snapshot of a DOM element.

    Attributes:
        tag: HTML tag name, lowercased (e.g. "button", "input", "div").
        text: Visible text content, stripped and lowercased.
        attributes: Frozen set of (name, value) pairs for all HTML attributes.
        dom_path: Tuple of ancestor tag names from root to this element.
        siblings: Tuple of tag names of immediate sibling elements.
        bbox: Bounding box at fingerprint time, or None if not available.
        locator: The original locator string used to find this element.
        test_id: Identifier for the test that created this fingerprint.
    """

    tag: str
    text: str
    attributes: frozenset[tuple[str, str]]
    dom_path: tuple[str, ...]
    siblings: tuple[str, ...]
    bbox: BoundingBox | None = None
    locator: str = ""
    test_id: str = ""

    @staticmethod
    def _normalize_text(text: str | None) -> str:
        """Normalize text content: strip, lowercase, collapse whitespace."""
        if not text:
            return ""
        return " ".join(text.strip().lower().split())

    @staticmethod
    def _normalize_tag(tag: str | None) -> str:
        """Normalize tag name: lowercase, strip."""
        if not tag:
            return ""
        return tag.strip().lower()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ElementFingerprint:
        """Create a fingerprint from a plain dictionary.

        Useful for reconstructing fingerprints from storage or test fixtures.
        Handles type coercion (lists -> tuples/frozensets) automatically.

        Args:
            data: Dictionary with fingerprint fields. At minimum requires
                'tag'. All other fields have sensible defaults.

        Returns:
            A new ElementFingerprint instance.
        """
        bbox_data = data.get("bbox")
        bbox: BoundingBox | None = None
        if bbox_data is not None:
            if isinstance(bbox_data, BoundingBox):
                bbox = bbox_data
            elif isinstance(bbox_data, dict):
                bbox = BoundingBox(
                    x=float(bbox_data.get("x", 0)),
                    y=float(bbox_data.get("y", 0)),
                    width=float(bbox_data.get("width", 0)),
                    height=float(bbox_data.get("height", 0)),
                )

        raw_attrs = data.get("attributes", set())
        if isinstance(raw_attrs, dict):
            attrs = frozenset(raw_attrs.items())
        elif isinstance(raw_attrs, (list, tuple)):
            attrs = frozenset(tuple(pair) for pair in raw_attrs)
        elif isinstance(raw_attrs, frozenset):
            attrs = raw_attrs
        else:
            attrs = frozenset()

        raw_dom = data.get("dom_path", ())
        dom_path = tuple(raw_dom) if not isinstance(raw_dom, tuple) else raw_dom

        raw_siblings = data.get("siblings", ())
        siblings = (
            tuple(raw_siblings) if not isinstance(raw_siblings, tuple) else raw_siblings
        )

        return cls(
            tag=cls._normalize_tag(data.get("tag", "")),
            text=cls._normalize_text(data.get("text", "")),
            attributes=attrs,
            dom_path=dom_path,
            siblings=siblings,
            bbox=bbox,
            locator=data.get("locator", ""),
            test_id=data.get("test_id", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the fingerprint to a plain dictionary for storage.

        Returns:
            Dictionary representation suitable for JSON serialization
            and SQLite storage.
        """
        result: dict[str, Any] = {
            "tag": self.tag,
            "text": self.text,
            "attributes": sorted([list(pair) for pair in self.attributes]),
            "dom_path": list(self.dom_path),
            "siblings": list(self.siblings),
            "locator": self.locator,
            "test_id": self.test_id,
        }
        if self.bbox is not None:
            result["bbox"] = {
                "x": self.bbox.x,
                "y": self.bbox.y,
                "width": self.bbox.width,
                "height": self.bbox.height,
            }
        else:
            result["bbox"] = None
        return result
