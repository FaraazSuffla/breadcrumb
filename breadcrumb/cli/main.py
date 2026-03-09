"""Breadcrumb CLI entry point.

Provides commands: report, doctor, generate, init, mcp.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import click

DEFAULT_DB = ".breadcrumb.db"


@click.group()
def cli() -> None:
    """Breadcrumb -- self-healing test framework CLI."""


# ---------------------------------------------------------------------------
# breadcrumb report
# ---------------------------------------------------------------------------


@cli.command()
@click.option("--db", default=DEFAULT_DB, help="Path to the breadcrumb database.", show_default=True)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["console", "html", "json"], case_sensitive=False),
    default="console",
    show_default=True,
    help="Output format.",
)
@click.option("--days", default=30, show_default=True, help="Include events from the last N days.")
@click.option("--output", "output_path", default=None, help="Output file path (for html/json formats).")
def report(db: str, fmt: str, days: int, output_path: str | None) -> None:
    """Generate a healing report from the breadcrumb database."""
    if not Path(db).exists():
        click.echo(f"Error: database file not found: {db}")
        raise SystemExit(1)

    from breadcrumb.core.storage import FingerprintStore

    store = FingerprintStore(db)
    try:
        if fmt == "console":
            from breadcrumb.report import ReportConsole

            click.echo(ReportConsole().render(store, days=days), nl=False)
        elif fmt == "html":
            from breadcrumb.report import ReportHTML

            out = output_path or "report.html"
            ReportHTML().export(store, out, days=days)
            click.echo(f"HTML report written to {out}")
        elif fmt == "json":
            from breadcrumb.report import ReportJSON

            out = output_path or "report.json"
            ReportJSON().export(store, out, days=days)
            click.echo(f"JSON report written to {out}")
    finally:
        store.close()


def _builtin_console_report(db: str, days: int) -> None:
    """Minimal console report using raw SQL queries."""
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        cutoff = time.time() - days * 86400

        # Check which tables exist
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}

        click.echo(f"Breadcrumb Report (last {days} days)")
        click.echo("=" * 40)

        if "fingerprints" in tables:
            count = conn.execute("SELECT COUNT(*) FROM fingerprints").fetchone()[0]
            click.echo(f"Stored fingerprints: {count}")

        if "healing_events" in tables:
            total = conn.execute("SELECT COUNT(*) FROM healing_events").fetchone()[0]
            recent = conn.execute(
                "SELECT COUNT(*) FROM healing_events WHERE timestamp >= ?",
                (cutoff,),
            ).fetchone()[0]
            click.echo(f"Healing events (total): {total}")
            click.echo(f"Healing events (last {days}d): {recent}")

            rows = conn.execute(
                "SELECT test_id, locator, confidence, timestamp "
                "FROM healing_events WHERE timestamp >= ? ORDER BY timestamp DESC",
                (cutoff,),
            ).fetchall()
            if rows:
                click.echo("")
                click.echo("Recent healing events:")
                for r in rows:
                    click.echo(f"  - {r['test_id']} | {r['locator']} | confidence={r['confidence']:.2f}")
        else:
            click.echo("No healing events recorded yet.")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# breadcrumb doctor
# ---------------------------------------------------------------------------


@cli.command()
@click.option("--db", default=DEFAULT_DB, help="Path to the breadcrumb database.", show_default=True)
def doctor(db: str) -> None:
    """Diagnose the health of the breadcrumb database."""
    click.echo("Breadcrumb Doctor")

    db_path = Path(db)
    if not db_path.exists():
        click.echo(f"DB: {db} (NOT FOUND)")
        click.echo("Status: No database found. Run tests with --breadcrumb to create one.")
        return

    click.echo(f"DB: {db} (exists)")

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}

        # Schema version
        schema_version = "unknown"
        if "schema_meta" in tables:
            row = conn.execute("SELECT value FROM schema_meta WHERE key = 'schema_version'").fetchone()
            if row is not None:
                schema_version = row[0]
        click.echo(f"Schema version: {schema_version}")

        # Fingerprints
        fp_count = 0
        stale_count = 0
        if "fingerprints" in tables:
            fp_count = conn.execute("SELECT COUNT(*) FROM fingerprints").fetchone()[0]
            stale_cutoff = time.time() - 30 * 86400
            stale_count = conn.execute(
                "SELECT COUNT(*) FROM fingerprints WHERE updated_at < ?",
                (stale_cutoff,),
            ).fetchone()[0]
        if stale_count > 0:
            click.echo(f"Fingerprints: {fp_count} ({stale_count} stale, older than 30 days)")
        else:
            click.echo(f"Fingerprints: {fp_count}")

        # Healing events
        he_count = 0
        if "healing_events" in tables:
            he_count = conn.execute("SELECT COUNT(*) FROM healing_events").fetchone()[0]
        click.echo(f"Healing events: {he_count}")

        # Test runs (table may not exist yet)
        if "test_runs" in tables:
            tr_count = conn.execute("SELECT COUNT(*) FROM test_runs").fetchone()[0]
            click.echo(f"Test runs: {tr_count}")

        # Quarantined tests (table may not exist yet)
        if "quarantined_tests" in tables:
            q_count = conn.execute("SELECT COUNT(*) FROM quarantined_tests").fetchone()[0]
            click.echo(f"Quarantined tests: {q_count}")
        else:
            click.echo("Quarantined tests: 0")

        click.echo("Status: OK")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# breadcrumb generate
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("url")
def generate(url: str) -> None:
    """Generate tests from a URL using AI (Phase 4)."""
    try:
        from breadcrumb.generate.classifier import ElementClassifier
        from breadcrumb.generate.codegen import TestCodeGenerator
        from breadcrumb.generate.crawler import PageCrawler

        page_name = url.rstrip("/").rsplit("/", 1)[-1] or "page"
        elements = PageCrawler().crawl(url)
        classified = [dict(el, role=ElementClassifier().classify(el)) for el in elements]
        gen = TestCodeGenerator()
        click.echo(gen.generate_page_object(page_name, classified))
        click.echo(gen.generate_test_file(page_name, classified, page_url=url))
    except ImportError:
        click.echo("Phase 4 - AI test generation: install playwright extra first")


# ---------------------------------------------------------------------------
# breadcrumb init
# ---------------------------------------------------------------------------

_CONFTEST_TEMPLATE = '''\
"""Conftest for {name} -- breadcrumb self-healing tests."""

import pytest


@pytest.fixture
def heal_page(page):
    """Wrap Playwright page with breadcrumb self-healing."""
    from breadcrumb import HealablePage

    return HealablePage(page, test_id="default")
'''

_SAMPLE_TEST_TEMPLATE = '''\
"""Sample test generated by breadcrumb init."""


def test_example(heal_page):
    """Example self-healing test."""
    heal_page.goto("https://example.com")
    heading = heal_page.locator("h1")
    assert heading is not None
'''


@cli.command()
@click.option("--name", default="myproject", show_default=True, help="Project name.")
@click.option("--dir", "directory", default=".", show_default=True, help="Output directory.")
def init(name: str, directory: str) -> None:
    """Scaffold a new breadcrumb test project."""
    base = Path(directory).resolve()

    # Create conftest.py
    conftest_path = base / "conftest.py"
    conftest_path.write_text(_CONFTEST_TEMPLATE.format(name=name), encoding="utf-8")
    click.echo(f"Created {conftest_path}")

    # Create tests directory and sample test
    tests_dir = base / "tests"
    tests_dir.mkdir(exist_ok=True)
    sample_path = tests_dir / "test_sample.py"
    sample_path.write_text(_SAMPLE_TEST_TEMPLATE, encoding="utf-8")
    click.echo(f"Created {sample_path}")

    click.echo("")
    click.echo(f"Project '{name}' initialized in {base}")
    click.echo("Next steps:")
    click.echo("  1. Install dependencies: pip install breadcrumb[playwright,cli]")
    click.echo("  2. Run tests: pytest --breadcrumb")


# ---------------------------------------------------------------------------
# breadcrumb mcp
# ---------------------------------------------------------------------------


@cli.command()
@click.option("--db", default=DEFAULT_DB, help="Default database path for tools.", show_default=True)
def mcp(db: str) -> None:
    """Start the MCP server (stdio transport) for AI assistant integration.

    Add to your Claude Desktop / Code config:

    \b
    {
      "mcpServers": {
        "breadcrumb": {
          "command": "breadcrumb",
          "args": ["mcp"]
        }
      }
    }
    """
    try:
        import asyncio

        from breadcrumb.mcp.server import main as mcp_main

        asyncio.run(mcp_main(db))
    except ImportError:
        click.echo("Error: MCP server requires the 'mcp' extra.")
        click.echo("  pip install breadcrumb[mcp]")
        raise SystemExit(1) from None
