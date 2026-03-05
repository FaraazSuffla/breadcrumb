"""Tests for breadcrumb.playwright.page_wrapper."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from breadcrumb.core.fingerprint import BoundingBox, ElementFingerprint
from breadcrumb.core.healer import Healer
from breadcrumb.core.storage import FingerprintStore
from breadcrumb.playwright.page_wrapper import (
    HealableLocator,
    HealablePage,
    heal,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_page() -> MagicMock:
    """A mock Playwright Page object."""
    page = MagicMock()
    page.locator.return_value = MagicMock()
    page.get_by_role.return_value = MagicMock()
    page.get_by_text.return_value = MagicMock()
    page.get_by_label.return_value = MagicMock()
    page.get_by_placeholder.return_value = MagicMock()
    page.get_by_test_id.return_value = MagicMock()
    return page


@pytest.fixture
def store(tmp_path: Path):
    """A real FingerprintStore with a temp database."""
    s = FingerprintStore(tmp_path / "test.db")
    yield s
    s.close()


@pytest.fixture
def healer(store: FingerprintStore) -> Healer:  # type: ignore[override]
    """A real Healer backed by the temp store."""
    return Healer(store=store, threshold=0.5)


@pytest.fixture
def healable_page(mock_page: MagicMock, healer: Healer) -> HealablePage:
    """A HealablePage with a mock Playwright page and real healer."""
    return HealablePage(page=mock_page, healer=healer, test_id="test_login")


# ---------------------------------------------------------------------------
# heal() factory function
# ---------------------------------------------------------------------------


class TestHealFactory:
    def test_creates_healable_page(self, mock_page: MagicMock, tmp_path: Path) -> None:
        hp = heal(mock_page, test_id="test_x", db_path=tmp_path / "h.db")
        assert isinstance(hp, HealablePage)
        assert hp.test_id == "test_x"

    def test_uses_provided_healer(
        self,
        mock_page: MagicMock,
        healer: Healer,
    ) -> None:
        hp = heal(mock_page, healer=healer)
        assert hp.healer is healer

    def test_default_db_path(self, mock_page: MagicMock) -> None:
        hp = heal(mock_page, test_id="t")
        assert isinstance(hp, HealablePage)


# ---------------------------------------------------------------------------
# HealablePage
# ---------------------------------------------------------------------------


class TestHealablePage:
    def test_locator_returns_healable_locator(
        self,
        healable_page: HealablePage,
    ) -> None:
        loc = healable_page.locator("#btn")
        assert isinstance(loc, HealableLocator)

    def test_get_by_role_returns_healable_locator(
        self,
        healable_page: HealablePage,
    ) -> None:
        loc = healable_page.get_by_role("button")
        assert isinstance(loc, HealableLocator)

    def test_get_by_text_returns_healable_locator(
        self,
        healable_page: HealablePage,
    ) -> None:
        loc = healable_page.get_by_text("Submit")
        assert isinstance(loc, HealableLocator)

    def test_get_by_label_returns_healable_locator(
        self,
        healable_page: HealablePage,
    ) -> None:
        loc = healable_page.get_by_label("Email")
        assert isinstance(loc, HealableLocator)

    def test_get_by_placeholder_returns_healable_locator(
        self,
        healable_page: HealablePage,
    ) -> None:
        loc = healable_page.get_by_placeholder("Enter name")
        assert isinstance(loc, HealableLocator)

    def test_get_by_test_id_returns_healable_locator(
        self,
        healable_page: HealablePage,
    ) -> None:
        loc = healable_page.get_by_test_id("submit-btn")
        assert isinstance(loc, HealableLocator)

    def test_proxies_unknown_attributes(
        self,
        healable_page: HealablePage,
        mock_page: MagicMock,
    ) -> None:
        mock_page.url = "https://example.com"
        assert healable_page.url == "https://example.com"

    def test_test_id_settable(self, healable_page: HealablePage) -> None:
        healable_page.test_id = "test_checkout"
        assert healable_page.test_id == "test_checkout"

    def test_page_property(
        self,
        healable_page: HealablePage,
        mock_page: MagicMock,
    ) -> None:
        assert healable_page.page is mock_page

    def test_healer_property(
        self,
        healable_page: HealablePage,
        healer: Healer,
    ) -> None:
        assert healable_page.healer is healer


# ---------------------------------------------------------------------------
# HealableLocator — success path (fingerprint and save)
# ---------------------------------------------------------------------------


class TestHealableLocatorSuccess:
    @patch("breadcrumb.playwright.page_wrapper.extract_fingerprint_sync")
    def test_click_calls_original_and_fingerprints(
        self,
        mock_extract: MagicMock,
        healable_page: HealablePage,
    ) -> None:
        mock_extract.return_value = ElementFingerprint(
            tag="button",
            text="submit",
            attributes=frozenset(),
            dom_path=(),
            siblings=(),
            locator="#btn",
            test_id="test_login",
        )

        loc = healable_page.locator("#btn")
        loc.click()

        # Original Playwright click was called
        loc.locator.click.assert_called_once()
        # Fingerprint was extracted
        mock_extract.assert_called_once()

    @patch("breadcrumb.playwright.page_wrapper.extract_fingerprint_sync")
    def test_fill_passes_value(
        self,
        mock_extract: MagicMock,
        healable_page: HealablePage,
    ) -> None:
        mock_extract.return_value = ElementFingerprint(
            tag="input",
            text="",
            attributes=frozenset(),
            dom_path=(),
            siblings=(),
            locator=".email",
            test_id="test_login",
        )

        loc = healable_page.locator(".email")
        loc.fill("user@test.com")

        loc.locator.fill.assert_called_once_with("user@test.com")

    @patch("breadcrumb.playwright.page_wrapper.extract_fingerprint_sync")
    def test_fingerprint_failure_doesnt_break_test(
        self,
        mock_extract: MagicMock,
        healable_page: HealablePage,
    ) -> None:
        mock_extract.side_effect = RuntimeError("extraction failed")

        loc = healable_page.locator("#btn")
        # Should not raise — fingerprint failure is swallowed
        loc.click()
        loc.locator.click.assert_called_once()

    def test_no_fingerprint_when_test_id_empty(
        self,
        mock_page: MagicMock,
        healer: Healer,
    ) -> None:
        hp = HealablePage(page=mock_page, healer=healer, test_id="")
        loc = hp.locator("#btn")

        with patch("breadcrumb.playwright.page_wrapper.extract_fingerprint_sync") as mock_extract:
            loc.click()
            mock_extract.assert_not_called()


# ---------------------------------------------------------------------------
# HealableLocator — failure + healing path
# ---------------------------------------------------------------------------


class TestHealableLocatorHealing:
    def _make_fp(self, **overrides: Any) -> ElementFingerprint:
        defaults: dict[str, Any] = {
            "tag": "button",
            "text": "submit",
            "attributes": frozenset({("id", "submit-btn"), ("class", "btn primary")}),
            "dom_path": ("html", "body", "form", "button"),
            "siblings": ("input", "label"),
            "bbox": BoundingBox(x=100, y=200, width=80, height=40),
            "locator": "#submit-btn",
            "test_id": "test_login",
        }
        defaults.update(overrides)
        return ElementFingerprint(**defaults)

    @patch("breadcrumb.playwright.page_wrapper.extract_fingerprint_sync")
    @patch("breadcrumb.playwright.page_wrapper.extract_all_candidates_sync")
    def test_heals_on_locator_failure(
        self,
        mock_candidates: MagicMock,
        mock_extract: MagicMock,
        healable_page: HealablePage,
    ) -> None:
        # Save a fingerprint first
        stored_fp = self._make_fp()
        healable_page.healer.save(stored_fp)

        # Mock the original locator failing
        original_locator = healable_page.page.locator.return_value
        original_locator.click.side_effect = Exception("Element not found")

        # Mock candidate extraction returning a matching element
        candidate_fp = self._make_fp(
            attributes=frozenset({("id", "submit-btn-v2"), ("class", "btn primary")}),
        )
        mock_candidates.return_value = [candidate_fp]

        # Mock the healed locator succeeding
        healed_locator = MagicMock()
        healable_page.page.locator.side_effect = [original_locator, healed_locator]

        mock_extract.return_value = candidate_fp

        loc = healable_page.locator("#submit-btn")
        loc.click()

        # The healed locator's click was called
        healed_locator.click.assert_called_once()

    @patch("breadcrumb.playwright.page_wrapper.extract_all_candidates_sync")
    def test_raises_original_error_when_healing_fails(
        self,
        mock_candidates: MagicMock,
        healable_page: HealablePage,
    ) -> None:
        # No stored fingerprint — healing should fail
        original_locator = healable_page.page.locator.return_value
        original_locator.click.side_effect = Exception("Element not found")
        mock_candidates.return_value = []

        loc = healable_page.locator("#nonexistent")
        with pytest.raises(Exception, match="Element not found"):
            loc.click()

    @patch("breadcrumb.playwright.page_wrapper.extract_all_candidates_sync")
    def test_raises_when_no_candidates_above_threshold(
        self,
        mock_candidates: MagicMock,
        healable_page: HealablePage,
    ) -> None:
        # Save a fingerprint
        stored_fp = self._make_fp()
        healable_page.healer.save(stored_fp)

        # Original fails
        original_locator = healable_page.page.locator.return_value
        original_locator.click.side_effect = Exception("Element not found")

        # Candidates are completely different — low similarity
        bad_candidate = self._make_fp(
            tag="div",
            text="unrelated",
            attributes=frozenset({("role", "alert")}),
            dom_path=("html", "body", "aside", "div"),
            siblings=("span",),
            bbox=BoundingBox(x=800, y=800, width=200, height=100),
        )
        mock_candidates.return_value = [bad_candidate]

        loc = healable_page.locator("#submit-btn")
        with pytest.raises(Exception, match="Element not found"):
            loc.click()

    def test_no_healing_when_test_id_empty(
        self,
        mock_page: MagicMock,
        healer: Healer,
    ) -> None:
        hp = HealablePage(page=mock_page, healer=healer, test_id="")
        original_locator = mock_page.locator.return_value
        original_locator.click.side_effect = Exception("Element not found")

        loc = hp.locator("#btn")
        with pytest.raises(Exception, match="Element not found"):
            loc.click()


# ---------------------------------------------------------------------------
# HealableLocator — selector building
# ---------------------------------------------------------------------------


class TestSelectorBuilding:
    def _make_loc(self, page: HealablePage) -> HealableLocator:
        return HealableLocator(
            locator=MagicMock(),
            selector="#test",
            page=page,
        )

    def test_prefers_data_testid(self, healable_page: HealablePage) -> None:
        loc = self._make_loc(healable_page)
        fp = ElementFingerprint(
            tag="button",
            text="click",
            attributes=frozenset({("data-testid", "submit"), ("id", "btn")}),
            dom_path=(),
            siblings=(),
        )
        selector = loc._build_healed_selector(fp)
        assert selector == '[data-testid="submit"]'

    def test_falls_back_to_id(self, healable_page: HealablePage) -> None:
        loc = self._make_loc(healable_page)
        fp = ElementFingerprint(
            tag="button",
            text="click",
            attributes=frozenset({("id", "my-btn")}),
            dom_path=(),
            siblings=(),
        )
        selector = loc._build_healed_selector(fp)
        assert selector == "#my-btn"

    def test_falls_back_to_text_for_interactive(
        self,
        healable_page: HealablePage,
    ) -> None:
        loc = self._make_loc(healable_page)
        fp = ElementFingerprint(
            tag="button",
            text="sign in",
            attributes=frozenset(),
            dom_path=(),
            siblings=(),
        )
        selector = loc._build_healed_selector(fp)
        assert 'has-text("sign in")' in selector

    def test_falls_back_to_class(self, healable_page: HealablePage) -> None:
        loc = self._make_loc(healable_page)
        fp = ElementFingerprint(
            tag="div",
            text="",
            attributes=frozenset({("class", "card primary")}),
            dom_path=(),
            siblings=(),
        )
        selector = loc._build_healed_selector(fp)
        assert selector == "div.card.primary"

    def test_falls_back_to_role(self, healable_page: HealablePage) -> None:
        loc = self._make_loc(healable_page)
        fp = ElementFingerprint(
            tag="nav",
            text="",
            attributes=frozenset({("role", "navigation")}),
            dom_path=(),
            siblings=(),
        )
        selector = loc._build_healed_selector(fp)
        assert selector == 'nav[role="navigation"]'

    def test_absolute_fallback_to_tag(self, healable_page: HealablePage) -> None:
        loc = self._make_loc(healable_page)
        fp = ElementFingerprint(
            tag="section",
            text="",
            attributes=frozenset(),
            dom_path=(),
            siblings=(),
        )
        selector = loc._build_healed_selector(fp)
        assert selector == "section"


# ---------------------------------------------------------------------------
# HealableLocator — navigation (first, last, nth)
# ---------------------------------------------------------------------------


class TestLocatorNavigation:
    def test_first_returns_healable(self, healable_page: HealablePage) -> None:
        loc = healable_page.locator(".item")
        first = loc.first()
        assert isinstance(first, HealableLocator)

    def test_last_returns_healable(self, healable_page: HealablePage) -> None:
        loc = healable_page.locator(".item")
        last = loc.last()
        assert isinstance(last, HealableLocator)

    def test_nth_returns_healable(self, healable_page: HealablePage) -> None:
        loc = healable_page.locator(".item")
        nth = loc.nth(2)
        assert isinstance(nth, HealableLocator)

    def test_count_proxies_directly(self, healable_page: HealablePage) -> None:
        loc = healable_page.locator(".item")
        loc.locator.count.return_value = 5
        assert loc.count() == 5

    def test_getattr_proxies_to_underlying(self, healable_page: HealablePage) -> None:
        loc = healable_page.locator("#btn")
        loc.locator.bounding_box.return_value = {"x": 0, "y": 0, "w": 10, "h": 10}
        result = loc.bounding_box()
        assert result == {"x": 0, "y": 0, "w": 10, "h": 10}


# ---------------------------------------------------------------------------
# Coverage gap: selector building — name attribute branch
# ---------------------------------------------------------------------------


class TestSelectorBuildingNameBranch:
    def _make_loc(self, page: HealablePage) -> HealableLocator:
        return HealableLocator(locator=MagicMock(), selector="#test", page=page)

    def test_falls_back_to_name_attribute(self, healable_page: HealablePage) -> None:
        loc = self._make_loc(healable_page)
        fp = ElementFingerprint(
            tag="input",
            text="",
            attributes=frozenset({("name", "username")}),
            dom_path=(),
            siblings=(),
        )
        selector = loc._build_healed_selector(fp)
        assert selector == 'input[name="username"]'


# ---------------------------------------------------------------------------
# Coverage gap: remaining action proxy methods
# ---------------------------------------------------------------------------


class TestRemainingActions:
    def _fp(self, tag: str = "button", locator: str = "#btn") -> ElementFingerprint:
        return ElementFingerprint(
            tag=tag,
            text="",
            attributes=frozenset(),
            dom_path=(),
            siblings=(),
            locator=locator,
            test_id="test_login",
        )

    @patch("breadcrumb.playwright.page_wrapper.extract_fingerprint_sync")
    def test_dblclick(self, mock_extract: MagicMock, healable_page: HealablePage) -> None:
        mock_extract.return_value = self._fp()
        loc = healable_page.locator("#btn")
        loc.dblclick()
        loc.locator.dblclick.assert_called_once()

    @patch("breadcrumb.playwright.page_wrapper.extract_fingerprint_sync")
    def test_type(self, mock_extract: MagicMock, healable_page: HealablePage) -> None:
        mock_extract.return_value = self._fp("input", "#inp")
        loc = healable_page.locator("#inp")
        loc.type("hello")
        loc.locator.type.assert_called_once_with("hello")

    @patch("breadcrumb.playwright.page_wrapper.extract_fingerprint_sync")
    def test_press(self, mock_extract: MagicMock, healable_page: HealablePage) -> None:
        mock_extract.return_value = self._fp("input", "#inp")
        loc = healable_page.locator("#inp")
        loc.press("Enter")
        loc.locator.press.assert_called_once_with("Enter")

    @patch("breadcrumb.playwright.page_wrapper.extract_fingerprint_sync")
    def test_check(self, mock_extract: MagicMock, healable_page: HealablePage) -> None:
        mock_extract.return_value = self._fp("input", "#chk")
        loc = healable_page.locator("#chk")
        loc.check()
        loc.locator.check.assert_called_once()

    @patch("breadcrumb.playwright.page_wrapper.extract_fingerprint_sync")
    def test_uncheck(self, mock_extract: MagicMock, healable_page: HealablePage) -> None:
        mock_extract.return_value = self._fp("input", "#chk")
        loc = healable_page.locator("#chk")
        loc.uncheck()
        loc.locator.uncheck.assert_called_once()

    @patch("breadcrumb.playwright.page_wrapper.extract_fingerprint_sync")
    def test_hover(self, mock_extract: MagicMock, healable_page: HealablePage) -> None:
        mock_extract.return_value = self._fp("div", "#d")
        loc = healable_page.locator("#d")
        loc.hover()
        loc.locator.hover.assert_called_once()

    @patch("breadcrumb.playwright.page_wrapper.extract_fingerprint_sync")
    def test_focus(self, mock_extract: MagicMock, healable_page: HealablePage) -> None:
        mock_extract.return_value = self._fp("input", "#inp")
        loc = healable_page.locator("#inp")
        loc.focus()
        loc.locator.focus.assert_called_once()

    @patch("breadcrumb.playwright.page_wrapper.extract_fingerprint_sync")
    def test_scroll_into_view_if_needed(self, mock_extract: MagicMock, healable_page: HealablePage) -> None:
        mock_extract.return_value = self._fp("div", "#d")
        loc = healable_page.locator("#d")
        loc.scroll_into_view_if_needed()
        loc.locator.scroll_into_view_if_needed.assert_called_once()

    @patch("breadcrumb.playwright.page_wrapper.extract_fingerprint_sync")
    def test_input_value(self, mock_extract: MagicMock, healable_page: HealablePage) -> None:
        mock_extract.return_value = self._fp("input", "#inp")
        healable_page.page.locator.return_value.input_value.return_value = "test@example.com"
        loc = healable_page.locator("#inp")
        assert loc.input_value() == "test@example.com"

    @patch("breadcrumb.playwright.page_wrapper.extract_fingerprint_sync")
    def test_inner_text(self, mock_extract: MagicMock, healable_page: HealablePage) -> None:
        mock_extract.return_value = self._fp("p", "#p")
        healable_page.page.locator.return_value.inner_text.return_value = "hello"
        loc = healable_page.locator("#p")
        assert loc.inner_text() == "hello"

    @patch("breadcrumb.playwright.page_wrapper.extract_fingerprint_sync")
    def test_inner_html(self, mock_extract: MagicMock, healable_page: HealablePage) -> None:
        mock_extract.return_value = self._fp("div", "#d")
        healable_page.page.locator.return_value.inner_html.return_value = "<span>hi</span>"
        loc = healable_page.locator("#d")
        assert loc.inner_html() == "<span>hi</span>"

    @patch("breadcrumb.playwright.page_wrapper.extract_fingerprint_sync")
    def test_text_content(self, mock_extract: MagicMock, healable_page: HealablePage) -> None:
        mock_extract.return_value = self._fp("p", "#p")
        healable_page.page.locator.return_value.text_content.return_value = "content"
        loc = healable_page.locator("#p")
        assert loc.text_content() == "content"

    @patch("breadcrumb.playwright.page_wrapper.extract_fingerprint_sync")
    def test_get_attribute(self, mock_extract: MagicMock, healable_page: HealablePage) -> None:
        mock_extract.return_value = self._fp("a", "#a")
        healable_page.page.locator.return_value.get_attribute.return_value = "/path"
        loc = healable_page.locator("#a")
        assert loc.get_attribute("href") == "/path"

    @patch("breadcrumb.playwright.page_wrapper.extract_fingerprint_sync")
    def test_is_visible(self, mock_extract: MagicMock, healable_page: HealablePage) -> None:
        mock_extract.return_value = self._fp("div", "#d")
        healable_page.page.locator.return_value.is_visible.return_value = True
        loc = healable_page.locator("#d")
        assert loc.is_visible() is True

    @patch("breadcrumb.playwright.page_wrapper.extract_fingerprint_sync")
    def test_is_enabled(self, mock_extract: MagicMock, healable_page: HealablePage) -> None:
        mock_extract.return_value = self._fp()
        healable_page.page.locator.return_value.is_enabled.return_value = True
        loc = healable_page.locator("#btn")
        assert loc.is_enabled() is True

    @patch("breadcrumb.playwright.page_wrapper.extract_fingerprint_sync")
    def test_is_checked(self, mock_extract: MagicMock, healable_page: HealablePage) -> None:
        mock_extract.return_value = self._fp("input", "#chk")
        healable_page.page.locator.return_value.is_checked.return_value = False
        loc = healable_page.locator("#chk")
        assert loc.is_checked() is False

    @patch("breadcrumb.playwright.page_wrapper.extract_fingerprint_sync")
    def test_select_option(self, mock_extract: MagicMock, healable_page: HealablePage) -> None:
        mock_extract.return_value = self._fp("select", "#sel")
        healable_page.page.locator.return_value.select_option.return_value = ["opt1"]
        loc = healable_page.locator("#sel")
        assert loc.select_option("opt1") == ["opt1"]


# ---------------------------------------------------------------------------
# Coverage gap: healed selector also fails → raises original error
# ---------------------------------------------------------------------------


class TestHealedActionFails:
    def _make_fp(self, **overrides: Any) -> ElementFingerprint:
        defaults: dict[str, Any] = {
            "tag": "button",
            "text": "submit",
            "attributes": frozenset({("id", "submit-btn"), ("class", "btn")}),
            "dom_path": ("html", "body", "form", "button"),
            "siblings": ("input",),
            "locator": "#submit-btn",
            "test_id": "test_login",
        }
        defaults.update(overrides)
        return ElementFingerprint(**defaults)

    @patch("breadcrumb.playwright.page_wrapper.extract_fingerprint_sync")
    @patch("breadcrumb.playwright.page_wrapper.extract_all_candidates_sync")
    def test_raises_original_when_healed_selector_also_fails(
        self,
        mock_candidates: MagicMock,
        mock_extract: MagicMock,
        healable_page: HealablePage,
    ) -> None:
        stored_fp = self._make_fp()
        healable_page.healer.save(stored_fp)

        original_locator = MagicMock()
        original_error = Exception("original locator broken")
        original_locator.click.side_effect = original_error

        candidate_fp = self._make_fp(attributes=frozenset({("id", "submit-btn-v2"), ("class", "btn")}))
        mock_candidates.return_value = [candidate_fp]

        healed_locator = MagicMock()
        healed_locator.click.side_effect = Exception("healed locator also broken")
        healable_page.page.locator.side_effect = [original_locator, healed_locator]

        mock_extract.return_value = candidate_fp

        loc = HealableLocator(
            locator=original_locator,
            selector="#submit-btn",
            page=healable_page,
        )
        with pytest.raises(Exception, match="original locator broken"):
            loc.click()

    @patch("breadcrumb.playwright.page_wrapper.extract_all_candidates_sync")
    def test_raises_when_candidate_extraction_fails(
        self,
        mock_candidates: MagicMock,
        healable_page: HealablePage,
    ) -> None:
        """Cover lines 229-231: extraction raises during healing."""
        stored_fp = self._make_fp()
        healable_page.healer.save(stored_fp)

        original_locator = MagicMock()
        original_locator.click.side_effect = Exception("locator broken")
        healable_page.page.locator.return_value = original_locator

        # Candidate extraction itself fails
        mock_candidates.side_effect = RuntimeError("page crashed")

        loc = HealableLocator(
            locator=original_locator,
            selector="#submit-btn",
            page=healable_page,
        )
        with pytest.raises(Exception, match="locator broken"):
            loc.click()

    @patch("breadcrumb.playwright.page_wrapper.extract_fingerprint_sync")
    @patch("breadcrumb.playwright.page_wrapper.extract_all_candidates_sync")
    def test_healed_fingerprint_save_failure_is_swallowed(
        self,
        mock_candidates: MagicMock,
        mock_extract: MagicMock,
        healable_page: HealablePage,
    ) -> None:
        """Cover lines 346-347: fingerprint save after successful heal raises."""
        stored_fp = self._make_fp()
        healable_page.healer.save(stored_fp)

        original_locator = MagicMock()
        original_locator.click.side_effect = Exception("locator broken")

        candidate_fp = self._make_fp(attributes=frozenset({("id", "submit-btn-v2"), ("class", "btn")}))
        mock_candidates.return_value = [candidate_fp]

        # Healed locator succeeds on click
        healed_locator = MagicMock()
        healed_locator.click.return_value = None
        # page.locator() is only called once (for the healed selector)
        healable_page.page.locator.return_value = healed_locator

        # Fingerprint extraction after heal raises — should be swallowed (lines 346-347)
        mock_extract.side_effect = RuntimeError("extraction failed post-heal")

        loc = HealableLocator(
            locator=original_locator,
            selector="#submit-btn",
            page=healable_page,
        )
        # Should NOT raise — the save failure is silently logged
        loc.click()
        healed_locator.click.assert_called_once()
