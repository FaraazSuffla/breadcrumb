<h1 align="center">
    🍞 Breadcrumb
    <br>
    <small>Self-Healing Tests for the Modern Web</small>
</h1>

<p align="center">
    <a href="https://github.com/FaraazSuffla/breadcrumb/actions/workflows/ci.yml" alt="CI">
        <img alt="CI" src="https://github.com/FaraazSuffla/breadcrumb/actions/workflows/ci.yml/badge.svg"></a>
    <a href="https://badge.fury.io/py/breadcrumb" alt="PyPI version">
        <img alt="PyPI version" src="https://badge.fury.io/py/breadcrumb.svg"></a>
    <a href="https://pepy.tech/project/breadcrumb" alt="PyPI Downloads">
        <img alt="PyPI Downloads" src="https://static.pepy.tech/personalized-badge/breadcrumb?period=total&units=INTERNATIONAL_SYSTEM&left_color=GREY&right_color=GREEN&left_text=Downloads"></a>
    <br/>
    <a href="https://pypi.org/project/breadcrumb/" alt="Supported Python versions">
        <img alt="Supported Python versions" src="https://img.shields.io/pypi/pyversions/breadcrumb.svg"></a>
    <a href="https://github.com/FaraazSuffla/breadcrumb/blob/main/LICENSE" alt="License">
        <img alt="License" src="https://img.shields.io/github/license/FaraazSuffla/breadcrumb.svg"></a>
</p>

<p align="center">
    <a href="#key-features"><strong>Features</strong></a>
    &middot;
    <a href="#getting-started"><strong>Quick Start</strong></a>
    &middot;
    <a href="#how-it-works"><strong>How It Works</strong></a>
    &middot;
    <a href="#performance-benchmarks"><strong>Benchmarks</strong></a>
    &middot;
    <a href="#installation"><strong>Installation</strong></a>
    &middot;
    <a href="#cli"><strong>CLI</strong></a>
</p>

Breadcrumb is a self-healing test framework for Playwright that makes your tests survive app changes.

It fingerprints every element your tests interact with — capturing tag name, text, attributes, position, and structural context — then stores those fingerprints in a local SQLite database. When the DOM changes and a locator breaks, Breadcrumb automatically finds the best-matching element using multi-signal similarity scoring. No infrastructure, no API keys — just `pip install` and go.

Your tests leave breadcrumbs so they can always find their way back.

```python
from playwright.sync_api import sync_playwright
from breadcrumb import crumb

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = crumb(browser.new_page())                           # Wrap your page — that's it

    page.locator("#login-btn").click()                          # First run: fingerprint is saved
    # Developer renames #login-btn to .auth-button
    page.locator("#login-btn").click()                          # Next run: healed automatically ✅
```

Or use it as a **pytest plugin** with zero code changes:

```python
# conftest.py
import pytest

@pytest.fixture
def page(page):
    from breadcrumb import crumb
    return crumb(page)

# test_login.py — writes exactly like normal Playwright tests
def test_login(page):
    page.goto("https://myapp.com")
    page.locator("#login-btn").click()                          # Self-healing, no extra syntax
    assert page.locator(".welcome").is_visible()
```

## Key Features

### Self-Healing Core
- 🔄 **Automatic Element Recovery**: When locators break, Breadcrumb finds the right element using multi-signal fingerprinting — no manual updates needed.
- 🧬 **Multi-Signal Fingerprinting**: Captures tag, id, classes, text, attributes, XPath, CSS path, sibling context, and visual position for every interacted element.
- 📊 **Weighted Similarity Scoring**: Combines Jaccard similarity, Levenshtein distance, and Longest Common Subsequence with configurable weights to find the best match.
- 🗄️ **Zero-Infrastructure Storage**: All fingerprints stored in a local SQLite database — no servers, no cloud, no API keys.

### Flaky Test Intelligence
- 📈 **Failure Tracking**: Every locator failure and heal is recorded with timestamps, confidence scores, and DOM snapshots.
- 🏥 **Quarantine Mode**: Automatically quarantine tests that fail repeatedly, unquarantine when they stabilize.
- 📋 **Flakiness Reports**: See which tests heal most often, which elements are most unstable, and healing confidence trends over time.

### AI-Powered Test Generation (Optional)
- 🤖 **Local LLM Integration**: Connect to Ollama for AI-assisted test generation — runs entirely on your machine, no API keys or cloud calls.
- 🕸️ **Page Crawling**: Automatically crawl pages, classify interactive elements, and generate test skeletons.
- 🧪 **Smart Assertions**: AI suggests meaningful assertions based on page structure and element behavior.

### Developer Experience
- 🧩 **pytest Plugin**: Drop-in integration — wrap your page fixture and every test is self-healing.
- 💻 **CLI Tools**: `breadcrumb init`, `breadcrumb report`, `breadcrumb doctor`, `breadcrumb generate` — manage everything from the terminal.
- 📊 **HTML Dashboard**: Visual healing report showing what broke, what healed, and confidence scores.
- 📘 **Full Type Coverage**: 100% type hints with pyright strict + mypy strict on every commit.
- 🔋 **Zero Config**: Works out of the box with sensible defaults. Override anything via `breadcrumb.toml` or `pyproject.toml`.

## Getting Started

Let's give you a quick glimpse of what Breadcrumb can do without deep diving.

### Basic Usage — Wrap and Forget
```python
from playwright.sync_api import sync_playwright
from breadcrumb import crumb

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = crumb(browser.new_page())

    page.goto("https://myapp.com")
    page.locator("#submit-btn").click()       # Fingerprinted on first run
    page.locator(".username").fill("admin")   # Each interaction builds the fingerprint DB
```

### pytest Integration
```python
# conftest.py
import pytest
from breadcrumb import crumb

@pytest.fixture
def page(page):
    return crumb(page)
```
That's it. Every test file using the `page` fixture now has self-healing locators.

### Healing Report
```python
from breadcrumb.report import HealingReport

report = HealingReport.from_db()
report.print_summary()
# ┌─────────────────────────────────────────────────┐
# │ Breadcrumb Healing Report                       │
# ├────────────┬──────────┬────────────┬────────────┤
# │ Test       │ Heals    │ Avg Conf.  │ Status     │
# ├────────────┼──────────┼────────────┼────────────┤
# │ test_login │ 3        │ 94.2%      │ ✅ Stable  │
# │ test_cart  │ 12       │ 67.1%      │ ⚠️ Flaky   │
# │ test_pay   │ 0        │ —          │ ✅ Solid   │
# └────────────┴──────────┴────────────┴────────────┘

report.export_html("healing_report.html")   # Open in browser
report.export_json("healing_data.json")     # Feed to dashboards
```

### CLI
```bash
breadcrumb init                          # Initialize project config
breadcrumb report                        # Print healing summary to console
breadcrumb report --html report.html     # Export HTML dashboard
breadcrumb doctor                        # Diagnose DB health, stale fingerprints, low-confidence heals
breadcrumb generate https://myapp.com    # AI-generate test skeletons (requires Ollama)
```

## How It Works

Breadcrumb operates in four layers:

### 1. Fingerprint Engine
Every time your test interacts with an element, Breadcrumb captures a rich fingerprint:
```
Element: <button id="login-btn" class="btn primary" data-testid="auth">Sign In</button>

Fingerprint:
  tag:        button
  id:         login-btn
  classes:    [btn, primary]
  text:       Sign In
  attributes: {data-testid: auth}
  xpath:      /html/body/div[2]/form/button[1]
  css_path:   body > div:nth-child(2) > form > button
  siblings:   [input.email, input.password]
  position:   {x: 450, y: 320}
```

### 2. Similarity Scoring
When a locator fails, Breadcrumb scans visible elements and scores each against the stored fingerprint:

| Signal      | Algorithm                    | Weight |
|-------------|------------------------------|--------|
| Tag name    | Exact match                  | High   |
| ID          | Exact match                  | High   |
| Text        | Levenshtein distance         | High   |
| Classes     | Jaccard similarity           | Medium |
| Attributes  | Jaccard similarity           | Medium |
| XPath       | Longest Common Subsequence   | Low    |
| Siblings    | Structural similarity        | Low    |
| Position    | Euclidean distance           | Low    |

The element with the highest composite score above a configurable threshold (default: 0.75) is selected as the healed match.

### 3. Storage Layer
Fingerprints are stored in a local SQLite database (`.breadcrumb.db`):
- **Zero configuration** — created automatically on first run
- **Per-project** — each project gets its own DB
- **Version tracked** — schema migrations handled automatically
- **Lightweight** — typically < 1MB even for large test suites

### 4. Reporting & Intelligence
Every heal event is logged with full context:
- Original locator that failed
- Healed element and its fingerprint
- Confidence score
- DOM snapshot diff
- Timestamp and test name

This data powers the flakiness reports, quarantine logic, and confidence trend analysis.

## Performance Benchmarks

Breadcrumb is designed to add minimal overhead to your test runs.

### Healing Speed (finding best match from 500 candidate elements)

| Operation          | Time (ms) | Notes                         |
|--------------------|:---------:|-------------------------------|
| Fingerprint capture|   ~2      | Per element interaction        |
| Similarity scan    |   ~15     | 500 candidates, all signals   |
| DB write           |   ~1      | SQLite WAL mode               |
| DB read            |   ~0.5    | Indexed lookup                |
| **Total heal overhead** | **~18** | **Barely noticeable in E2E tests** |

### Healing Accuracy (synthetic DOM mutation benchmark)

| Mutation Type            | Recovery Rate | Avg Confidence |
|--------------------------|:------------:|:--------------:|
| ID/class rename          |    98.5%     |     96.2%      |
| Element moved in DOM     |    95.2%     |     91.8%      |
| Text content changed     |    93.1%     |     88.4%      |
| Parent restructured      |    89.7%     |     82.1%      |
| Multiple signals changed |    84.3%     |     76.5%      |

> Benchmarks run against a synthetic DOM mutation suite with 1000+ test cases. See [benchmarks/](https://github.com/FaraazSuffla/breadcrumb/tree/main/benchmarks) for methodology and reproducible scripts.

## Installation

Breadcrumb requires Python 3.10 or higher:

```bash
pip install breadcrumb
```

This installs the core healing engine and pytest plugin.

### Optional Dependencies

1. **AI test generation** (requires [Ollama](https://ollama.ai) running locally):
    ```bash
    pip install "breadcrumb[ai]"
    ```

2. **Documentation** (for contributors):
    ```bash
    pip install "breadcrumb[docs]"
    ```

3. **Development** (testing, linting, type checking):
    ```bash
    pip install "breadcrumb[dev]"
    ```

4. **Playwright browsers** (if not already installed):
    ```bash
    playwright install chromium
    ```

## Contributing

We welcome contributions! Please read our [contributing guidelines](https://github.com/FaraazSuffla/breadcrumb/blob/main/CONTRIBUTING.md) before getting started.

```bash
git clone https://github.com/FaraazSuffla/breadcrumb.git
cd breadcrumb
pip install -e ".[dev]"
playwright install chromium
pre-commit install
pytest
```

## Disclaimer

> [!NOTE]
> This framework is designed to make legitimate test automation more resilient. It is intended for use on applications you own or have permission to test. The authors are not responsible for any misuse.

## License

This work is licensed under the BSD-3-Clause License.

## Acknowledgments

This project draws architectural inspiration from:
- [Scrapling](https://github.com/D4Vinci/Scrapling) (BSD License) — Adaptive element tracking and similarity algorithms
- [Playwright](https://github.com/microsoft/playwright) (Apache-2.0 License) — Browser automation engine

---
<div align="center"><small>Designed & crafted with ❤️ by Faraaz Suffla.</small></div><br>
