# CLI Reference

The `breadcrumb` command provides five subcommands for working with your
healing database, generating tests, and running the MCP server.

```
breadcrumb [OPTIONS] COMMAND [ARGS]...
```

---

## `breadcrumb report`

Generate a healing summary from the database.

```bash
breadcrumb report [OPTIONS]
```

**Options:**

| Option | Default | Description |
|---|---|---|
| `--db PATH` | `.breadcrumb.db` | Path to the database file |
| `--format {console,html,json}` | `console` | Output format |
| `--days N` | `30` | Include events from the last N days |
| `--output PATH` | `report.html` / `report.json` | Output file (html/json only) |

**Examples:**

```bash
# Console summary (last 30 days)
breadcrumb report

# HTML dashboard
breadcrumb report --format html --output my-report.html

# JSON export for CI tooling
breadcrumb report --format json --days 7 --output ci-report.json

# Use a custom database
breadcrumb report --db /path/to/project/.breadcrumb.db
```

---

## `breadcrumb doctor`

Diagnose the health of the breadcrumb database.

```bash
breadcrumb doctor [OPTIONS]
```

**Options:**

| Option | Default | Description |
|---|---|---|
| `--db PATH` | `.breadcrumb.db` | Path to the database file |

**Output includes:**

- Schema version
- Total fingerprint count (with stale fingerprint count if any are older than 30 days)
- Total healing event count
- Test run count (if Phase 3 tables exist)
- Quarantined test count
- Overall status: `OK` or issues

**Example:**

```bash
$ breadcrumb doctor
Breadcrumb Doctor
DB: .breadcrumb.db (exists)
Schema version: 2
Fingerprints: 42
Healing events: 7
Test runs: 150
Quarantined tests: 1
Status: OK
```

---

## `breadcrumb generate`

Crawl a URL and generate a Page Object Model + pytest test skeleton.

```bash
breadcrumb generate URL
```

**Arguments:**

| Argument | Description |
|---|---|
| `URL` | URL of the page to crawl |

**Example:**

```bash
breadcrumb generate https://myapp.com/login
```

This outputs two Python files:

1. A **Page Object Model** with locators for all interactive elements
2. A **pytest test file** with stub tests for each element

If [Ollama](https://ollama.com/) is installed, richer test descriptions are generated
using a local LLM.

---

## `breadcrumb init`

Scaffold a new breadcrumb test project.

```bash
breadcrumb init [OPTIONS]
```

**Options:**

| Option | Default | Description |
|---|---|---|
| `--name TEXT` | `myproject` | Project name (used in file headers) |
| `--dir PATH` | `.` | Output directory |

**Example:**

```bash
breadcrumb init --name checkout-suite --dir ./e2e
```

Creates:

```
e2e/
├── conftest.py         # heal_page fixture
└── tests/
    └── test_sample.py  # example test
```

---

## `breadcrumb mcp`

Start the MCP server over stdio transport for AI assistant integration.

```bash
breadcrumb mcp [OPTIONS]
```

**Options:**

| Option | Default | Description |
|---|---|---|
| `--db PATH` | `.breadcrumb.db` | Default database path for tools |

**Requires:** `pip install playwright-crumb[mcp]`

See [MCP Server](mcp.md) for full setup instructions and available tools.
