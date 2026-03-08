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
</p>

---

## What is this?

Your Playwright test clicks `#login-btn`. A developer renames it to `.auth-button`. The button still works — but your test crashes.

**Breadcrumb fixes this.** It remembers what every element looks like the first time your test touches it. If the locator breaks later, it finds the element anyway using the text, position, tag, and other signals it stored. Your test passes. You change nothing.

No cloud. No API keys. One line of code.

---

## Install

> Not on PyPI yet. Install from source:

```bash
git clone https://github.com/FaraazSuffla/breadcrumb.git
cd breadcrumb
pip install -e ".[dev]"
playwright install chromium
```

Requires **Python 3.10+**.

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
    page.locator("#login-btn").click()   # Run 1: element fingerprinted and saved
    # Developer renames #login-btn to .auth-button ...
    page.locator("#login-btn").click()   # Run 2: healed automatically ✅
```

> **Note:** `test_id` is required for healing to work. It tells Breadcrumb which fingerprint to look up when a locator breaks. Use a unique name per test.

### Option 2 — pytest (recommended)

Use the built-in `heal_page` fixture. No `test_id` needed — it's set automatically.

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

---

## How it works

**First run:** Breadcrumb saves a fingerprint of every element your test touches — tag, text, ID, classes, position, and more — to a local `.breadcrumb.db` file.

**Next run (if locator breaks):** Breadcrumb scans the page, scores every visible element against the saved fingerprint, and uses the best match. If nothing scores above 0.5 confidence, the test fails normally — Breadcrumb never silently picks a wrong element.

That's it.

---

## CLI

```bash
breadcrumb report                            # print healing summary to console
breadcrumb report --format html              # export HTML dashboard
breadcrumb report --format json              # export JSON data
breadcrumb report --days 7                   # limit to last 7 days
breadcrumb doctor                            # check DB health and stale fingerprints
breadcrumb init --name myproject             # scaffold a new project
breadcrumb generate https://myapp.com        # generate Page Object Model from a URL
breadcrumb generate https://myapp.com --out ./tests  # write files to a directory
```

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
| MCP server + docs site | 🔜 Next |

---

## Security

The `generate` command crawls arbitrary web pages and embeds HTML attribute values into generated Python source files. Breadcrumb protects against this in two ways:

- **CSS selector injection** — `id`, `class`, and `name` attributes are stripped to word characters and hyphens only. `data-testid` and text values are backslash-escaped for CSS quoted strings.
- **Code injection** — selectors are embedded using Python's `repr()`, which safely escapes all quote variants, backslashes, and newlines before writing them into generated `.py` files.
- **Prompt injection** — when Ollama is used, page names and element data are stripped of non-printable characters and capped in length before being embedded in LLM prompts.

No generated file can execute or exfiltrate data beyond what Playwright already does.

---

## Common Pitfalls

**Healing not working?** Make sure you pass `test_id` when using the standalone wrapper:

```python
# Wrong — healing silently disabled
page = crumb(browser.new_page())

# Right — healing works
page = crumb(browser.new_page(), test_id="test_login")
```

The pytest `heal_page` fixture sets `test_id` automatically. This only affects standalone usage.

**Database in the wrong place?** `.breadcrumb.db` is created in whatever directory you run Python from. To set a fixed location:

```python
page = crumb(browser.new_page(), test_id="test_login", db_path="./tests/.breadcrumb.db")
```

---

## Benchmarks

Healing a typical page (30-100 elements) adds under **15ms** per broken locator.

| Operation | Time |
|---|---|
| Single similarity score | ~0.009 ms |
| Heal over 100 candidates | ~2 ms |
| Heal over 1,000 candidates | ~14 ms |
| Fingerprint write (SQLite) | ~0.29 ms |
| Fingerprint read | ~0.006 ms |

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
