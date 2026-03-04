"""Tests for breadcrumb.plugins.pytest_plugin."""

from __future__ import annotations

import tempfile
from pathlib import Path

from breadcrumb.plugins.pytest_plugin import BreadcrumbState


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
