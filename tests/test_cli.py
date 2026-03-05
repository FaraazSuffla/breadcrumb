"""Tests for breadcrumb.cli.main."""

from __future__ import annotations

import pytest

from breadcrumb.cli.main import cli


class TestCli:
    def test_cli_raises_systemexit(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            cli()
        assert "not yet available" in str(exc_info.value)
