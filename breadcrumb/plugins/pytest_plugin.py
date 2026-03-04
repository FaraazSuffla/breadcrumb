"""Breadcrumb pytest plugin — self-healing locator support for Playwright tests.

This plugin is registered via the ``pytest11`` entry point in pyproject.toml.
It provides:

1. ``--breadcrumb`` CLI flag to enable self-healing across all tests.
2. ``heal_page`` fixture that wraps a Playwright ``page`` with self-healing.
3. Automatic test_id injection from the pytest node ID.
4. ``--breadcrumb-report`` flag to print a healing summary after the session.

Usage::

    # Explicit — use the heal_page fixture
    def test_login(heal_page):
        heal_page.locator("#login-btn").click()

    # Or via CLI flag (auto-wraps all 'page' fixtures)
    # pytest --breadcrumb
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Generator

import pytest

from breadcrumb.core.healer import Healer
from breadcrumb.core.storage import FingerprintStore
from breadcrumb.playwright.page_wrapper import HealablePage

logger = logging.getLogger("breadcrumb.plugin")


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register Breadcrumb CLI options."""
    group = parser.getgroup("breadcrumb", "Self-healing test locators")
    group.addoption(
        "--breadcrumb",
        action="store_true",
        default=False,
        help="Enable self-healing locators for all Playwright tests.",
    )
    group.addoption(
        "--breadcrumb-db",
        type=str,
        default=".breadcrumb.db",
        help="Path to the Breadcrumb SQLite database (default: .breadcrumb.db).",
    )
    group.addoption(
        "--breadcrumb-threshold",
        type=float,
        default=0.5,
        help="Minimum similarity score for healing (default: 0.5).",
    )
    group.addoption(
        "--breadcrumb-report",
        action="store_true",
        default=False,
        help="Print a healing summary after the test session.",
    )


class BreadcrumbState:
    """Shared state for the Breadcrumb plugin across a test session."""

    def __init__(self, db_path: str, threshold: float) -> None:
        self.store = FingerprintStore(Path(db_path))
        self.healer = Healer(store=self.store, threshold=threshold)
        self.healed_count = 0
        self.failed_heals = 0
        self.tests_with_healing: list[str] = []

    def close(self) -> None:
        """Clean up resources."""
        self.store.close()


_state: BreadcrumbState | None = None


def pytest_configure(config: pytest.Config) -> None:
    """Set up shared Breadcrumb state if the plugin is enabled."""
    global _state  # noqa: PLW0603
    if config.getoption("breadcrumb", default=False):
        db_path = config.getoption("breadcrumb_db", default=".breadcrumb.db")
        threshold = config.getoption("breadcrumb_threshold", default=0.5)
        _state = BreadcrumbState(db_path=db_path, threshold=threshold)
        logger.info(
            "Breadcrumb enabled: db=%s threshold=%.2f",
            db_path,
            threshold,
        )


def pytest_unconfigure(config: pytest.Config) -> None:
    """Tear down shared state."""
    global _state  # noqa: PLW0603
    if _state is not None:
        _state.close()
        _state = None


def pytest_terminal_summary(
    terminalreporter: Any,
    exitstatus: int,
    config: pytest.Config,
) -> None:
    """Print healing summary if --breadcrumb-report is enabled."""
    if not config.getoption("breadcrumb_report", default=False):
        return
    if _state is None:
        return

    terminalreporter.write_sep("=", "Breadcrumb Healing Report")

    stats = _state.store.stats()
    terminalreporter.write_line(
        f"  Fingerprints stored: {stats['fingerprints']}",
    )
    terminalreporter.write_line(
        f"  Healing events:      {stats['healing_events']}",
    )

    events = _state.store.get_healing_events()
    if events:
        terminalreporter.write_line("")
        terminalreporter.write_line("  Recent healing events:")
        for event in events[:10]:
            terminalreporter.write_line(
                f"    {event.test_id} | {event.locator} "
                f"| confidence={event.confidence:.4f}",
            )
    else:
        terminalreporter.write_line("  No healing events recorded.")


@pytest.fixture
def heal_page(request: pytest.FixtureRequest) -> Generator[HealablePage, None, None]:
    """Fixture that wraps a Playwright page with self-healing.

    Requires a ``page`` fixture to be available (from pytest-playwright
    or a custom fixture). Automatically sets the test_id from the
    pytest node ID.

    Yields:
        A HealablePage wrapping the Playwright page.
    """
    # Get the Playwright page from the existing 'page' fixture
    page = request.getfixturevalue("page")
    test_id = request.node.nodeid

    if _state is not None:
        healable = HealablePage(
            page=page,
            healer=_state.healer,
            test_id=test_id,
        )
    else:
        # Plugin not activated via CLI — create standalone healer
        db_path = Path(".breadcrumb.db")
        store = FingerprintStore(db_path)
        healer = Healer(store=store)
        healable = HealablePage(page=page, healer=healer, test_id=test_id)

    yield healable
