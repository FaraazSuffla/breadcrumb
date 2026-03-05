"""End-to-end integration tests for the self-healing workflow.

Run with:
    pytest tests/test_integration.py --integration

These tests use real Playwright + Chromium and load the demo_app HTML pages
directly from disk (no server required). They verify that the full
fingerprint → break → heal cycle works correctly.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from breadcrumb.core.storage import FingerprintStore
from breadcrumb.playwright.page_wrapper import HealablePage, heal

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        yield b
        b.close()


@pytest.fixture
def page(browser):
    p = browser.new_page()
    yield p
    p.close()


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_healed(raw_page, db: Path, test_id: str) -> HealablePage:
    return heal(raw_page, test_id=test_id, db_path=db, threshold=0.4)


# ---------------------------------------------------------------------------
# Test: fingerprint is saved on first interaction
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestFingerprintSaving:
    def test_fingerprint_saved_after_click(self, page, v1_url, db_path):
        hp = _make_healed(page, db_path, "test_fingerprint_saving")
        page.goto(v1_url)

        hp.locator("#login-btn").click()

        store = FingerprintStore(db_path)
        fp = store.load_fingerprint("test_fingerprint_saving", "#login-btn")
        store.close()

        assert fp is not None
        assert fp.tag == "button"
        assert fp.locator == "#login-btn"
        assert fp.test_id == "test_fingerprint_saving"

    def test_fingerprint_saved_after_fill(self, page, v1_url, db_path):
        hp = _make_healed(page, db_path, "test_fill")
        page.goto(v1_url)

        hp.locator("#email-input").fill("test@example.com")

        store = FingerprintStore(db_path)
        fp = store.load_fingerprint("test_fill", "#email-input")
        store.close()

        assert fp is not None
        assert fp.tag == "input"

    def test_fingerprint_contains_text_content(self, page, v1_url, db_path):
        hp = _make_healed(page, db_path, "test_text")
        page.goto(v1_url)

        hp.locator("#login-btn").click()

        store = FingerprintStore(db_path)
        fp = store.load_fingerprint("test_text", "#login-btn")
        store.close()

        assert fp is not None
        assert "sign in" in fp.text

    def test_fingerprint_persists_across_healer_instances(self, page, v1_url, db_path):
        """Fingerprint written by one Healer is readable by another."""
        hp1 = _make_healed(page, db_path, "test_persist")
        page.goto(v1_url)
        hp1.locator("#login-btn").click()
        hp1.healer.store.close()

        # New healer, same DB
        store = FingerprintStore(db_path)
        fp = store.load_fingerprint("test_persist", "#login-btn")
        store.close()

        assert fp is not None
        assert fp.tag == "button"


# ---------------------------------------------------------------------------
# Test: healing on locator failure
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestHealing:
    def _fingerprint_on_v1(self, page, v1_url, db_path, test_id, selector):
        """Load v1, interact with selector to save fingerprint, close store."""
        hp = _make_healed(page, db_path, test_id)
        page.goto(v1_url)
        # Use the underlying page to click — we just want the fingerprint saved
        hp.locator(selector).click()
        hp.healer.store.close()

    def test_heals_id_rename(self, page, v1_url, v2_url, db_path):
        """#login-btn renamed to #auth-button — should heal via data-testid/text match."""
        test_id = "test_heals_id_rename"
        self._fingerprint_on_v1(page, v1_url, db_path, test_id, "#login-btn")

        # Now load v2 (the "broken" version) and try the old selector
        hp = _make_healed(page, db_path, test_id)
        page.goto(v2_url)

        # #login-btn does not exist in v2 — should heal
        hp.locator("#login-btn").click()

        # Healing event recorded
        store = FingerprintStore(db_path)
        events = store.get_healing_events(test_id=test_id)
        store.close()
        assert len(events) >= 1
        assert events[0].confidence > 0.4

    def test_heals_search_button(self, page, v1_url, v2_url, db_path):
        """#search-btn renamed to #find-btn, text 'Search' -> 'Find'."""
        test_id = "test_heals_search"
        self._fingerprint_on_v1(page, v1_url, db_path, test_id, "#search-btn")

        hp = _make_healed(page, db_path, test_id)
        page.goto(v2_url)
        hp.locator("#search-btn").click()

        store = FingerprintStore(db_path)
        events = store.get_healing_events(test_id=test_id)
        store.close()
        assert len(events) >= 1

    def test_heals_subscribe_button(self, page, v1_url, v2_url, db_path):
        """#subscribe-btn renamed to #newsletter-btn."""
        test_id = "test_heals_subscribe"
        self._fingerprint_on_v1(page, v1_url, db_path, test_id, "#subscribe-btn")

        hp = _make_healed(page, db_path, test_id)
        page.goto(v2_url)
        hp.locator("#subscribe-btn").click()

        store = FingerprintStore(db_path)
        events = store.get_healing_events(test_id=test_id)
        store.close()
        assert len(events) >= 1

    def test_no_healing_without_stored_fingerprint(self, page, v2_url, db_path):
        """No stored fingerprint — should raise original Playwright error."""
        from playwright.sync_api import Error as PlaywrightError

        hp = _make_healed(page, db_path, "test_no_fp")
        page.goto(v2_url)

        with pytest.raises(PlaywrightError):
            hp.locator("#login-btn").click()

    def test_stable_selector_does_not_heal(self, page, v1_url, v2_url, db_path):
        """data-testid survives the refactor — no heal event should be recorded."""
        test_id = "test_stable"
        hp = _make_healed(page, db_path, test_id)

        # v1: fingerprint saved using data-testid selector
        page.goto(v1_url)
        hp.locator('[data-testid="login-submit"]').click()

        # v2: same data-testid exists — locator succeeds without healing
        page.goto(v2_url)
        hp.locator('[data-testid="login-submit"]').click()

        store = FingerprintStore(db_path)
        events = store.get_healing_events(test_id=test_id)
        store.close()
        # No healing events — selector resolved normally both times
        assert len(events) == 0

    def test_preserved_product_id_does_not_heal(self, page, v1_url, v2_url, db_path):
        """#add-to-cart-1 exists in both v1 and v2 — should not need healing."""
        test_id = "test_product_stable"
        hp = _make_healed(page, db_path, test_id)

        page.goto(v1_url)
        hp.locator("#add-to-cart-1").click()

        page.goto(v2_url)
        hp.locator("#add-to-cart-1").click()

        store = FingerprintStore(db_path)
        events = store.get_healing_events(test_id=test_id)
        store.close()
        assert len(events) == 0


# ---------------------------------------------------------------------------
# Test: multiple interactions in one test (realistic usage)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestRealisticWorkflow:
    def test_full_login_workflow_heals(self, page, v1_url, v2_url, db_path):
        """Simulate a full login workflow fingerprinted on v1, run on v2."""
        test_id = "test_login_workflow"

        # Run on v1 — fingerprint everything
        hp = _make_healed(page, db_path, test_id)
        page.goto(v1_url)
        hp.locator("#email-input").fill("user@example.com")
        hp.locator("#password-input").fill("secret")
        hp.locator("#login-btn").click()
        hp.healer.store.close()

        # Run on v2 — all three locators broke, should all heal
        hp2 = _make_healed(page, db_path, test_id)
        page.goto(v2_url)
        hp2.locator("#email-input").fill("user@example.com")
        hp2.locator("#password-input").fill("secret")
        hp2.locator("#login-btn").click()

        store = FingerprintStore(db_path)
        events = store.get_healing_events(test_id=test_id)
        store.close()

        # All three locators should have healed
        healed_locators = {e.locator for e in events}
        assert "#login-btn" in healed_locators
        assert "#email-input" in healed_locators
        assert "#password-input" in healed_locators

    def test_healing_updates_stored_fingerprint(self, page, v1_url, v2_url, db_path):
        """After healing, the stored fingerprint should be updated to the new element."""
        test_id = "test_fp_update"

        hp = _make_healed(page, db_path, test_id)
        page.goto(v1_url)
        hp.locator("#login-btn").click()

        # Verify original fingerprint
        store = FingerprintStore(db_path)
        fp_before = store.load_fingerprint(test_id, "#login-btn")
        store.close()
        assert fp_before is not None

        # Run on v2 — heal occurs
        hp2 = _make_healed(page, db_path, test_id)
        page.goto(v2_url)
        hp2.locator("#login-btn").click()

        # Fingerprint should now reflect the healed element
        store = FingerprintStore(db_path)
        fp_after = store.load_fingerprint(test_id, "#login-btn")
        store.close()

        assert fp_after is not None
        # The updated fingerprint should differ from the original
        # (the healed element has different attributes/id in v2)
        assert fp_before.to_dict() != fp_after.to_dict()
