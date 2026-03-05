"""Shared test fixtures and configuration."""

from __future__ import annotations

from pathlib import Path

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--integration",
        action="store_true",
        default=False,
        help="Run integration tests (requires Playwright + Chromium).",
    )


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    if not config.getoption("--integration"):
        skip = pytest.mark.skip(reason="Pass --integration to run")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip)


@pytest.fixture(scope="session")
def v1_url(tmp_path_factory: pytest.TempPathFactory) -> str:
    """File URL to the v1 demo page."""
    src = Path(__file__).parent / "demo_app" / "v1.html"
    return src.as_uri()


@pytest.fixture(scope="session")
def v2_url(tmp_path_factory: pytest.TempPathFactory) -> str:
    """File URL to the v2 demo page (simulates a DOM-breaking refactor)."""
    src = Path(__file__).parent / "demo_app" / "v2.html"
    return src.as_uri()
