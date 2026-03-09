# Breadcrumb

**Self-healing Playwright test framework.** When a CSS locator breaks because a developer renamed a class or ID, Breadcrumb fingerprints every element touched during a test run and uses multi-signal similarity scoring to automatically find the right element — without cloud services, API keys, or external infrastructure.

**One-line wrapper. Zero config. Local-only.**

---

## Quick Install

```bash
pip install playwright-crumb[playwright]
playwright install chromium
```

## Quick Start

```python
from breadcrumb import crumb

# Wrap any Playwright page — that's it
page = crumb(browser.new_page(), test_id="test_login")
page.locator("#login-btn").click()   # fingerprinted on first run
                                     # auto-healed on subsequent runs
```

With the pytest plugin:

```python
def test_login(heal_page):
    heal_page.goto("https://myapp.com")
    heal_page.locator("#login-btn").click()   # zero extra syntax
```

Run:

```bash
pytest --breadcrumb --breadcrumb-report
```

---

## Why Breadcrumb?

| Without Breadcrumb | With Breadcrumb |
|---|---|
| `#login-btn` renamed → test fails | `#login-btn` renamed → test heals automatically |
| Manual locator hunt every sprint | Confidence score logged, nothing breaks |
| Flaky tests block CI | Flaky tests auto-quarantined, CI stays green |

---

## Feature Overview

- **Self-healing locators** — multi-signal fingerprint + similarity scoring
- **pytest plugin** — drop-in `heal_page` fixture, zero code changes
- **Flaky test tracker** — EWMA flip-rate, Stable / Flaky / Chronic classification
- **Reports** — console, HTML dashboard, JSON export
- **CLI** — `report`, `doctor`, `init`, `generate`, `mcp`
- **AI generation** — crawl a page → get a Page Object Model + pytest file
- **MCP server** — expose breadcrumb to Claude Code and other AI assistants

---

## Status

Breadcrumb is **pre-alpha**. All five phases of the roadmap are complete.
PyPI publication is the next step.

| Phase | Focus | Status |
|---|---|---|
| 1 | Fingerprint engine + SQLite storage + similarity scoring | ✅ Complete |
| 2 | Playwright wrapper + pytest plugin + basic healing | ✅ Complete |
| 3 | Flaky test tracker + quarantine + HTML/JSON/console reporting | ✅ Complete |
| 4 | CLI + AI test generation | ✅ Complete |
| 5 | MCP server + MkDocs documentation | ✅ Complete |
