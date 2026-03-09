<h1 align="center">
    🍞 Breadcrumb
    <br>
    <small>Self-Healing Playwright Tests</small>
</h1>

<p align="center">
    <a href="https://github.com/FaraazSuffla/breadcrumb/actions/workflows/ci.yml">
        <img alt="CI" src="https://github.com/FaraazSuffla/breadcrumb/actions/workflows/ci.yml/badge.svg"></a>
    <a href="https://github.com/FaraazSuffla/breadcrumb/blob/main/LICENSE">
        <img alt="License" src="https://img.shields.io/github/license/FaraazSuffla/breadcrumb.svg"></a>
    <img alt="Python" src="https://img.shields.io/badge/python-3.10%2B-blue">
    <img alt="Status" src="https://img.shields.io/badge/status-pre--alpha-orange">
    <a href="https://faraazsuffla.github.io/breadcrumb/">
        <img alt="Docs" src="https://img.shields.io/badge/docs-online-blue"></a>
</p>

---

## What is this?

Your Playwright test clicks `#login-btn`. A developer renames it to `.auth-button`. The button still works — but your test crashes.

**Breadcrumb fixes this automatically.** On the first run it fingerprints every element your test touches. When a locator breaks later, it finds the right element using the text, position, tag, DOM path, and other signals it stored — then carries on. No cloud. No API keys. One line of code.

Beyond healing, Breadcrumb also:
- **Tracks flaky tests** — measures per-test flip rates and auto-quarantines chronic failures
- **Generates tests** — crawls a page and writes Page Object Model + pytest skeletons for you
- **Exposes MCP tools** — lets Claude and other AI assistants query your healing database directly

---

## Install

```bash
pip install pytest-breadcrumb[playwright]
playwright install chromium
```

Requires **Python 3.10+**.

> **Pre-alpha:** This is an early release (`0.1.0a2`). The API is stable but the project is under active development.

**Optional extras:**

| Extra | Installs |
|---|---|
| `pip install pytest-breadcrumb[playwright]` | Playwright wrapper |
| `pip install pytest-breadcrumb[mcp]` | MCP server (for AI assistants) |
| `pip install pytest-breadcrumb[ai]` | Ollama integration for AI test generation |
| `pip install pytest-breadcrumb[playwright,ai,mcp]` | Full feature set |

**Install from source (development):**

```bash
git clone https://github.com/FaraazSuffla/breadcrumb.git
cd breadcrumb
pip install -e ".[dev]"
playwright install chromium
```

---

## Quick Start

### Option 1 — Standalone script

Wrap your Playwright page with `crumb()` and pass a `test_id`:

```python
from playwright.sync_api import sync_playwright
from breadcrumb import crumb

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = crumb(browser.new_page(), test_id="test_login")  # one-line wrapper

    page.goto("https://myapp.com")
    page.locator("#login-btn").click()   # Run 1: fingerprinted and saved
    # Developer renames #login-btn to .auth-button ...
    page.locator("#login-btn").click()   # Run 2: healed automatically ✅
```

> **Note:** `test_id` is required for standalone usage. It tells Breadcrumb which fingerprint to look up when a locator breaks. The pytest fixture sets it automatically.

### Option 2 — pytest (recommended)

Use the built-in `heal_page` fixture — `test_id` is set from the test name automatically:

```python
# test_login.py
def test_login(heal_page):
    heal_page.goto("https://myapp.com")
    heal_page.locator("#login-btn").click()
    assert heal_page.locator(".welcome").is_visible()
```

```bash
pytest --breadcrumb --breadcrumb-report
```

`--breadcrumb` enables healing. `--breadcrumb-report` prints a healing summary to the console at the end of the test session. `crumb` and `heal` are identical aliases — use whichever feels natural.

---

## How it works

**1. Learn** — On the first run, Breadcrumb fingerprints every element your test touches: tag name, text content, ID, CSS classes, attributes, DOM path, sibling context, and visual position. Fingerprints are saved to `.breadcrumb.db` (local SQLite, WAL mode).

**2. Heal** — When a locator breaks on a later run, Breadcrumb scans the live page, scores every visible element against the stored fingerprint using seven similarity signals, and retries with the best match. If nothing scores above 0.5 confidence, the test fails normally — Breadcrumb never silently picks a wrong element.

**3. Report** — Every heal event is logged with the original locator, new locator, and confidence score. Breadcrumb tracks per-test pass/fail rates and auto-quarantines tests that flip repeatedly.

---

## Features

| Feature | Status |
|---|---|
| Self-healing locators (Playwright wrapper) | ✅ Working |
| pytest plugin (`heal_page` fixture) | ✅ Working |
| Flaky test tracker + auto-quarantine | ✅ Working |
| Console / HTML / JSON reports | ✅ Working |
| CLI (`report`, `doctor`, `init`, `generate`) | ✅ Working |
| AI test generation (Page Object Models) | ✅ Working |
| MCP server + docs site | ✅ Working |

---

## CLI

```bash
# View healing summary
breadcrumb report
breadcrumb report --format html          # → report.html dashboard
breadcrumb report --format json          # → report.json
breadcrumb report --days 7               # limit to last 7 days

# Check database health
breadcrumb doctor

# Generate tests from a live page
breadcrumb generate https://myapp.com
breadcrumb generate https://myapp.com --out ./tests

# Scaffold a new project
breadcrumb init --name myproject         # creates conftest.py + tests/test_sample.py

# Start the MCP server (requires pip install pytest-breadcrumb[mcp])
breadcrumb mcp
breadcrumb mcp --db /path/to/.breadcrumb.db
```

---

## Flaky Test Tracking

Every test run is recorded. Breadcrumb computes a flip rate (how often a test alternates pass → fail) and classifies each test automatically:

| Tier | Flip rate | What happens |
|---|---|---|
| **Stable** | 0% | Normal |
| **Intermittent** | 0–20% | Flagged in report |
| **Flaky** | 20–50% | Auto-quarantined |
| **Chronic** | > 50% | Quarantined + doctor warning |

Quarantined tests are skipped automatically until they recover. View the full breakdown:

```bash
breadcrumb report --format html   # opens a dashboard with per-test status
breadcrumb doctor                 # shows quarantine count and stale fingerprints
```

---

## MCP / AI Tools

Breadcrumb exposes **7 tools via MCP**, letting Claude and other AI assistants query your healing database directly.

**Install:**

```bash
pip install pytest-breadcrumb[mcp]
```

**Configure Claude Desktop** — edit your `claude_desktop_config.json`:

- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux:** `~/.config/Claude/claude_desktop_config.json`

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

**Available tools:**

| Tool | Description |
|---|---|
| `breadcrumb_stats` | Total fingerprint + heal-event counts |
| `breadcrumb_report` | Full healing report for the last N days |
| `breadcrumb_doctor` | DB health check (schema, stale fingerprints, quarantine) |
| `breadcrumb_healing_events` | Recent heal events, filterable by test name |
| `breadcrumb_flaky_tests` | Per-test flakiness classification |
| `breadcrumb_generate_tests` | Crawl a URL and return POM + pytest source code |
| `breadcrumb_list_fingerprints` | All stored element fingerprints |

---

## Security

The `generate` command crawls arbitrary web pages and embeds HTML attribute values into generated Python source files. Breadcrumb protects against this in three ways:

- **CSS selector injection** — `id`, `class`, and `name` attributes are stripped to word characters and hyphens only. `data-testid` and text values are backslash-escaped for CSS quoted strings.
- **Code injection** — selectors are embedded using Python's `repr()`, which safely escapes all quote variants, backslashes, and newlines before writing them into generated `.py` files.
- **Prompt injection** — when Ollama is used, page names and element data are stripped of non-printable characters and capped in length before being embedded in LLM prompts.

No generated file can execute or exfiltrate data beyond what Playwright already does.

---

## Benchmarks

Healing a typical page (30–100 elements) adds under **15 ms** per broken locator.

| Operation | Time |
|---|---|
| Single similarity score | ~0.009 ms |
| Heal over 100 candidates | ~2 ms |
| Heal over 1,000 candidates | ~14 ms |
| Fingerprint write (SQLite) | ~0.29 ms |
| Fingerprint read | ~0.006 ms |

---

## Common Pitfalls

**Healing not working?** Always pass an explicit `test_id` when using the standalone wrapper:

```python
# Avoid — test_id is auto-inferred from the call stack, which can be unstable
page = crumb(browser.new_page())

# Recommended — stable, predictable fingerprint key
page = crumb(browser.new_page(), test_id="test_login")
```

Without an explicit `test_id`, Breadcrumb infers one from the calling filename and function name. If you refactor code or rename functions, the inferred ID changes and healing breaks. The pytest `heal_page` fixture sets `test_id` automatically from the test node ID.

**Database in the wrong place?** `.breadcrumb.db` is created in the directory you run Python from. To set a fixed location:

```python
page = crumb(browser.new_page(), test_id="test_login", db_path="./tests/.breadcrumb.db")
```

**Confidence too low?** If your app has significant DOM changes between runs, lower the threshold:

```python
page = crumb(browser.new_page(), test_id="test_login", threshold=0.4)
```

The default is `0.5`. Going below `0.3` risks false positives.

See the [Troubleshooting guide](docs/troubleshooting.md) for more common issues.

---

## Contributing

```bash
git clone https://github.com/FaraazSuffla/breadcrumb.git
cd breadcrumb
pip install -e ".[dev]"
playwright install chromium
pre-commit install
pytest
```

See [CONTRIBUTING.md](https://github.com/FaraazSuffla/breadcrumb/blob/main/CONTRIBUTING.md) for details.

---

## License

BSD-3-Clause. See [LICENSE](https://github.com/FaraazSuffla/breadcrumb/blob/main/LICENSE).

## Acknowledgments

- [Scrapling](https://github.com/D4Vinci/Scrapling) (BSD License) — adaptive element tracking inspiration
- [Playwright](https://github.com/microsoft/playwright) (Apache-2.0) — browser automation engine

---

<div align="center"><small>Designed & crafted with ❤️ by Faraaz Suffla</small></div>
