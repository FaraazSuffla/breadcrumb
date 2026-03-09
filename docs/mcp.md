# MCP Server

Breadcrumb ships a [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) server
that exposes breadcrumb operations as native tools for Claude Code, Claude Desktop, and
other MCP-compatible AI assistants.

## Installation

```bash
pip install playwright-crumb[mcp]
```

## Claude Desktop / Claude Code Configuration

Add breadcrumb to your `claude_desktop_config.json` (or Claude Code MCP settings):

```json
{
  "mcpServers": {
    "breadcrumb": {
      "command": "breadcrumb",
      "args": ["mcp"]
    }
  }
}
```

With a custom database path:

```json
{
  "mcpServers": {
    "breadcrumb": {
      "command": "breadcrumb",
      "args": ["mcp", "--db", "/path/to/project/.breadcrumb.db"]
    }
  }
}
```

## Starting the server manually

```bash
breadcrumb mcp
```

The server listens on **stdio** — this is the standard transport for local MCP servers.

---

## Available Tools

### `breadcrumb_stats`

Return fingerprint and healing-event counts from the database.

**Input:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `db_path` | string | `.breadcrumb.db` | Path to the database file |

**Example output:**

```json
{
  "fingerprints": 42,
  "healing_events": 7
}
```

---

### `breadcrumb_report`

Return a full JSON healing report for the last N days.

**Input:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `db_path` | string | `.breadcrumb.db` | Path to the database file |
| `days` | integer | `30` | Report window in days |

**Example output:**

```json
{
  "generated_at": 1741478400.0,
  "period_days": 30,
  "summary": {
    "total_tests": 10,
    "healed": 3,
    "flaky": 1,
    "failing": 0
  },
  "healing_events": [...],
  "top_locators": [...]
}
```

---

### `breadcrumb_doctor`

Run a health check on the breadcrumb database.

**Input:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `db_path` | string | `.breadcrumb.db` | Path to the database file |

**Example output:**

```json
{
  "db_path": ".breadcrumb.db",
  "schema_version": "2",
  "fingerprints": 42,
  "stale_fingerprints": 0,
  "healing_events": 7,
  "test_runs": 150,
  "quarantined_tests": 1,
  "status": "OK"
}
```

`status` is `"OK"` when everything is healthy, `"WARNING"` when stale fingerprints exist,
and `"NOT FOUND"` when the database file doesn't exist.

---

### `breadcrumb_healing_events`

Retrieve recent healing events, optionally filtered by test ID.

**Input:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `db_path` | string | `.breadcrumb.db` | Path to the database file |
| `test_id` | string | *(none)* | Filter to a specific test (optional) |
| `limit` | integer | `50` | Maximum events to return |

**Example output:**

```json
[
  {
    "test_id": "test_login",
    "locator": "#login-btn",
    "confidence": 0.87,
    "timestamp": 1741478400.0
  }
]
```

---

### `breadcrumb_flaky_tests`

Classify all tracked tests by flakiness and list quarantined tests.

**Input:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `db_path` | string | `.breadcrumb.db` | Path to the database file |

**Example output:**

```json
{
  "classifications": {
    "test_login": "Stable",
    "test_checkout": "Flaky",
    "test_payment": "Chronic"
  },
  "quarantined": ["test_checkout", "test_payment"]
}
```

Classification tiers: **Stable**, **Intermittent**, **Flaky**, **Chronic**.

---

### `breadcrumb_generate_tests`

Crawl a URL and generate a Page Object Model + pytest test file.

**Input:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `url` | string | Yes | URL of the page to crawl |

**Example output:**

```json
{
  "page_object": "class LoginPage:\n    ...",
  "test_file": "def test_login(heal_page):\n    ..."
}
```

---

### `breadcrumb_list_fingerprints`

List all stored element fingerprints.

**Input:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `db_path` | string | `.breadcrumb.db` | Path to the database file |

**Example output:**

```json
[
  {
    "test_id": "test_login",
    "locator": "#login-btn",
    "tag": "button",
    "text": "log in",
    "dom_path": ["html", "body", "div", "form", "button"],
    "attributes": [["class", "btn btn-primary"], ["type", "submit"]]
  }
]
```

---

## Programmatic usage

You can also use the server in your own Python code:

```python
import asyncio
from breadcrumb.mcp.server import create_server, main

# Create the server object (useful for testing / embedding)
server = create_server()

# Start over stdio (blocks until the client disconnects)
asyncio.run(main(db_path=".breadcrumb.db"))
```
