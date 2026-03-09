"""Breadcrumb MCP server — exposes breadcrumb tools to AI assistants.

Seven tools are registered:

- ``breadcrumb_stats``            — fingerprint + heal-event counts
- ``breadcrumb_report``           — full JSON healing report (N days)
- ``breadcrumb_doctor``           — DB health check
- ``breadcrumb_healing_events``   — recent heal events, filterable by test_id
- ``breadcrumb_flaky_tests``      — per-test flakiness classification
- ``breadcrumb_generate_tests``   — generate POM + pytest from a URL
- ``breadcrumb_list_fingerprints``— enumerate stored fingerprints

All tool-handler functions are importable without the ``mcp`` package so they
can be tested independently.  The ``mcp`` library is only imported inside
``create_server()`` and ``main()``.
"""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Any

from breadcrumb.core.storage import FingerprintStore
from breadcrumb.flaky.analyzer import TestAnalyzer
from breadcrumb.flaky.quarantine import QuarantineManager
from breadcrumb.flaky.tracker import TestTracker, migrate_schema
from breadcrumb.generate.classifier import ElementClassifier
from breadcrumb.generate.codegen import TestCodeGenerator
from breadcrumb.generate.crawler import PageCrawler
from breadcrumb.report.json import ReportJSON

# ---------------------------------------------------------------------------
# Handler functions — pure business logic, no mcp dependency
# ---------------------------------------------------------------------------


def _stats_handler(db_path: str) -> dict[str, Any]:
    """Return fingerprint and healing-event counts from the database.

    Args:
        db_path: Path to the ``.breadcrumb.db`` file.

    Returns:
        Dict with keys ``fingerprints`` and ``healing_events`` (int counts).
    """
    store = FingerprintStore(db_path)
    try:
        result: dict[str, Any] = store.stats()
        return result
    finally:
        store.close()


def _report_handler(db_path: str, days: int = 30) -> dict[str, Any]:
    """Return a full JSON healing report.

    Args:
        db_path: Path to the ``.breadcrumb.db`` file.
        days: Report window in days.

    Returns:
        JSON-serialisable dict produced by :class:`~breadcrumb.report.ReportJSON`.
    """
    store = FingerprintStore(db_path)
    try:
        return ReportJSON().render(store, days=days)  # type: ignore[no-any-return]
    finally:
        store.close()


def _doctor_handler(db_path: str) -> dict[str, Any]:
    """Run a health check on the breadcrumb database.

    Args:
        db_path: Path to the ``.breadcrumb.db`` file.

    Returns:
        Dict with schema version, counts, stale fingerprint count, and
        ``status`` (``"OK"`` or ``"WARNING"``).
    """
    import os

    result: dict[str, Any] = {"db_path": db_path}

    if not os.path.exists(db_path):
        result["status"] = "NOT FOUND"
        result["message"] = "Database not found. Run tests with --breadcrumb to create one."
        return result

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}

        schema_version: str = "unknown"
        if "schema_meta" in tables:
            row = conn.execute("SELECT value FROM schema_meta WHERE key = 'schema_version'").fetchone()
            if row is not None:
                schema_version = row[0]
        result["schema_version"] = schema_version

        fp_count = 0
        stale_count = 0
        if "fingerprints" in tables:
            fp_count = conn.execute("SELECT COUNT(*) FROM fingerprints").fetchone()[0]
            stale_cutoff = time.time() - 30 * 86400
            stale_count = conn.execute(
                "SELECT COUNT(*) FROM fingerprints WHERE updated_at < ?",
                (stale_cutoff,),
            ).fetchone()[0]
        result["fingerprints"] = fp_count
        result["stale_fingerprints"] = stale_count

        he_count = 0
        if "healing_events" in tables:
            he_count = conn.execute("SELECT COUNT(*) FROM healing_events").fetchone()[0]
        result["healing_events"] = he_count

        if "test_runs" in tables:
            result["test_runs"] = conn.execute("SELECT COUNT(*) FROM test_runs").fetchone()[0]

        q_count = 0
        if "quarantine" in tables:
            q_count = conn.execute("SELECT COUNT(*) FROM quarantine").fetchone()[0]
        result["quarantined_tests"] = q_count

        result["status"] = "WARNING" if stale_count > 0 else "OK"
        return result
    finally:
        conn.close()


def _healing_events_handler(
    db_path: str,
    test_id: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Retrieve recent healing events.

    Args:
        db_path: Path to the ``.breadcrumb.db`` file.
        test_id: If provided, filter events to this test only.
        limit: Maximum number of events to return.

    Returns:
        List of dicts with ``test_id``, ``locator``, ``confidence``,
        and ``timestamp`` keys.
    """
    store = FingerprintStore(db_path)
    try:
        events = store.get_healing_events(test_id=test_id)
        return [
            {
                "test_id": ev.test_id,
                "locator": ev.locator,
                "confidence": ev.confidence,
                "timestamp": ev.timestamp,
            }
            for ev in events[:limit]
        ]
    finally:
        store.close()


def _flaky_tests_handler(db_path: str) -> dict[str, Any]:
    """Classify all tracked tests by flakiness.

    Args:
        db_path: Path to the ``.breadcrumb.db`` file.

    Returns:
        Dict with ``classifications`` (test_id → tier) and ``quarantined``
        (sorted list of quarantined test IDs).
    """
    store = FingerprintStore(db_path)
    try:
        migrate_schema(store)
        tracker = TestTracker(store)
        analyzer = TestAnalyzer(tracker)
        quarantine_mgr = QuarantineManager(store, analyzer)
        classifications = analyzer.get_all_classifications()
        quarantined = set(quarantine_mgr.get_all_quarantined())
        return {
            "classifications": classifications,
            "quarantined": sorted(quarantined),
        }
    finally:
        store.close()


def _generate_tests_handler(url: str) -> dict[str, str]:
    """Crawl *url* and generate a Page Object Model + pytest skeleton.

    Args:
        url: The page URL to crawl.

    Returns:
        Dict with ``page_object`` and ``test_file`` keys (Python source strings).
    """
    page_name = url.rstrip("/").rsplit("/", 1)[-1] or "page"
    elements = PageCrawler().crawl(url)
    classified = [dict(el, role=ElementClassifier().classify(el)) for el in elements]
    gen = TestCodeGenerator()
    return {
        "page_object": gen.generate_page_object(page_name, classified),
        "test_file": gen.generate_test_file(page_name, classified, page_url=url),
    }


def _list_fingerprints_handler(db_path: str) -> list[dict[str, Any]]:
    """List all stored element fingerprints.

    Args:
        db_path: Path to the ``.breadcrumb.db`` file.

    Returns:
        List of fingerprint summary dicts (tag, text snippet, locator, test_id).
    """
    store = FingerprintStore(db_path)
    try:
        fingerprints = store.get_all_fingerprints()
        return [
            {
                "test_id": fp.test_id,
                "locator": fp.locator,
                "tag": fp.tag,
                "text": fp.text[:100] if fp.text else "",
                "dom_path": list(fp.dom_path),
                "attributes": sorted(list(fp.attributes)),
            }
            for fp in fingerprints
        ]
    finally:
        store.close()


# ---------------------------------------------------------------------------
# MCP server factory
# ---------------------------------------------------------------------------

_TOOLS_SCHEMA: list[dict[str, Any]] = [
    {
        "name": "breadcrumb_stats",
        "description": "Return fingerprint and healing-event counts from the breadcrumb database.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "db_path": {
                    "type": "string",
                    "description": "Path to the .breadcrumb.db file.",
                    "default": ".breadcrumb.db",
                },
            },
        },
    },
    {
        "name": "breadcrumb_report",
        "description": "Return a full JSON healing report for the last N days.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "db_path": {
                    "type": "string",
                    "description": "Path to the .breadcrumb.db file.",
                    "default": ".breadcrumb.db",
                },
                "days": {
                    "type": "integer",
                    "description": "Number of days to include in the report.",
                    "default": 30,
                },
            },
        },
    },
    {
        "name": "breadcrumb_doctor",
        "description": (
            "Run a health check on the breadcrumb database: "
            "reports schema version, stale fingerprint count, and quarantine count."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "db_path": {
                    "type": "string",
                    "description": "Path to the .breadcrumb.db file.",
                    "default": ".breadcrumb.db",
                },
            },
        },
    },
    {
        "name": "breadcrumb_healing_events",
        "description": "Retrieve recent healing events, optionally filtered by test ID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "db_path": {
                    "type": "string",
                    "description": "Path to the .breadcrumb.db file.",
                    "default": ".breadcrumb.db",
                },
                "test_id": {
                    "type": "string",
                    "description": "Filter events to this test ID only (optional).",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of events to return.",
                    "default": 50,
                },
            },
        },
    },
    {
        "name": "breadcrumb_flaky_tests",
        "description": (
            "Classify all tracked tests by flakiness "
            "(Stable / Intermittent / Flaky / Chronic) and list quarantined tests."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "db_path": {
                    "type": "string",
                    "description": "Path to the .breadcrumb.db file.",
                    "default": ".breadcrumb.db",
                },
            },
        },
    },
    {
        "name": "breadcrumb_generate_tests",
        "description": "Crawl a URL and generate a Page Object Model + pytest test file.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL of the page to crawl.",
                },
            },
            "required": ["url"],
        },
    },
    {
        "name": "breadcrumb_list_fingerprints",
        "description": "List all stored element fingerprints in the breadcrumb database.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "db_path": {
                    "type": "string",
                    "description": "Path to the .breadcrumb.db file.",
                    "default": ".breadcrumb.db",
                },
            },
        },
    },
]


def create_server() -> Any:
    """Create and return the configured breadcrumb MCP server.

    Requires the ``mcp`` optional extra (``pip install breadcrumb[mcp]``).

    Returns:
        A configured :class:`mcp.server.Server` instance.
    """
    from mcp import types  # type: ignore[import-not-found]
    from mcp.server import Server  # type: ignore[import-not-found]

    app: Any = Server("breadcrumb")

    @app.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name=t["name"],
                description=t["description"],
                inputSchema=t["inputSchema"],
            )
            for t in _TOOLS_SCHEMA
        ]

    @app.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
        db_path: str = arguments.get("db_path", ".breadcrumb.db")

        try:
            result: Any
            if name == "breadcrumb_stats":
                result = _stats_handler(db_path)
            elif name == "breadcrumb_report":
                days = int(arguments.get("days", 30))
                result = _report_handler(db_path, days=days)
            elif name == "breadcrumb_doctor":
                result = _doctor_handler(db_path)
            elif name == "breadcrumb_healing_events":
                test_id: str | None = arguments.get("test_id")
                limit = int(arguments.get("limit", 50))
                result = _healing_events_handler(db_path, test_id=test_id, limit=limit)
            elif name == "breadcrumb_flaky_tests":
                result = _flaky_tests_handler(db_path)
            elif name == "breadcrumb_generate_tests":
                result = _generate_tests_handler(arguments["url"])
            elif name == "breadcrumb_list_fingerprints":
                result = _list_fingerprints_handler(db_path)
            else:
                result = {"error": f"Unknown tool: {name}"}
        except Exception as exc:
            result = {"error": str(exc)}

        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

    return app


async def main(db_path: str = ".breadcrumb.db") -> None:
    """Start the breadcrumb MCP server over stdio transport.

    Args:
        db_path: Default database path passed to tools that accept it.
            Individual tool calls can override this per-invocation.
    """
    from mcp.server.stdio import stdio_server  # type: ignore[import-not-found]

    app = create_server()
    async with stdio_server() as streams:
        read_stream, write_stream = streams
        await app.run(read_stream, write_stream, app.create_initialization_options())
