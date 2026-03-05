"""Tests for breadcrumb.plugins.pytest_plugin."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

import breadcrumb.plugins.pytest_plugin as plugin_module
from breadcrumb.plugins.pytest_plugin import BreadcrumbState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(
    breadcrumb: bool = False,
    breadcrumb_db: str = ".breadcrumb.db",
    breadcrumb_threshold: float = 0.5,
    breadcrumb_report: bool = False,
) -> MagicMock:
    """Build a mock pytest.Config with Breadcrumb options."""
    config = MagicMock(spec=pytest.Config)

    def _getoption(name: str, default: Any = None) -> Any:
        return {
            "breadcrumb": breadcrumb,
            "breadcrumb_db": breadcrumb_db,
            "breadcrumb_threshold": breadcrumb_threshold,
            "breadcrumb_report": breadcrumb_report,
        }.get(name, default)

    config.getoption.side_effect = _getoption
    return config


# ---------------------------------------------------------------------------
# BreadcrumbState
# ---------------------------------------------------------------------------


class TestBreadcrumbState:
    def test_creates_store_and_healer(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = str(Path(td) / "test.db")
            state = BreadcrumbState(db_path=db_path, threshold=0.6)
            assert state.store is not None
            assert state.healer is not None
            assert state.healed_count == 0
            assert state.failed_heals == 0
            assert state.tests_with_healing == []
            state.close()

    def test_close_is_safe_to_call_twice(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = str(Path(td) / "test.db")
            state = BreadcrumbState(db_path=db_path, threshold=0.5)
            state.close()
            # Should not raise on double close
            state.close()

    def test_custom_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = str(Path(td) / "test.db")
            state = BreadcrumbState(db_path=db_path, threshold=0.8)
            assert state.healer.threshold == 0.8
            state.close()


# ---------------------------------------------------------------------------
# pytest_configure / pytest_unconfigure
# ---------------------------------------------------------------------------


class TestPytestConfigure:
    def setup_method(self) -> None:
        # Reset global state before each test
        plugin_module._state = None

    def teardown_method(self) -> None:
        if plugin_module._state is not None:
            plugin_module._state.close()
        plugin_module._state = None

    def test_creates_state_when_flag_enabled(self, tmp_path: Path) -> None:
        db = str(tmp_path / "bc.db")
        config = _make_config(breadcrumb=True, breadcrumb_db=db, breadcrumb_threshold=0.7)
        plugin_module.pytest_configure(config)
        assert plugin_module._state is not None
        assert plugin_module._state.healer.threshold == 0.7

    def test_does_not_create_state_without_flag(self) -> None:
        config = _make_config(breadcrumb=False)
        plugin_module.pytest_configure(config)
        assert plugin_module._state is None

    def test_unconfigure_clears_state(self, tmp_path: Path) -> None:
        db = str(tmp_path / "bc.db")
        config = _make_config(breadcrumb=True, breadcrumb_db=db)
        plugin_module.pytest_configure(config)
        assert plugin_module._state is not None
        plugin_module.pytest_unconfigure(config)
        assert plugin_module._state is None

    def test_unconfigure_is_safe_when_state_is_none(self) -> None:
        config = _make_config(breadcrumb=False)
        # Should not raise
        plugin_module.pytest_unconfigure(config)

    def test_configure_uses_default_db_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Redirect the default db to tmp_path so we don't pollute the project root
        monkeypatch.chdir(tmp_path)
        config = _make_config(breadcrumb=True)
        plugin_module.pytest_configure(config)
        assert plugin_module._state is not None


# ---------------------------------------------------------------------------
# pytest_terminal_summary
# ---------------------------------------------------------------------------


class TestTerminalSummary:
    def setup_method(self) -> None:
        plugin_module._state = None

    def teardown_method(self) -> None:
        if plugin_module._state is not None:
            plugin_module._state.close()
        plugin_module._state = None

    def _make_reporter(self) -> MagicMock:
        reporter = MagicMock()
        reporter.write_sep = MagicMock()
        reporter.write_line = MagicMock()
        return reporter

    def test_does_nothing_when_report_flag_off(self, tmp_path: Path) -> None:
        db = str(tmp_path / "bc.db")
        config = _make_config(breadcrumb=True, breadcrumb_db=db, breadcrumb_report=False)
        plugin_module.pytest_configure(config)
        reporter = self._make_reporter()

        plugin_module.pytest_terminal_summary(reporter, exitstatus=0, config=config)
        reporter.write_sep.assert_not_called()

    def test_does_nothing_when_state_is_none(self) -> None:
        config = _make_config(breadcrumb_report=True)
        reporter = self._make_reporter()

        plugin_module.pytest_terminal_summary(reporter, exitstatus=0, config=config)
        reporter.write_sep.assert_not_called()

    def test_prints_summary_with_no_events(self, tmp_path: Path) -> None:
        db = str(tmp_path / "bc.db")
        config = _make_config(breadcrumb=True, breadcrumb_db=db, breadcrumb_report=True)
        plugin_module.pytest_configure(config)
        reporter = self._make_reporter()

        plugin_module.pytest_terminal_summary(reporter, exitstatus=0, config=config)

        reporter.write_sep.assert_called_once()
        # Should mention fingerprints and healing events
        lines = [call.args[0] for call in reporter.write_line.call_args_list]
        assert any("Fingerprints" in line for line in lines)
        assert any("Healing events" in line for line in lines)
        assert any("No healing events" in line for line in lines)

    def test_prints_recent_events(self, tmp_path: Path) -> None:
        db = str(tmp_path / "bc.db")
        config = _make_config(breadcrumb=True, breadcrumb_db=db, breadcrumb_report=True)
        plugin_module.pytest_configure(config)
        assert plugin_module._state is not None

        # Insert a real healing event
        import time

        from breadcrumb.core.fingerprint import ElementFingerprint
        from breadcrumb.core.storage import HealingEvent

        fp = ElementFingerprint(
            tag="button",
            text="click",
            attributes=frozenset(),
            dom_path=(),
            siblings=(),
            locator="#btn",
            test_id="test_example",
        )
        plugin_module._state.store.save_fingerprint(fp)
        plugin_module._state.store.record_healing(
            HealingEvent(
                test_id="test_example",
                locator="#btn",
                confidence=0.92,
                original_fingerprint=fp.to_dict(),
                healed_fingerprint=fp.to_dict(),
                timestamp=time.time(),
            )
        )

        reporter = self._make_reporter()
        plugin_module.pytest_terminal_summary(reporter, exitstatus=0, config=config)

        lines = [call.args[0] for call in reporter.write_line.call_args_list]
        assert any("test_example" in line for line in lines)
        assert any("0.9200" in line for line in lines)


# ---------------------------------------------------------------------------
# heal_page fixture
# ---------------------------------------------------------------------------


def _call_heal_page(request: MagicMock) -> Any:
    """Call the heal_page fixture function directly, bypassing pytest's fixture mechanism."""
    import inspect

    raw_fn = inspect.unwrap(plugin_module.heal_page)
    gen = raw_fn(request)
    return next(gen)


class TestHealPageFixture:
    def setup_method(self) -> None:
        plugin_module._state = None

    def teardown_method(self) -> None:
        if plugin_module._state is not None:
            plugin_module._state.close()
        plugin_module._state = None

    def test_heal_page_uses_plugin_state(self, tmp_path: Path) -> None:
        db = str(tmp_path / "bc.db")
        state = BreadcrumbState(db_path=db, threshold=0.75)
        mock_page = MagicMock()

        request = MagicMock(spec=pytest.FixtureRequest)
        request.getfixturevalue.return_value = mock_page
        request.node.nodeid = "tests/test_x.py::test_y"

        plugin_module._state = state
        healable = _call_heal_page(request)

        from breadcrumb.playwright.page_wrapper import HealablePage

        assert isinstance(healable, HealablePage)
        assert healable.healer is state.healer
        assert healable.test_id == "tests/test_x.py::test_y"
        state.close()

    def test_heal_page_creates_standalone_healer_without_state(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Redirect default db to tmp_path so SQLite cleanup is handled by tmp_path
        monkeypatch.chdir(tmp_path)
        mock_page = MagicMock()

        request = MagicMock(spec=pytest.FixtureRequest)
        request.getfixturevalue.return_value = mock_page
        request.node.nodeid = "tests/test_x.py::test_z"

        plugin_module._state = None
        healable = _call_heal_page(request)

        from breadcrumb.playwright.page_wrapper import HealablePage

        assert isinstance(healable, HealablePage)
        assert healable.test_id == "tests/test_x.py::test_z"

    def test_heal_page_injects_node_id_as_test_id(self, tmp_path: Path) -> None:
        db = str(tmp_path / "bc.db")
        state = BreadcrumbState(db_path=db, threshold=0.5)
        mock_page = MagicMock()

        request = MagicMock(spec=pytest.FixtureRequest)
        request.getfixturevalue.return_value = mock_page
        request.node.nodeid = "tests/integration/test_login.py::test_login_flow"

        plugin_module._state = state
        healable = _call_heal_page(request)

        assert healable.test_id == "tests/integration/test_login.py::test_login_flow"
        state.close()


# ---------------------------------------------------------------------------
# Coverage gap: pytest_addoption registers the expected CLI flags
# ---------------------------------------------------------------------------


class TestPytestAddOption:
    def test_registers_breadcrumb_options(self) -> None:
        group = MagicMock()
        parser = MagicMock()
        parser.getgroup.return_value = group

        plugin_module.pytest_addoption(parser)

        parser.getgroup.assert_called_once_with("breadcrumb", "Self-healing test locators")
        # Verify all four options were registered
        option_names = [call.args[0] for call in group.addoption.call_args_list]
        assert "--breadcrumb" in option_names
        assert "--breadcrumb-db" in option_names
        assert "--breadcrumb-threshold" in option_names
        assert "--breadcrumb-report" in option_names
