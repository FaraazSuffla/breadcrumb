"""Example: self-healing login test with Breadcrumb.

This file shows the two main usage patterns. Copy and adapt for your own app.

Run with:
    pytest examples/test_login.py --breadcrumb

Or run standalone (no pytest):
    python examples/test_login.py
"""

# ─── Option 1: pytest fixture (recommended) ────────────────────────────────
#
# The heal_page fixture is provided automatically when you run with --breadcrumb.
# test_id is set from the test node ID, so fingerprints stay stable across runs.


def test_login_with_fixture(heal_page):  # type: ignore[no-untyped-def]
    """Demonstrate self-healing using the pytest fixture.

    On the first run, breadcrumb fingerprints every element you interact with.
    On subsequent runs, if a locator breaks (e.g. #login-btn renamed to #auth-btn),
    breadcrumb finds the right element automatically and the test still passes.
    """
    heal_page.goto("https://example.com")

    # Fingerprinted on first run; healed automatically if the selector changes later.
    assert heal_page.locator("h1").is_visible()


# ─── Option 2: standalone script ───────────────────────────────────────────
#
# Use crumb() to wrap any Playwright page outside of pytest.
# Always pass an explicit test_id — it is the key used to look up fingerprints.


def run_standalone() -> None:
    """Demonstrate self-healing in a plain Python script (no pytest)."""
    from playwright.sync_api import sync_playwright

    from breadcrumb import crumb

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = crumb(
            browser.new_page(),
            test_id="example_login",  # stable key for fingerprint lookup
            db_path=".breadcrumb.db",  # where to store fingerprints
            threshold=0.5,  # minimum confidence to accept a healed element
        )

        page.goto("https://example.com")

        # Run 1: the h1 is fingerprinted and saved.
        # Run 2: if the selector breaks, breadcrumb heals automatically.
        assert page.locator("h1").is_visible()

        browser.close()


if __name__ == "__main__":
    run_standalone()
