# Getting Started

## Installation

Breadcrumb requires Python 3.10+ and Playwright.

```bash
pip install pytest-breadcrumb[playwright]
playwright install chromium
```

For the full feature set (AI generation + MCP server):

```bash
pip install pytest-breadcrumb[playwright,ai,mcp]
```

To build the documentation locally:

```bash
pip install pytest-breadcrumb[docs]
mkdocs serve
```

### Install from source

```bash
git clone https://github.com/FaraazSuffla/breadcrumb.git
cd breadcrumb
pip install -e ".[dev]"
playwright install chromium
pre-commit install
```

---

## Option 1: One-line wrapper

Wrap any Playwright `Page` object with `crumb()`:

```python
from playwright.sync_api import sync_playwright
from breadcrumb import crumb

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = crumb(browser.new_page(), test_id="test_checkout")

    page.goto("https://myapp.com/checkout")
    page.locator("#place-order-btn").click()   # fingerprinted automatically
```

On the first run, Breadcrumb saves a fingerprint for `#place-order-btn`.
If the locator breaks on a later run (e.g. the developer renames it to
`#submit-order`), Breadcrumb scores all visible elements against the stored
fingerprint and heals automatically — if confidence exceeds the threshold (default 0.5).

---

## Option 2: pytest plugin

The pytest plugin provides a ready-made `heal_page` fixture.

### 1. Enable the plugin

```ini
# pytest.ini or pyproject.toml
[tool.pytest.ini_options]
addopts = "--breadcrumb"
```

Or pass the flag directly:

```bash
pytest --breadcrumb
```

### 2. Use the fixture

```python
def test_login(heal_page):
    heal_page.goto("https://myapp.com/login")
    heal_page.locator("#username").fill("alice")
    heal_page.locator("#password").fill("secret")
    heal_page.locator("#login-btn").click()
    assert heal_page.locator(".dashboard").is_visible()
```

### 3. Generate a report

```bash
pytest --breadcrumb --breadcrumb-report
# or after the run:
breadcrumb report --format html --output report.html
```

---

## Configuring the threshold

The default confidence threshold is **0.5**. Below this value, no healing
occurs and the test fails normally — Breadcrumb never silently picks the
wrong element.

Pass a custom threshold via the `HealablePage` constructor:

```python
from breadcrumb import HealablePage

page = HealablePage(raw_page, test_id="my_test", threshold=0.7)
```

Or via `crumb()`:

```python
page = crumb(raw_page, test_id="my_test", threshold=0.7)
```

---

## Project scaffold

Use `breadcrumb init` to scaffold a new project in seconds:

```bash
breadcrumb init --name my-e2e-suite --dir ./e2e
```

This creates:

```
e2e/
├── conftest.py        # heal_page fixture
└── tests/
    └── test_sample.py # example test
```
