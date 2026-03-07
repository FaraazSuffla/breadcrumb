"""Self-healing Playwright page wrapper.

This module provides ``heal(page)`` — the primary user-facing API. It wraps
a standard Playwright Page so that locator actions automatically:

1. **On success**: fingerprint the resolved element and save it to storage.
2. **On failure**: retrieve the stored fingerprint, scan the DOM for candidates,
   score them, and retry with the best match above the confidence threshold.

Usage::

    from breadcrumb.playwright import heal

    def test_login(page):
        page.goto("https://app.example.com")
        heal(page).locator("#login-btn").click()   # self-heals if #login-btn changes

The wrapper is transparent — all Playwright Page methods are proxied through,
so you can mix ``heal(page)`` calls with normal ``page`` calls freely.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from breadcrumb.core.fingerprint import ElementFingerprint
from breadcrumb.core.healer import Healer, HealResult
from breadcrumb.core.storage import FingerprintStore
from breadcrumb.playwright.extractor import (
    extract_all_candidates_sync,
    extract_fingerprint_sync,
)

logger = logging.getLogger("breadcrumb.playwright")

# Default database path — in the project root alongside tests
_DEFAULT_DB_NAME = ".breadcrumb.db"


def heal(
    page: Any,
    test_id: str = "",
    db_path: Path | str | None = None,
    threshold: float = 0.5,
    weights: dict[str, float] | None = None,
    healer: Healer | None = None,
) -> HealablePage:
    """Wrap a Playwright Page with self-healing locator support.

    This is the primary entry point for users. Call it once and use the
    returned page for all locator operations in a test.

    Args:
        page: A Playwright sync Page object.
        test_id: Identifier for the current test. If empty, the wrapper
            will attempt to infer it from the pytest request context.
        db_path: Path to the SQLite database. Defaults to .breadcrumb.db
            in the current working directory.
        threshold: Minimum similarity score to accept a healed element.
        weights: Custom weights for similarity scoring signals.
        healer: Pre-configured Healer instance. If provided, db_path,
            threshold, and weights are ignored.

    Returns:
        A HealablePage that proxies all Page methods with self-healing.
    """
    if healer is None:
        resolved_path = Path(db_path) if db_path is not None else Path(_DEFAULT_DB_NAME)
        store = FingerprintStore(resolved_path)
        healer = Healer(store=store, threshold=threshold, weights=weights)

    resolved_test_id = test_id
    if not resolved_test_id:
        import inspect
        import os
        frame = inspect.stack()
        for f in frame[1:]:
            fname = f.filename if hasattr(f, "filename") else f[1]
            func = f.function if hasattr(f, "function") else f[3]
            if fname and not fname.endswith("page_wrapper.py"):
                resolved_test_id = f"{os.path.basename(fname)}::{func}"
                break
        if not resolved_test_id:
            resolved_test_id = "breadcrumb_default"
    return HealablePage(page=page, healer=healer, test_id=resolved_test_id)


class HealablePage:
    """Playwright Page wrapper that adds self-healing to locator operations.

    This class proxies all attribute access to the underlying Playwright Page,
    but intercepts ``locator()`` calls to return a ``HealableLocator`` instead.

    Attributes:
        _page: The wrapped Playwright Page.
        _healer: The Healer instance for fingerprint storage and healing.
        _test_id: The current test identifier.
    """

    def __init__(
        self,
        page: Any,
        healer: Healer,
        test_id: str = "",
    ) -> None:
        self._page = page
        self._healer = healer
        self._test_id = test_id

    @property
    def page(self) -> Any:
        """Access the underlying Playwright Page directly."""
        return self._page

    @property
    def healer(self) -> Healer:
        """Access the Healer instance."""
        return self._healer

    @property
    def test_id(self) -> str:
        """The current test identifier."""
        return self._test_id

    @test_id.setter
    def test_id(self, value: str) -> None:
        self._test_id = value

    def locator(self, selector: str, **kwargs: Any) -> HealableLocator:
        """Create a self-healing locator.

        Wraps Page.locator() to return a HealableLocator that fingerprints
        on success and heals on failure.

        Args:
            selector: CSS selector, XPath, text, or other Playwright selector.
            **kwargs: Additional arguments passed to Page.locator().

        Returns:
            A HealableLocator wrapping the Playwright Locator.
        """
        pw_locator = self._page.locator(selector, **kwargs)
        return HealableLocator(
            locator=pw_locator,
            selector=selector,
            page=self,
        )

    def get_by_role(self, role: str, **kwargs: Any) -> HealableLocator:
        """Wrap Page.get_by_role() with self-healing."""
        pw_locator = self._page.get_by_role(role, **kwargs)
        selector = f"role={role}"
        return HealableLocator(locator=pw_locator, selector=selector, page=self)

    def get_by_text(self, text: str, **kwargs: Any) -> HealableLocator:
        """Wrap Page.get_by_text() with self-healing."""
        pw_locator = self._page.get_by_text(text, **kwargs)
        selector = f"text={text}"
        return HealableLocator(locator=pw_locator, selector=selector, page=self)

    def get_by_label(self, text: str, **kwargs: Any) -> HealableLocator:
        """Wrap Page.get_by_label() with self-healing."""
        pw_locator = self._page.get_by_label(text, **kwargs)
        selector = f"label={text}"
        return HealableLocator(locator=pw_locator, selector=selector, page=self)

    def get_by_placeholder(self, text: str, **kwargs: Any) -> HealableLocator:
        """Wrap Page.get_by_placeholder() with self-healing."""
        pw_locator = self._page.get_by_placeholder(text, **kwargs)
        selector = f"placeholder={text}"
        return HealableLocator(locator=pw_locator, selector=selector, page=self)

    def get_by_test_id(self, test_id: str) -> HealableLocator:
        """Wrap Page.get_by_test_id() with self-healing."""
        pw_locator = self._page.get_by_test_id(test_id)
        selector = f"test-id={test_id}"
        return HealableLocator(locator=pw_locator, selector=selector, page=self)

    def __getattr__(self, name: str) -> Any:
        """Proxy all other attribute access to the underlying Page."""
        return getattr(self._page, name)


class HealableLocator:
    """Playwright Locator wrapper with self-healing on action failure.

    When an action (click, fill, etc.) is called:

    1. Try the original locator.
    2. If it succeeds, fingerprint the element and save it.
    3. If it fails, attempt healing:
       a. Load the stored fingerprint for (test_id, selector).
       b. Extract all visible elements from the page as candidates.
       c. Score candidates against the stored fingerprint.
       d. If a match exceeds the threshold, retry the action with the healed locator.
       e. If no match, re-raise the original error.
    """

    def __init__(
        self,
        locator: Any,
        selector: str,
        page: HealablePage,
    ) -> None:
        self._locator = locator
        self._selector = selector
        self._page = page

    @property
    def locator(self) -> Any:
        """The underlying Playwright Locator."""
        return self._locator

    def _fingerprint_and_save(self) -> None:
        """Fingerprint the resolved element and save to storage."""
        if not self._page.test_id:
            return
        try:
            fp = extract_fingerprint_sync(
                self._locator,
                locator_str=self._selector,
                test_id=self._page.test_id,
            )
            self._page.healer.save(fp)
        except Exception:
            # Fingerprinting failure should never break the test
            logger.debug(
                "Failed to fingerprint element for selector=%s",
                self._selector,
                exc_info=True,
            )

    def _attempt_heal(self) -> HealResult:
        """Try to heal the broken locator using stored fingerprint data."""
        if not self._page.test_id:
            return HealResult(healed=False, candidate=None, score=None, all_scores=[])

        try:
            candidates = extract_all_candidates_sync(self._page.page)
        except Exception:
            logger.debug("Failed to extract candidates for healing", exc_info=True)
            return HealResult(healed=False, candidate=None, score=None, all_scores=[])

        return self._page.healer.heal(
            test_id=self._page.test_id,
            locator=self._selector,
            candidates=candidates,
        )

    def _build_healed_selector(self, fp: ElementFingerprint) -> str:
        """Build a Playwright selector from a healed fingerprint.

        Tries to construct the most specific selector possible from
        the fingerprint data. Priority order:
        1. data-testid attribute
        2. id attribute
        3. Unique text content with tag
        4. CSS class combination with tag
        5. Tag + nth-match as fallback
        """
        attrs = dict(fp.attributes)

        # Prefer data-testid
        for attr_name in ("data-testid", "data-test-id", "data-qa"):
            if attr_name in attrs:
                return f'[{attr_name}="{attrs[attr_name]}"]'

        # Prefer id
        if "id" in attrs:
            return f"#{attrs['id']}"

        # Prefer visible text for interactive elements
        if fp.text and fp.tag in ("button", "a", "label", "h1", "h2", "h3", "h4", "h5", "h6"):
            escaped_text = fp.text.replace('"', '\\"')
            return f'{fp.tag}:has-text("{escaped_text}")'

        # Class-based selector
        if "class" in attrs:
            classes = attrs["class"].strip().split()
            if classes:
                class_selector = ".".join(classes[:3])  # Use first 3 classes max
                return f"{fp.tag}.{class_selector}"

        # Last resort: tag + role or name
        if "role" in attrs:
            return f'{fp.tag}[role="{attrs["role"]}"]'
        if "name" in attrs:
            return f'{fp.tag}[name="{attrs["name"]}"]'

        # Absolute fallback
        return fp.tag

    def _execute_with_healing(
        self,
        action_name: str,
        action_fn: Any,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute a locator action with automatic healing on failure.

        Args:
            action_name: Name of the action (for logging).
            action_fn: Callable for the action on the original locator.
            *args: Positional arguments for the action.
            **kwargs: Keyword arguments for the action.

        Returns:
            The result of the action.

        Raises:
            The original Playwright error if healing fails.
        """
        try:
            result = action_fn(*args, **kwargs)
            # Success — fingerprint and save
            self._fingerprint_and_save()
            return result
        except Exception as original_error:
            logger.info(
                "Locator failed: selector=%s action=%s, attempting heal...",
                self._selector,
                action_name,
            )

            heal_result = self._attempt_heal()

            if not heal_result.healed or heal_result.candidate is None:
                logger.info(
                    "Healing failed for selector=%s — no suitable candidate found",
                    self._selector,
                )
                raise

            # Build a new selector from the healed fingerprint
            new_selector = self._build_healed_selector(heal_result.candidate)
            logger.info(
                "Healed: %s -> %s (confidence=%.4f)",
                self._selector,
                new_selector,
                heal_result.score.total if heal_result.score else 0.0,
            )

            try:
                healed_locator = self._page.page.locator(new_selector)
                healed_action = getattr(healed_locator, action_name)
                result = healed_action(*args, **kwargs)

                # Healed action succeeded — fingerprint the healed element
                try:
                    fp = extract_fingerprint_sync(
                        healed_locator,
                        locator_str=self._selector,  # Keep original selector as key
                        test_id=self._page.test_id,
                    )
                    self._page.healer.save(fp)
                except Exception:
                    logger.debug("Failed to save healed fingerprint", exc_info=True)

                return result
            except Exception:
                logger.info(
                    "Healed selector %s also failed, raising original error",
                    new_selector,
                )
                raise original_error from None

    # ----- Playwright Locator action proxies -----

    def click(self, **kwargs: Any) -> None:
        """Click the element, with self-healing on failure."""
        self._execute_with_healing("click", self._locator.click, **kwargs)

    def dblclick(self, **kwargs: Any) -> None:
        """Double-click the element, with self-healing on failure."""
        self._execute_with_healing("dblclick", self._locator.dblclick, **kwargs)

    def fill(self, value: str, **kwargs: Any) -> None:
        """Fill the element with text, with self-healing on failure."""
        self._execute_with_healing("fill", self._locator.fill, value, **kwargs)

    def type(self, text: str, **kwargs: Any) -> None:
        """Type text into the element, with self-healing on failure."""
        self._execute_with_healing("type", self._locator.type, text, **kwargs)

    def press(self, key: str, **kwargs: Any) -> None:
        """Press a key on the element, with self-healing on failure."""
        self._execute_with_healing("press", self._locator.press, key, **kwargs)

    def check(self, **kwargs: Any) -> None:
        """Check a checkbox/radio, with self-healing on failure."""
        self._execute_with_healing("check", self._locator.check, **kwargs)

    def uncheck(self, **kwargs: Any) -> None:
        """Uncheck a checkbox, with self-healing on failure."""
        self._execute_with_healing("uncheck", self._locator.uncheck, **kwargs)

    def select_option(self, values: Any = None, **kwargs: Any) -> list[str]:
        """Select option(s) in a <select>, with self-healing on failure."""
        return self._execute_with_healing(
            "select_option",
            self._locator.select_option,
            values,
            **kwargs,
        )

    def hover(self, **kwargs: Any) -> None:
        """Hover over the element, with self-healing on failure."""
        self._execute_with_healing("hover", self._locator.hover, **kwargs)

    def focus(self, **kwargs: Any) -> None:
        """Focus the element, with self-healing on failure."""
        self._execute_with_healing("focus", self._locator.focus, **kwargs)

    def scroll_into_view_if_needed(self, **kwargs: Any) -> None:
        """Scroll element into view, with self-healing on failure."""
        self._execute_with_healing(
            "scroll_into_view_if_needed",
            self._locator.scroll_into_view_if_needed,
            **kwargs,
        )

    def input_value(self, **kwargs: Any) -> str:
        """Get input value, with self-healing on failure."""
        return self._execute_with_healing(
            "input_value",
            self._locator.input_value,
            **kwargs,
        )

    def inner_text(self, **kwargs: Any) -> str:
        """Get inner text, with self-healing on failure."""
        return self._execute_with_healing(
            "inner_text",
            self._locator.inner_text,
            **kwargs,
        )

    def inner_html(self, **kwargs: Any) -> str:
        """Get inner HTML, with self-healing on failure."""
        return self._execute_with_healing(
            "inner_html",
            self._locator.inner_html,
            **kwargs,
        )

    def text_content(self, **kwargs: Any) -> str | None:
        """Get text content, with self-healing on failure."""
        return self._execute_with_healing(
            "text_content",
            self._locator.text_content,
            **kwargs,
        )

    def get_attribute(self, name: str, **kwargs: Any) -> str | None:
        """Get attribute value, with self-healing on failure."""
        return self._execute_with_healing(
            "get_attribute",
            self._locator.get_attribute,
            name,
            **kwargs,
        )

    def is_visible(self, **kwargs: Any) -> bool:
        """Check visibility, with self-healing on failure."""
        return self._execute_with_healing(
            "is_visible",
            self._locator.is_visible,
            **kwargs,
        )

    def is_enabled(self, **kwargs: Any) -> bool:
        """Check if enabled, with self-healing on failure."""
        return self._execute_with_healing(
            "is_enabled",
            self._locator.is_enabled,
            **kwargs,
        )

    def is_checked(self, **kwargs: Any) -> bool:
        """Check if checked, with self-healing on failure."""
        return self._execute_with_healing(
            "is_checked",
            self._locator.is_checked,
            **kwargs,
        )

    def count(self) -> int:
        """Return the number of matching elements (no healing — count can't fail)."""
        return self._locator.count()

    def first(self) -> HealableLocator:
        """Return a HealableLocator pointing to the first match."""
        return HealableLocator(
            locator=self._locator.first,
            selector=f"{self._selector} >> first",
            page=self._page,
        )

    def last(self) -> HealableLocator:
        """Return a HealableLocator pointing to the last match."""
        return HealableLocator(
            locator=self._locator.last,
            selector=f"{self._selector} >> last",
            page=self._page,
        )

    def nth(self, index: int) -> HealableLocator:
        """Return a HealableLocator pointing to the nth match."""
        return HealableLocator(
            locator=self._locator.nth(index),
            selector=f"{self._selector} >> nth={index}",
            page=self._page,
        )

    def __getattr__(self, name: str) -> Any:
        """Proxy all other attribute access to the underlying Locator."""
        return getattr(self._locator, name)

