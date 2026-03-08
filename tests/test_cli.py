"""Tests for breadcrumb.cli.main."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

import pytest
from click.testing import CliRunner

from breadcrumb.cli.main import cli


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    """Create a temporary breadcrumb DB with schema and sample data."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """\
        CREATE TABLE schema_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        INSERT INTO schema_meta (key, value) VALUES ('schema_version', '1');

        CREATE TABLE fingerprints (
            test_id TEXT NOT NULL,
            locator TEXT NOT NULL,
            fingerprint_json TEXT NOT NULL,
            updated_at REAL NOT NULL,
            PRIMARY KEY (test_id, locator)
        );

        CREATE TABLE healing_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_id TEXT NOT NULL,
            locator TEXT NOT NULL,
            confidence REAL NOT NULL,
            original_json TEXT NOT NULL,
            healed_json TEXT NOT NULL,
            timestamp REAL NOT NULL
        );
        """
    )
    # Insert a fingerprint
    conn.execute(
        "INSERT INTO fingerprints (test_id, locator, fingerprint_json, updated_at) VALUES (?, ?, ?, ?)",
        ("test_login", "#login-btn", json.dumps({"tag": "button"}), time.time()),
    )
    # Insert a healing event
    conn.execute(
        "INSERT INTO healing_events (test_id, locator, confidence, original_json, healed_json, timestamp) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            "test_login",
            "#login-btn",
            0.85,
            json.dumps({"tag": "button", "id": "login-btn"}),
            json.dumps({"tag": "button", "id": "auth-button"}),
            time.time(),
        ),
    )
    conn.commit()
    conn.close()
    return db_path


class TestReportCommand:
    def test_report_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["report", "--help"])
        assert result.exit_code == 0
        assert "--db" in result.output
        assert "--format" in result.output

    def test_report_missing_db(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["report", "--db", "nonexistent.db"])
        assert result.exit_code != 0
        assert "not found" in result.output

    def test_report_console_with_data(self, runner: CliRunner, tmp_db: Path) -> None:
        result = runner.invoke(cli, ["report", "--format", "console", "--db", str(tmp_db)])
        assert result.exit_code == 0
        assert "Test Health Summary" in result.output
        assert "Healed:" in result.output
        assert "#login-btn" in result.output

    def test_report_console_custom_days(self, runner: CliRunner, tmp_db: Path) -> None:
        result = runner.invoke(cli, ["report", "--format", "console", "--db", str(tmp_db), "--days", "7"])
        assert result.exit_code == 0
        assert "last 7 days" in result.output

    def test_report_html_creates_file(self, runner: CliRunner, tmp_db: Path, tmp_path: Path) -> None:
        out = str(tmp_path / "report.html")
        result = runner.invoke(cli, ["report", "--format", "html", "--db", str(tmp_db), "--output", out])
        assert result.exit_code == 0
        assert "HTML report written to" in result.output
        assert Path(out).exists()

    def test_report_json_creates_file(self, runner: CliRunner, tmp_db: Path, tmp_path: Path) -> None:
        out = str(tmp_path / "report.json")
        result = runner.invoke(cli, ["report", "--format", "json", "--db", str(tmp_db), "--output", out])
        assert result.exit_code == 0
        assert "JSON report written to" in result.output
        assert Path(out).exists()


class TestDoctorCommand:
    def test_doctor_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["doctor", "--help"])
        assert result.exit_code == 0

    def test_doctor_missing_db(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["doctor", "--db", "nonexistent.db"])
        assert result.exit_code == 0
        assert "NOT FOUND" in result.output
        assert "No database found" in result.output

    def test_doctor_with_data(self, runner: CliRunner, tmp_db: Path) -> None:
        result = runner.invoke(cli, ["doctor", "--db", str(tmp_db)])
        assert result.exit_code == 0
        assert "Breadcrumb Doctor" in result.output
        assert "exists" in result.output
        assert "Schema version: 1" in result.output
        assert "Fingerprints: 1" in result.output
        assert "Healing events: 1" in result.output
        assert "Quarantined tests: 0" in result.output
        assert "Status: OK" in result.output

    def test_doctor_stale_fingerprints(self, runner: CliRunner, tmp_path: Path) -> None:
        """Fingerprints older than 30 days should be flagged as stale."""
        db_path = tmp_path / "stale.db"
        conn = sqlite3.connect(str(db_path))
        conn.executescript(
            """\
            CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            INSERT INTO schema_meta (key, value) VALUES ('schema_version', '1');
            CREATE TABLE fingerprints (
                test_id TEXT NOT NULL, locator TEXT NOT NULL,
                fingerprint_json TEXT NOT NULL, updated_at REAL NOT NULL,
                PRIMARY KEY (test_id, locator)
            );
            CREATE TABLE healing_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_id TEXT NOT NULL, locator TEXT NOT NULL,
                confidence REAL NOT NULL, original_json TEXT NOT NULL,
                healed_json TEXT NOT NULL, timestamp REAL NOT NULL
            );
            """
        )
        old_ts = time.time() - 60 * 86400  # 60 days ago
        conn.execute(
            "INSERT INTO fingerprints VALUES (?, ?, ?, ?)",
            ("test_old", "#old", json.dumps({"tag": "div"}), old_ts),
        )
        conn.commit()
        conn.close()

        result = runner.invoke(cli, ["doctor", "--db", str(db_path)])
        assert result.exit_code == 0
        assert "stale" in result.output
        assert "older than 30 days" in result.output


class TestGenerateCommand:
    def test_generate_outputs_page_object(self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
        """CLI generate command produces POM + test code without hitting the network."""
        fake_elements = [{"tag": "button", "id": "login", "text": "Login", "type": "", "classes": []}]
        monkeypatch.setattr("breadcrumb.generate.crawler.PageCrawler.crawl", lambda self, url: fake_elements)
        result = runner.invoke(cli, ["generate", "http://example.com"])
        assert result.exit_code == 0
        assert "class" in result.output  # POM class is emitted


class TestInitCommand:
    def test_init_creates_files(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(cli, ["init", "--name", "testproj", "--dir", str(tmp_path)])
        assert result.exit_code == 0
        assert "testproj" in result.output

        conftest = tmp_path / "conftest.py"
        assert conftest.exists()
        content = conftest.read_text(encoding="utf-8")
        assert "testproj" in content
        assert "heal_page" in content

        sample = tmp_path / "tests" / "test_sample.py"
        assert sample.exists()
        sample_content = sample.read_text(encoding="utf-8")
        assert "test_example" in sample_content

    def test_init_default_name(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(cli, ["init", "--dir", str(tmp_path)])
        assert result.exit_code == 0
        conftest = tmp_path / "conftest.py"
        assert conftest.exists()
        content = conftest.read_text(encoding="utf-8")
        assert "myproject" in content


class TestCliGroup:
    def test_cli_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "report" in result.output
        assert "doctor" in result.output
        assert "generate" in result.output
        assert "init" in result.output
