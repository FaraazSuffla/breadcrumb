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
    <a href="#planned-features"><strong>Features</strong></a>
    &middot;
    <a href="#roadmap"><strong>Roadmap</strong></a>
    &middot;
    <a href="#installation"><strong>Installation</strong></a>
    &middot;
    <a href="#contributing"><strong>Contributing</strong></a>
</p>

> **⚠️ Pre-Alpha — Under Active Development**
>
> Breadcrumb is not yet functional. This README describes the intended design and API. Star/watch the repo to follow progress. Contributions welcome.

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
  attributes: {data-testid: auth}
  xpath:      /html/body/div[2]/form/button[1]
  css_path:   body > div:nth-child(2) > form > button
  siblings:   [input.email, input.password]
  position:   {x: 450, y: 320}
```
Each signal carries a different weight. An `id` match is strong evidence; a positional match alone is weak. The combination is what makes healing reliable.

### Layer 2 — Similarity Scoring
When a locator fails, Breadcrumb scans all visible elements and scores each one against the stored fingerprint:

| Signal      | Algorithm                    | Weight | Why                                    |
|-------------|------------------------------|--------|----------------------------------------|
| Tag name    | Exact match                  | High   | A button rarely becomes a div          |
| ID          | Exact match                  | High   | Most reliable when present             |
| Text        | Levenshtein distance         | High   | "Sign In" → "Log In" is still a match |
| Classes     | Jaccard similarity           | Medium | Classes shuffle but overlap            |
| Attributes  | Jaccard similarity           | Medium | data-testid often survives refactors   |
| XPath       | Longest Common Subsequence   | Low    | Structural hint, not a guarantee       |
| Siblings    | Structural similarity        | Low    | Nearby elements provide context        |
| Position    | Euclidean distance           | Low    | Layout shifts happen often             |

The element with the highest composite score above a configurable threshold (default: 0.75) is selected as the healed match. Below the threshold, the test fails normally — Breadcrumb never silently picks a wrong element.

### Layer 3 — Storage
Fingerprints live in a local SQLite database (`.breadcrumb.db`), created automatically on first run. Zero servers, zero config. Schema migrations are handled internally so the DB format can evolve across versions without breaking your data.

### Layer 4 — Reporting & Intelligence
Every heal event is logged: what locator broke, what element was selected, confidence score, and timestamp. This data powers flakiness reports, confidence trend analysis, and an optional quarantine system that sidelines chronically unstable tests.

## Planned API Preview

> **These code examples show the intended API. None of this is implemented yet.**

### Basic Usage — Wrap and Forget
```python
from playwright.sync_api import sync_playwright
from breadcrumb import crumb

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = crumb(browser.new_page())                           # Wrap your page — that's it

    page.goto("https://myapp.com")
    page.locator("#login-btn").click()                          # First run: fingerprint saved
    # Developer renames #login-btn → .auth-button
    page.locator("#login-btn").click()                          # Next run: healed automatically ✅
```

### pytest Integration
```python
# conftest.py
import pytest
from breadcrumb import crumb

@pytest.fixture
def page(page):
    return crumb(page)

# test_login.py — writes exactly like normal Playwright tests
def test_login(page):
    page.goto("https://myapp.com")
    page.locator("#login-btn").click()                          # Self-healing, zero extra syntax
    assert page.locator(".welcome").is_visible()
```

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

report.export_html("healing_report.html")
report.export_json("healing_data.json")
```

### CLI
```bash
breadcrumb init                          # Initialize project config
breadcrumb report                        # Print healing summary
breadcrumb report --html report.html     # Export HTML dashboard
breadcrumb doctor                        # Diagnose DB health and stale fingerprints
breadcrumb generate https://myapp.com    # AI-generate test skeletons (requires Ollama)
```

## Planned Features

### Self-Healing Core
- 🔄 **Automatic Element Recovery** — When locators break, Breadcrumb finds the right element using multi-signal fingerprinting.
- 🧬 **Multi-Signal Fingerprinting** — Captures tag, id, classes, text, attributes, XPath, CSS path, sibling context, and visual position.
- 📊 **Weighted Similarity Scoring** — Combines Jaccard, Levenshtein, and LCS with configurable weights.
- 🗄️ **Zero-Infrastructure Storage** — Local SQLite. No servers, no cloud, no API keys.

### Flaky Test Intelligence
- 📈 **Failure Tracking** — Every heal recorded with confidence scores and DOM context.
- 🏥 **Quarantine Mode** — Auto-quarantine chronically flaky tests, unquarantine when stable.
- 📋 **Trend Analysis** — Healing frequency, confidence drift, and element stability over time.

### AI-Powered Test Generation (Optional)
- 🤖 **Local LLM via Ollama** — AI-assisted test generation running entirely on your machine.
- 🕸️ **Page Crawling** — Discover interactive elements and generate test skeletons.
- 🧪 **Smart Assertions** — AI suggests assertions based on page structure.

### Developer Experience
- 🧩 **pytest Plugin** — One-line fixture wrapper, every test becomes self-healing.
- 💻 **CLI** — `init`, `report`, `doctor`, `generate` commands.
- 📊 **HTML Dashboard** — Visual report of heals, confidence, and flakiness.
- 📘 **Full Type Coverage** — pyright strict + mypy strict on every commit.
- 🔋 **Zero Config** — Sensible defaults. Override via `breadcrumb.toml` or `pyproject.toml`.

## Roadmap

| Phase | Focus                    | Status         |
|-------|--------------------------|----------------|
| 1     | Fingerprint engine + SQLite storage + similarity scoring | 🔜 Up next |
| 2     | Playwright page wrapper + pytest plugin + basic healing | ⬜ Planned |
| 3     | Flaky test tracker + quarantine + reporting (console, HTML, JSON) | ⬜ Planned |
| 4     | CLI (`init`, `report`, `doctor`) + configuration system | ⬜ Planned |
| 5     | AI test generation via Ollama + page crawler | ⬜ Planned |

## Benchmark Strategy

Benchmarks will be published once Phase 1 is complete. The planned benchmark suite will measure:

- **Healing speed** — Time to scan N candidate elements and find the best match
- **Healing accuracy** — Recovery rate across synthetic DOM mutation types (ID rename, class change, element relocation, parent restructure, multi-signal changes)
- **Overhead** — Added latency per test interaction vs raw Playwright
- **Storage** — DB size growth over test suite lifetime

All benchmarks will be reproducible via scripts in [`benchmarks/`](https://github.com/FaraazSuffla/breadcrumb/tree/main/benchmarks).

## Installation

> **Not yet published to PyPI.** For now, install from source:

```bash
git clone https://github.com/FaraazSuffla/breadcrumb.git
cd breadcrumb
pip install -e "."
playwright install chromium
```

Breadcrumb requires **Python 3.10+**.

### Optional Dependencies

```bash
pip install -e ".[ai]"       # Ollama integration for AI test generation
pip install -e ".[dev]"      # pytest, ruff, pyright, mypy, pre-commit
pip install -e ".[docs]"     # MkDocs + Material theme
```

## Tech Stack

| Component        | Technology                                       |
|------------------|--------------------------------------------------|
| Language         | Python 3.10+                                     |
| Browser engine   | Playwright                                       |
| Test framework   | pytest (plugin architecture)                     |
| Similarity       | Jaccard, Levenshtein, LCS (pure Python, no deps) |
| Storage          | SQLite (stdlib, WAL mode)                        |
| AI (optional)    | Ollama (local LLMs)                              |
| Linting          | Ruff                                             |
| Type checking    | pyright (strict) + mypy (strict)                 |
| CI               | GitHub Actions                                   |
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
