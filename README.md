<h1 align="center">
    🍞 Breadcrumb
    <br>
    <small>Self-Healing Tests for the Modern Web</small>
</h1>

<p align="center">
    <a href="https://github.com/FaraazSuffla/breadcrumb/actions/workflows/ci.yml">
        <img alt="CI" src="https://github.com/FaraazSuffla/breadcrumb/actions/workflows/ci.yml/badge.svg"></a>
    <a href="https://github.com/FaraazSuffla/breadcrumb/blob/main/LICENSE">
        <img alt="License" src="https://img.shields.io/github/license/FaraazSuffla/breadcrumb.svg"></a>
    <img alt="Python" src="https://img.shields.io/badge/python-3.10%2B-blue">
    <img alt="Status" src="https://img.shields.io/badge/status-pre--alpha-orange">
</p>

<p align="center">
    <a href="#the-problem"><strong>The Problem</strong></a>
    &middot;
    <a href="#how-it-works"><strong>How It Works</strong></a>
    &middot;
    <a href="#quick-start"><strong>Quick Start</strong></a>
    &middot;
    <a href="#features"><strong>Features</strong></a>
    &middot;
    <a href="#cli"><strong>CLI</strong></a>
    &middot;
    <a href="#roadmap"><strong>Roadmap</strong></a>
    &middot;
    <a href="#installation"><strong>Installation</strong></a>
</p>

> **⚠️ Pre-Alpha — Phases 1–4 Complete**
>
> The core engine, Playwright integration, flaky test tracker, reporting suite, and CLI are all working. Phase 5 (MCP server + documentation site) is next. Star/watch the repo to follow progress. Contributions welcome.

---

## The Problem

A developer renames a button from `#login-btn` to `.auth-button`. Nothing about the app's behavior changed — but your entire test suite goes red. You spend the next hour grepping through test files, updating locators, and re-running CI. Multiply that by every frontend deploy, every team, every sprint.

**This is the #1 time sink in test automation.** Industry data shows teams spend 30–40% of their test maintenance effort just fixing broken locators that still point at the right element — it just has a new name.

Breadcrumb fixes this. It wraps your Playwright page, fingerprints every element your tests touch, and when a locator breaks, it automatically finds the right element using multi-signal similarity scoring. No cloud service, no API keys, no infrastructure — just a `pip install` and a one-line wrapper.

Your tests leave breadcrumbs so they can always find their way back.

## How It Works

Breadcrumb operates in four layers:

### Layer 1 — Fingerprint Engine
Every time your test interacts with an element, Breadcrumb captures a rich fingerprint:
```
Element: <button id="login-btn" class="btn primary" data-testid="auth">Sign In</button>

Fingerprint:
  tag:        button
  id:         login-btn
  classes:    [btn, primary]
  text:       Sign In
  attributes: {data-testid: auth, class: btn primary, id: login-btn}
  siblings:   [input, label]
  dom_path:   [html, body, form, button]
  position:   {x: 450, y: 320, width: 120, height: 40}
```
Each signal carries a different weight. An `id` match is strong evidence; a positional match alone is weak. The combination is what makes healing reliable.

### Layer 2 — Similarity Scoring
When a locator fails, Breadcrumb scans all visible elements and scores each one against the stored fingerprint:

| Signal      | Algorithm                  | Weight | Why                                    |
|-------------|----------------------------|--------|----------------------------------------|
| Tag name    | Exact match                | High   | A button rarely becomes a div          |
| ID          | Exact match                | High   | Most reliable when present             |
| Text        | Levenshtein distance       | High   | "Sign In" → "Log In" is still a match |
| Classes     | Jaccard similarity         | Medium | Classes shuffle but overlap            |
| Attributes  | Jaccard similarity         | Medium | data-testid often survives refactors   |
| DOM path    | Longest Common Subsequence | Low    | Structural hint, not a guarantee      |
| Siblings    | LCS similarity             | Low    | Nearby elements provide context        |
| Position    | Euclidean distance         | Low    | Layout shifts happen often             |

The element with the highest composite score above a configurable threshold (default: 0.5) is selected as the healed match. Below the threshold, the test fails normally — Breadcrumb never silently picks a wrong element.

### Layer 3 — Storage
Fingerprints and all heal events live in a local SQLite database (`.breadcrumb.db`), created automatically on first run. Zero servers, zero config. The schema migrates automatically across versions.

### Layer 4 — Reporting & Intelligence
Every heal event is logged with locator, confidence score, and timestamp. A built-in flaky test tracker records pass/fail history per test, computes flip-rate scores, and can auto-quarantine chronically unstable tests. Reports are available as plain text, HTML, and JSON.

## Quick Start

### Basic Usage — Wrap and Forget
```python
from playwright.sync_api import sync_playwright
from breadcrumb import crumb

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = crumb(browser.new_page())                            # Wrap your page — that's it

    page.goto("https://myapp.com")
    page.locator("#login-btn").click()                          # First run: fingerprint saved
    # Developer renames #login-btn → .auth-button
    page.locator("#login-btn").click()                          # Next run: healed automatically ✅
```

### pytest Plugin — Built-in Fixture

Enable the plugin with `--breadcrumb` and use the `heal_page` fixture:

```python
# test_login.py
def test_login(heal_page):
    heal_page.goto("https://myapp.com")
    heal_page.locator("#login-btn").click()     # Self-healing, zero extra syntax
    assert heal_page.locator(".welcome").is_visible()
```

```bash
pytest --breadcrumb --breadcrumb-report
# Healing summary printed at the end of the session
```

### Flaky Test Tracking

Record test history and detect instability:

```python
from breadcrumb.core.storage import FingerprintStore
from breadcrumb.flaky import TestTracker, TestAnalyzer, QuarantineManager

store = FingerprintStore()
tracker = TestTracker(store)

tracker.record_run("tests/test_login.py::test_login", "passed", duration_ms=250)
tracker.record_run("tests/test_login.py::test_login", "failed", error_type="AssertionError")

analyzer = TestAnalyzer(tracker)
print(analyzer.classify("tests/test_login.py::test_login"))   # "Intermittent"
print(f"Flip-rate: {analyzer.compute_fliprate(...):.2f}")

manager = QuarantineManager(store, analyzer)
manager.auto_update()   # auto-quarantines Flaky/Chronic, releases Stable/Intermittent
```

### Healing Report

```python
from breadcrumb.core.storage import FingerprintStore
from breadcrumb.report import ReportConsole, ReportHTML, ReportJSON

store = FingerprintStore()

print(ReportConsole().render(store, days=30))
ReportHTML().export(store, "report.html", days=30)
ReportJSON().export(store, "report.json", days=30)
```

```
Test Health Summary (last 30 days)
Total tests: 142
Stable: 118 (83.1%)
Healed: 16 (11.3%)
Flaky: 5 (3.5%)
Failing: 3 (2.1%)

Top healed locators:
  #login-btn           healed 4x  avg confidence: 0.82
  .submit-form         healed 2x  avg confidence: 0.91

Flaky tests:
  test_checkout        fliprate: 0.40  status: Flaky
  test_search          fliprate: 0.25  status: Intermittent
```

## CLI

The `breadcrumb` command provides four subcommands:

```bash
# Health report — console, HTML, or JSON output
breadcrumb report
breadcrumb report --format html --output report.html
breadcrumb report --format json --output report.json --days 7

# DB diagnostics — schema version, stale fingerprints, quarantine status
breadcrumb doctor
breadcrumb doctor --db /path/to/custom.db

# Scaffold a new project with conftest.py and a sample test
breadcrumb init --name myproject --dir ./tests

# Generate Page Object Models from a live URL (requires Playwright)
breadcrumb generate https://myapp.com
```

Install with CLI support:

```bash
pip install -e ".[cli]"
```

### AI Test Generation

Breadcrumb can crawl a URL, classify interactive elements by semantic role, and emit Page Object Model classes and pytest stubs:

```python
from breadcrumb.generate import PageCrawler, ElementClassifier, TestCodeGenerator

crawler = PageCrawler()
elements = crawler.crawl_static(html_string)          # or crawl(url, playwright_page)

classifier = ElementClassifier()
classified = classifier.classify_page(elements)

gen = TestCodeGenerator()
print(gen.generate_page_object("LoginPage", classified))
```

Output:

```python
class LoginPage:
    def __init__(self, page):
        self.page = page
        self.email_input = page.locator('[data-testid="email"]')
        self.submit_button = page.locator('button:has-text("Sign In")')

    def fill_email_input(self, value: str) -> None:
        self.email_input.fill(value)

    def click_submit_button(self) -> None:
        self.submit_button.click()
```

Optional Ollama integration generates richer test names and docstrings — but Ollama is never required. Everything works without it.

## Features

### Self-Healing Core ✅
- **Automatic Element Recovery** — When locators break, Breadcrumb finds the right element using multi-signal fingerprinting.
- **Multi-Signal Fingerprinting** — Captures tag, id, classes, text, attributes, DOM path, sibling context, and visual position.
- **Weighted Similarity Scoring** — Combines Jaccard, Levenshtein, and LCS with configurable weights.
- **Zero-Infrastructure Storage** — Local SQLite (WAL mode). No servers, no cloud, no API keys.

### Playwright + pytest Integration ✅
- **Playwright Wrapper** — `crumb(page)` wraps any Playwright `Page` transparently.
- **pytest Plugin** — `heal_page` fixture, `--breadcrumb` flag, per-session healing summary.
- **Heal Event Log** — Every heal recorded with locator, confidence score, and timestamp.

### Flaky Test Intelligence ✅
- **Execution History Tracking** — Records pass/fail, duration, healing occurrence, error type, and environment per test run.
- **Flip-Rate Analysis** — Standard and EWMA-weighted flip-rates (Apple "Modeling and ranking flaky tests" method).
- **Stability Classification** — Stable / Intermittent / Flaky / Chronic tiers based on flip-rate thresholds.
- **Auto-Quarantine** — Flaky and Chronic tests are quarantined automatically; released when they stabilise.

### Reporting ✅
- **Console Report** — Plain-text health summary with totals, top healed locators, and flaky test list.
- **HTML Dashboard** — Standalone HTML file with inline CSS — no external dependencies.
- **JSON Export** — Structured data for integration with external dashboards or CI systems.

### CLI ✅
- **`breadcrumb report`** — Generate reports in console, HTML, or JSON format.
- **`breadcrumb doctor`** — Diagnose DB health: schema version, stale fingerprints, quarantine count.
- **`breadcrumb init`** — Scaffold a new project with `conftest.py` and a sample test.
- **`breadcrumb generate`** — Generate Page Object Models from a live URL.

### AI Test Generation ✅
- **Page Crawler** — Extracts all interactive elements (buttons, inputs, links, selects, forms) from a live page or static HTML.
- **Semantic Classifier** — Classifies elements by role (login form, search, navigation, etc.) using heuristics — no LLM required.
- **Code Generator** — Emits Page Object Model classes and pytest test files.
- **Optional Ollama** — Richer test names via a local LLM when available; silent fallback otherwise.

### Developer Experience ✅
- **Full Type Coverage** — pyright + mypy on every commit.
- **Zero Config** — Sensible defaults. Override via `pyproject.toml` or CLI flags.
- **279 Tests** — 91% coverage across all modules, integration tests on real Chromium.

## Roadmap

| Phase | Focus                                                                | Status      |
|-------|----------------------------------------------------------------------|-------------|
| 1     | Fingerprint engine + SQLite storage + similarity scoring             | ✅ Complete |
| 2     | Playwright page wrapper + pytest plugin                              | ✅ Complete |
| 3     | Flaky test tracker + quarantine + reporting (console, HTML, JSON)    | ✅ Complete |
| 4     | CLI (`report`, `doctor`, `generate`, `init`) + AI test generation   | ✅ Complete |
| 5     | MCP server + documentation site (MkDocs)                            | 🔄 Next     |

## Benchmarks

Measured on an i7-class machine with Python 3.12. See [`benchmarks/`](https://github.com/FaraazSuffla/breadcrumb/tree/main/benchmarks) for reproducible scripts.

| Benchmark                         | Result       |
|-----------------------------------|--------------|
| Single-pair similarity score      | ~0.009 ms    |
| Heal over 100 candidates          | ~2 ms        |
| Heal over 1 000 candidates        | ~14 ms       |
| Fingerprint INSERT (SQLite WAL)   | ~0.29 ms/op  |
| Fingerprint SELECT by key         | ~0.006 ms/op |

Healing a typical page (30–100 interactive elements) adds **under 15 ms** per broken locator — imperceptible in a test suite.

## Installation

> **Not yet published to PyPI.** Install from source:

```bash
git clone https://github.com/FaraazSuffla/breadcrumb.git
cd breadcrumb
pip install -e ".[dev]"      # includes pytest, playwright, click, ruff, pyright, mypy
playwright install chromium
```

Breadcrumb requires **Python 3.10+**.

### Optional Extras

```bash
pip install -e ".[cli]"         # Click CLI (included in dev)
pip install -e ".[ai]"          # Ollama integration for richer AI-generated test names
pip install -e ".[docs]"        # MkDocs + Material theme for the documentation site
```

## Tech Stack

| Component        | Technology                                       |
|------------------|--------------------------------------------------|
| Language         | Python 3.10+                                     |
| Browser engine   | Playwright                                       |
| Test framework   | pytest (plugin architecture)                     |
| Similarity       | Jaccard, Levenshtein, LCS (pure Python, no deps) |
| Storage          | SQLite (stdlib, WAL mode)                        |
| CLI              | Click                                            |
| AI (optional)    | Ollama (local LLMs)                              |
| Linting          | Ruff                                             |
| Type checking    | pyright + mypy                                   |
| CI               | GitHub Actions (Python 3.10–3.13 matrix)         |
| License          | BSD-3-Clause                                     |

## Contributing

Contributions are welcome — especially during this early stage. Please read the [contributing guide](https://github.com/FaraazSuffla/breadcrumb/blob/main/CONTRIBUTING.md) first.

```bash
git clone https://github.com/FaraazSuffla/breadcrumb.git
cd breadcrumb
pip install -e ".[dev]"
playwright install chromium
pre-commit install
pytest
```

## License

BSD-3-Clause. See [LICENSE](https://github.com/FaraazSuffla/breadcrumb/blob/main/LICENSE).

## Acknowledgments

Architectural inspiration from:
- [Scrapling](https://github.com/D4Vinci/Scrapling) (BSD License) — Adaptive element tracking and smart similarity algorithms
- [Playwright](https://github.com/microsoft/playwright) (Apache-2.0) — Browser automation engine

---
<div align="center"><small>Designed & crafted with ❤️ by Faraaz Suffla</small></div><br>
