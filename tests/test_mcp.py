"""Unit tests for breadcrumb MCP server.

All tests mock FingerprintStore so no real SQLite database is needed.
The ``mcp`` library itself is also mocked so this test file runs without
``pip install breadcrumb[mcp]``.
"""

from __future__ import annotations

import asyncio
import json
import sys
from types import ModuleType
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Inject mcp stubs into sys.modules BEFORE importing breadcrumb.mcp.server
# ---------------------------------------------------------------------------


def _make_mcp_stubs() -> None:
    """Register lightweight mcp stubs so imports inside server.py succeed."""
    if "mcp" in sys.modules:
        return

    mcp_stub = ModuleType("mcp")
    mcp_server_stub = ModuleType("mcp.server")
    mcp_stdio_stub = ModuleType("mcp.server.stdio")
    mcp_types_stub = ModuleType("mcp.types")

    # Server stub
    class _Server:
        def __init__(self, name: str) -> None:
            self.name = name
            self._list_tools_handler: Any = None
            self._call_tool_handler: Any = None

        def list_tools(self) -> Any:
            def decorator(fn: Any) -> Any:
                self._list_tools_handler = fn
                return fn

            return decorator

        def call_tool(self) -> Any:
            def decorator(fn: Any) -> Any:
                self._call_tool_handler = fn
                return fn

            return decorator

        def create_initialization_options(self) -> Any:
            return {}

        async def run(self, read: Any, write: Any, opts: Any) -> None:
            pass

    # TextContent stub
    class _TextContent:
        def __init__(self, type: str, text: str) -> None:  # noqa: A002
            self.type = type
            self.text = text

    # Tool stub
    class _Tool:
        def __init__(self, name: str, description: str, inputSchema: Any) -> None:  # noqa: N803
            self.name = name
            self.description = description
            self.inputSchema = inputSchema

    mcp_server_stub.Server = _Server  # type: ignore[attr-defined]
    mcp_types_stub.TextContent = _TextContent  # type: ignore[attr-defined]
    mcp_types_stub.Tool = _Tool  # type: ignore[attr-defined]

    # stdio_server stub: async context manager yielding (AsyncMock, AsyncMock)
    from contextlib import asynccontextmanager

    @asynccontextmanager  # type: ignore[arg-type]
    async def _stdio_server() -> Any:  # type: ignore[misc]
        yield (AsyncMock(), AsyncMock())

    mcp_stdio_stub.stdio_server = _stdio_server  # type: ignore[attr-defined]

    mcp_stub.types = mcp_types_stub  # type: ignore[attr-defined]

    sys.modules["mcp"] = mcp_stub
    sys.modules["mcp.server"] = mcp_server_stub
    sys.modules["mcp.server.stdio"] = mcp_stdio_stub
    sys.modules["mcp.types"] = mcp_types_stub


_make_mcp_stubs()

# Now safe to import from breadcrumb.mcp.server
from breadcrumb.mcp.server import (  # noqa: E402
    _TOOLS_SCHEMA,
    _doctor_handler,
    _flaky_tests_handler,
    _generate_tests_handler,
    _healing_events_handler,
    _list_fingerprints_handler,
    _report_handler,
    _stats_handler,
    create_server,
    main,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_store() -> MagicMock:
    """Return a mock FingerprintStore."""
    store = MagicMock()
    store.stats.return_value = {"fingerprints": 5, "healing_events": 3}
    store.get_healing_events.return_value = []
    store.get_all_fingerprints.return_value = []
    return store


@pytest.fixture()
def mock_fingerprint() -> MagicMock:
    """Return a mock ElementFingerprint."""
    fp = MagicMock()
    fp.test_id = "test_login"
    fp.locator = "#login-btn"
    fp.tag = "button"
    fp.text = "Log In"
    fp.dom_path = ("html", "body", "div", "button")
    fp.attributes = frozenset([("type", "submit"), ("class", "btn")])
    return fp


@pytest.fixture()
def mock_healing_event() -> MagicMock:
    """Return a mock HealingEvent."""
    ev = MagicMock()
    ev.test_id = "test_login"
    ev.locator = "#login-btn"
    ev.confidence = 0.87
    ev.timestamp = 1_000_000.0
    return ev


# ---------------------------------------------------------------------------
# _stats_handler
# ---------------------------------------------------------------------------


class TestStatsHandler:
    def test_returns_counts(self, mock_store: MagicMock) -> None:
        import breadcrumb.mcp.server as srv

        with patch.object(srv, "FingerprintStore", return_value=mock_store):
            result = _stats_handler(".breadcrumb.db")

        assert result == {"fingerprints": 5, "healing_events": 3}

    def test_closes_store(self, mock_store: MagicMock) -> None:
        import breadcrumb.mcp.server as srv

        with patch.object(srv, "FingerprintStore", return_value=mock_store):
            _stats_handler(".breadcrumb.db")

        mock_store.close.assert_called_once()

    def test_closes_on_exception(self, mock_store: MagicMock) -> None:
        import breadcrumb.mcp.server as srv

        mock_store.stats.side_effect = RuntimeError("db error")
        with patch.object(srv, "FingerprintStore", return_value=mock_store), pytest.raises(RuntimeError):
            _stats_handler(".breadcrumb.db")

        mock_store.close.assert_called_once()


# ---------------------------------------------------------------------------
# _report_handler
# ---------------------------------------------------------------------------


class TestReportHandler:
    def test_returns_report(self, mock_store: MagicMock) -> None:
        import breadcrumb.mcp.server as srv

        report_data = {"summary": {"total": 10}}
        mock_report = MagicMock()
        mock_report.render.return_value = report_data

        with (
            patch.object(srv, "FingerprintStore", return_value=mock_store),
            patch.object(srv, "ReportJSON", return_value=mock_report),
        ):
            result = _report_handler(".breadcrumb.db", days=7)

        assert result == report_data
        mock_report.render.assert_called_once_with(mock_store, days=7)

    def test_default_days(self, mock_store: MagicMock) -> None:
        import breadcrumb.mcp.server as srv

        mock_report = MagicMock()
        mock_report.render.return_value = {}

        with (
            patch.object(srv, "FingerprintStore", return_value=mock_store),
            patch.object(srv, "ReportJSON", return_value=mock_report),
        ):
            _report_handler(".breadcrumb.db")

        mock_report.render.assert_called_once_with(mock_store, days=30)

    def test_closes_store(self, mock_store: MagicMock) -> None:
        import breadcrumb.mcp.server as srv

        mock_report = MagicMock()
        mock_report.render.return_value = {}

        with (
            patch.object(srv, "FingerprintStore", return_value=mock_store),
            patch.object(srv, "ReportJSON", return_value=mock_report),
        ):
            _report_handler(".breadcrumb.db")

        mock_store.close.assert_called_once()


# ---------------------------------------------------------------------------
# _doctor_handler
# ---------------------------------------------------------------------------


class TestDoctorHandler:
    def test_db_not_found(self, tmp_path: Any) -> None:
        result = _doctor_handler(str(tmp_path / "missing.db"))
        assert result["status"] == "NOT FOUND"
        assert "message" in result

    def test_healthy_db(self, tmp_path: Any) -> None:
        import sqlite3

        db = tmp_path / "test.db"
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute("INSERT INTO schema_meta VALUES ('schema_version', '1')")
        conn.execute(
            "CREATE TABLE fingerprints "
            "(test_id TEXT, locator TEXT, fingerprint_json TEXT, updated_at REAL, PRIMARY KEY (test_id, locator))"
        )
        conn.execute(
            "CREATE TABLE healing_events "
            "(id INTEGER PRIMARY KEY, test_id TEXT, locator TEXT, confidence REAL, "
            "original_json TEXT, healed_json TEXT, timestamp REAL)"
        )
        conn.commit()
        conn.close()

        result = _doctor_handler(str(db))
        assert result["status"] == "OK"
        assert result["schema_version"] == "1"
        assert result["fingerprints"] == 0
        assert result["stale_fingerprints"] == 0
        assert result["healing_events"] == 0
        assert result["quarantined_tests"] == 0

    def test_stale_fingerprints_warns(self, tmp_path: Any) -> None:
        import sqlite3
        import time

        db = tmp_path / "test.db"
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute("INSERT INTO schema_meta VALUES ('schema_version', '1')")
        conn.execute(
            "CREATE TABLE fingerprints "
            "(test_id TEXT, locator TEXT, fingerprint_json TEXT, updated_at REAL, PRIMARY KEY (test_id, locator))"
        )
        conn.execute(
            "CREATE TABLE healing_events "
            "(id INTEGER PRIMARY KEY, test_id TEXT, locator TEXT, confidence REAL, "
            "original_json TEXT, healed_json TEXT, timestamp REAL)"
        )
        old_ts = time.time() - 40 * 86400
        conn.execute("INSERT INTO fingerprints VALUES ('t1', '#btn', '{}', ?)", (old_ts,))
        conn.commit()
        conn.close()

        result = _doctor_handler(str(db))
        assert result["status"] == "WARNING"
        assert result["stale_fingerprints"] == 1

    def test_missing_tables_default_counts(self, tmp_path: Any) -> None:
        import sqlite3

        db = tmp_path / "empty.db"
        conn = sqlite3.connect(str(db))
        conn.commit()
        conn.close()

        result = _doctor_handler(str(db))
        assert result["fingerprints"] == 0
        assert result["healing_events"] == 0
        assert result["quarantined_tests"] == 0
        assert result["schema_version"] == "unknown"


# ---------------------------------------------------------------------------
# _healing_events_handler
# ---------------------------------------------------------------------------


class TestHealingEventsHandler:
    def test_returns_events(self, mock_store: MagicMock, mock_healing_event: MagicMock) -> None:
        import breadcrumb.mcp.server as srv

        mock_store.get_healing_events.return_value = [mock_healing_event]

        with patch.object(srv, "FingerprintStore", return_value=mock_store):
            result = _healing_events_handler(".breadcrumb.db")

        assert len(result) == 1
        assert result[0]["test_id"] == "test_login"
        assert result[0]["locator"] == "#login-btn"
        assert result[0]["confidence"] == 0.87

    def test_filters_by_test_id(self, mock_store: MagicMock) -> None:
        import breadcrumb.mcp.server as srv

        with patch.object(srv, "FingerprintStore", return_value=mock_store):
            _healing_events_handler(".breadcrumb.db", test_id="my_test")

        mock_store.get_healing_events.assert_called_once_with(test_id="my_test")

    def test_limit_applied(self, mock_store: MagicMock) -> None:
        import breadcrumb.mcp.server as srv

        events = [MagicMock(test_id=f"t{i}", locator=f"#btn{i}", confidence=0.9, timestamp=float(i)) for i in range(10)]
        mock_store.get_healing_events.return_value = events

        with patch.object(srv, "FingerprintStore", return_value=mock_store):
            result = _healing_events_handler(".breadcrumb.db", limit=3)

        assert len(result) == 3

    def test_closes_store(self, mock_store: MagicMock) -> None:
        import breadcrumb.mcp.server as srv

        with patch.object(srv, "FingerprintStore", return_value=mock_store):
            _healing_events_handler(".breadcrumb.db")

        mock_store.close.assert_called_once()


# ---------------------------------------------------------------------------
# _flaky_tests_handler
# ---------------------------------------------------------------------------


class TestFlakyTestsHandler:
    def test_returns_classifications(self, mock_store: MagicMock) -> None:
        import breadcrumb.mcp.server as srv

        mock_analyzer = MagicMock()
        mock_analyzer.get_all_classifications.return_value = {"test_login": "Flaky", "test_home": "Stable"}
        mock_quarantine = MagicMock()
        mock_quarantine.get_all_quarantined.return_value = ["test_login"]

        with (
            patch.object(srv, "FingerprintStore", return_value=mock_store),
            patch.object(srv, "migrate_schema"),
            patch.object(srv, "TestAnalyzer", return_value=mock_analyzer),
            patch.object(srv, "QuarantineManager", return_value=mock_quarantine),
        ):
            result = _flaky_tests_handler(".breadcrumb.db")

        assert result["classifications"] == {"test_login": "Flaky", "test_home": "Stable"}
        assert result["quarantined"] == ["test_login"]

    def test_closes_store(self, mock_store: MagicMock) -> None:
        import breadcrumb.mcp.server as srv

        mock_analyzer = MagicMock()
        mock_analyzer.get_all_classifications.return_value = {}
        mock_quarantine = MagicMock()
        mock_quarantine.get_all_quarantined.return_value = []

        with (
            patch.object(srv, "FingerprintStore", return_value=mock_store),
            patch.object(srv, "migrate_schema"),
            patch.object(srv, "TestAnalyzer", return_value=mock_analyzer),
            patch.object(srv, "QuarantineManager", return_value=mock_quarantine),
        ):
            _flaky_tests_handler(".breadcrumb.db")

        mock_store.close.assert_called_once()


# ---------------------------------------------------------------------------
# _generate_tests_handler
# ---------------------------------------------------------------------------


class TestGenerateTestsHandler:
    def test_returns_pom_and_test(self) -> None:
        import breadcrumb.mcp.server as srv

        mock_crawler = MagicMock()
        mock_crawler.crawl.return_value = [{"tag": "button", "text": "Submit"}]
        mock_classifier = MagicMock()
        mock_classifier.classify.return_value = "action"
        mock_gen = MagicMock()
        mock_gen.generate_page_object.return_value = "# POM"
        mock_gen.generate_test_file.return_value = "# Tests"

        with (
            patch.object(srv, "PageCrawler", return_value=mock_crawler),
            patch.object(srv, "ElementClassifier", return_value=mock_classifier),
            patch.object(srv, "TestCodeGenerator", return_value=mock_gen),
        ):
            result = _generate_tests_handler("https://example.com/login")

        assert result["page_object"] == "# POM"
        assert result["test_file"] == "# Tests"

    def test_page_name_from_url(self) -> None:
        import breadcrumb.mcp.server as srv

        mock_crawler = MagicMock()
        mock_crawler.crawl.return_value = []
        mock_classifier = MagicMock()
        mock_classifier.classify.return_value = "unknown"
        mock_gen = MagicMock()
        mock_gen.generate_page_object.return_value = ""
        mock_gen.generate_test_file.return_value = ""

        with (
            patch.object(srv, "PageCrawler", return_value=mock_crawler),
            patch.object(srv, "ElementClassifier", return_value=mock_classifier),
            patch.object(srv, "TestCodeGenerator", return_value=mock_gen),
        ):
            _generate_tests_handler("https://example.com/checkout")

        call_args = mock_gen.generate_page_object.call_args[0]
        assert call_args[0] == "checkout"

    def test_root_url_defaults_to_page(self) -> None:
        """A URL with only a trailing slash after stripping yields the host, not 'page'."""
        import breadcrumb.mcp.server as srv

        mock_crawler = MagicMock()
        mock_crawler.crawl.return_value = []
        mock_classifier = MagicMock()
        mock_classifier.classify.return_value = "unknown"
        mock_gen = MagicMock()
        mock_gen.generate_page_object.return_value = ""
        mock_gen.generate_test_file.return_value = ""

        with (
            patch.object(srv, "PageCrawler", return_value=mock_crawler),
            patch.object(srv, "ElementClassifier", return_value=mock_classifier),
            patch.object(srv, "TestCodeGenerator", return_value=mock_gen),
        ):
            _generate_tests_handler("https://example.com/")

        # "https://example.com/".rstrip("/") → "https://example.com"
        # rsplit("/", 1)[-1] → "example.com" (non-empty, so used as-is)
        call_args = mock_gen.generate_page_object.call_args[0]
        assert call_args[0] == "example.com"


# ---------------------------------------------------------------------------
# _list_fingerprints_handler
# ---------------------------------------------------------------------------


class TestListFingerprintsHandler:
    def test_returns_fingerprint_summaries(self, mock_store: MagicMock, mock_fingerprint: MagicMock) -> None:
        import breadcrumb.mcp.server as srv

        mock_store.get_all_fingerprints.return_value = [mock_fingerprint]

        with patch.object(srv, "FingerprintStore", return_value=mock_store):
            result = _list_fingerprints_handler(".breadcrumb.db")

        assert len(result) == 1
        assert result[0]["test_id"] == "test_login"
        assert result[0]["locator"] == "#login-btn"
        assert result[0]["tag"] == "button"
        assert result[0]["text"] == "Log In"

    def test_text_truncated_at_100(self, mock_store: MagicMock) -> None:
        import breadcrumb.mcp.server as srv

        fp = MagicMock()
        fp.test_id = "t1"
        fp.locator = "#x"
        fp.tag = "p"
        fp.text = "x" * 200
        fp.dom_path = ()
        fp.attributes = frozenset()
        mock_store.get_all_fingerprints.return_value = [fp]

        with patch.object(srv, "FingerprintStore", return_value=mock_store):
            result = _list_fingerprints_handler(".breadcrumb.db")

        assert len(result[0]["text"]) == 100

    def test_empty_text(self, mock_store: MagicMock) -> None:
        import breadcrumb.mcp.server as srv

        fp = MagicMock()
        fp.test_id = "t1"
        fp.locator = "#x"
        fp.tag = "div"
        fp.text = ""
        fp.dom_path = ()
        fp.attributes = frozenset()
        mock_store.get_all_fingerprints.return_value = [fp]

        with patch.object(srv, "FingerprintStore", return_value=mock_store):
            result = _list_fingerprints_handler(".breadcrumb.db")

        assert result[0]["text"] == ""

    def test_closes_store(self, mock_store: MagicMock) -> None:
        import breadcrumb.mcp.server as srv

        with patch.object(srv, "FingerprintStore", return_value=mock_store):
            _list_fingerprints_handler(".breadcrumb.db")

        mock_store.close.assert_called_once()


# ---------------------------------------------------------------------------
# create_server / tool registration
# ---------------------------------------------------------------------------


class TestCreateServer:
    def test_returns_server(self) -> None:
        server = create_server()
        assert server is not None
        assert server.name == "breadcrumb"

    def test_seven_tools_registered(self) -> None:
        assert len(_TOOLS_SCHEMA) == 7
        names = [t["name"] for t in _TOOLS_SCHEMA]
        assert "breadcrumb_stats" in names
        assert "breadcrumb_report" in names
        assert "breadcrumb_doctor" in names
        assert "breadcrumb_healing_events" in names
        assert "breadcrumb_flaky_tests" in names
        assert "breadcrumb_generate_tests" in names
        assert "breadcrumb_list_fingerprints" in names

    def test_list_tools_handler_registered(self) -> None:
        server = create_server()
        assert server._list_tools_handler is not None

    def test_call_tool_handler_registered(self) -> None:
        server = create_server()
        assert server._call_tool_handler is not None

    def test_list_tools_returns_tool_objects(self) -> None:
        server = create_server()
        tools = asyncio.run(server._list_tools_handler())
        assert len(tools) == 7
        assert all(hasattr(t, "name") for t in tools)

    def test_call_tool_stats(self, mock_store: MagicMock) -> None:
        import breadcrumb.mcp.server as srv

        server = create_server()
        with patch.object(srv, "FingerprintStore", return_value=mock_store):
            result = asyncio.run(server._call_tool_handler("breadcrumb_stats", {"db_path": ".breadcrumb.db"}))

        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data == {"fingerprints": 5, "healing_events": 3}

    def test_call_tool_unknown(self) -> None:
        server = create_server()
        result = asyncio.run(server._call_tool_handler("nonexistent_tool", {}))
        data = json.loads(result[0].text)
        assert "error" in data
        assert "Unknown tool" in data["error"]

    def test_call_tool_exception_returns_error(self, mock_store: MagicMock) -> None:
        import breadcrumb.mcp.server as srv

        mock_store.stats.side_effect = RuntimeError("boom")
        server = create_server()
        with patch.object(srv, "FingerprintStore", return_value=mock_store):
            result = asyncio.run(server._call_tool_handler("breadcrumb_stats", {}))
        data = json.loads(result[0].text)
        assert "error" in data
        assert "boom" in data["error"]

    def test_call_tool_healing_events_with_test_id(self, mock_store: MagicMock) -> None:
        import breadcrumb.mcp.server as srv

        server = create_server()
        with patch.object(srv, "FingerprintStore", return_value=mock_store):
            result = asyncio.run(
                server._call_tool_handler(
                    "breadcrumb_healing_events",
                    {"db_path": ".breadcrumb.db", "test_id": "t1", "limit": 10},
                )
            )

        mock_store.get_healing_events.assert_called_once_with(test_id="t1")
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_call_tool_report(self, mock_store: MagicMock) -> None:
        import breadcrumb.mcp.server as srv

        mock_report = MagicMock()
        mock_report.render.return_value = {"summary": {}}
        server = create_server()
        with (
            patch.object(srv, "FingerprintStore", return_value=mock_store),
            patch.object(srv, "ReportJSON", return_value=mock_report),
        ):
            result = asyncio.run(server._call_tool_handler("breadcrumb_report", {"days": 7}))

        mock_report.render.assert_called_once_with(mock_store, days=7)
        data = json.loads(result[0].text)
        assert "summary" in data

    def test_call_tool_doctor(self, tmp_path: Any) -> None:
        server = create_server()
        result = asyncio.run(server._call_tool_handler("breadcrumb_doctor", {"db_path": str(tmp_path / "x.db")}))
        data = json.loads(result[0].text)
        assert data["status"] == "NOT FOUND"

    def test_call_tool_flaky(self, mock_store: MagicMock) -> None:
        import breadcrumb.mcp.server as srv

        mock_analyzer = MagicMock()
        mock_analyzer.get_all_classifications.return_value = {}
        mock_quarantine = MagicMock()
        mock_quarantine.get_all_quarantined.return_value = []
        server = create_server()
        with (
            patch.object(srv, "FingerprintStore", return_value=mock_store),
            patch.object(srv, "migrate_schema"),
            patch.object(srv, "TestAnalyzer", return_value=mock_analyzer),
            patch.object(srv, "QuarantineManager", return_value=mock_quarantine),
        ):
            result = asyncio.run(server._call_tool_handler("breadcrumb_flaky_tests", {}))

        data = json.loads(result[0].text)
        assert "classifications" in data

    def test_call_tool_list_fingerprints(self, mock_store: MagicMock) -> None:
        import breadcrumb.mcp.server as srv

        server = create_server()
        with patch.object(srv, "FingerprintStore", return_value=mock_store):
            result = asyncio.run(server._call_tool_handler("breadcrumb_list_fingerprints", {}))

        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_call_tool_generate(self) -> None:
        import breadcrumb.mcp.server as srv

        mock_crawler = MagicMock()
        mock_crawler.crawl.return_value = []
        mock_classifier = MagicMock()
        mock_classifier.classify.return_value = "unknown"
        mock_gen = MagicMock()
        mock_gen.generate_page_object.return_value = "# POM"
        mock_gen.generate_test_file.return_value = "# Tests"
        server = create_server()
        with (
            patch.object(srv, "PageCrawler", return_value=mock_crawler),
            patch.object(srv, "ElementClassifier", return_value=mock_classifier),
            patch.object(srv, "TestCodeGenerator", return_value=mock_gen),
        ):
            result = asyncio.run(
                server._call_tool_handler(
                    "breadcrumb_generate_tests",
                    {"url": "https://example.com"},
                )
            )

        data = json.loads(result[0].text)
        assert data["page_object"] == "# POM"


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


class TestMain:
    def test_main_starts_server(self) -> None:
        """main() should call stdio_server and app.run without error."""
        asyncio.run(asyncio.wait_for(main(".breadcrumb.db"), timeout=2.0))
