# CLAUDE.md — Breadcrumb

## What This Project Is

Self-healing Playwright test library. When a locator breaks because a developer renamed a class or ID, Breadcrumb fingerprints every element touched during a test run and uses multi-signal similarity scoring to automatically find the right element — without cloud services, API keys, or external infrastructure.

**One-line wrapper. Zero config. Local-only.**

---

## Current Status: Pre-Alpha

| Phase | Focus | Status |
|---|---|---|
| 1 | Fingerprint engine + SQLite storage + similarity scoring | ✅ Complete |
| 2 | Playwright wrapper + pytest plugin + basic healing | ✅ Complete |
| 3 | Flaky test tracker + quarantine + HTML/JSON/console reporting | ✅ Complete |
| 4 | CLI (`report`, `doctor`, `generate`, `init`) + AI test generation | ✅ Complete |
| 5 | MCP server + MkDocs documentation | ⬜ Planned |

**Not yet published to PyPI.** Install from source only.

---

## Architecture

### Four Layers

1. **Fingerprint Engine** — Captures tag, id, classes, text content, attributes, DOM path, sibling context, and visual position on every element interaction.

2. **Similarity Scoring** — When a locator fails, scores all visible elements against the stored fingerprint using:
   - Exact match → tag, id
   - Levenshtein distance → text content
   - Jaccard similarity → classes, attributes
   - Longest Common Subsequence → DOM path, siblings
   - Euclidean distance → position
   - Configurable threshold (default: 0.5). Below threshold = normal test failure. Never silently picks a wrong element.

3. **Storage** — Local SQLite (`.breadcrumb.db`, WAL mode). Auto-created on first run. Schema migrations handled internally.

4. **Reporting & Intelligence** — Heal event log with locator, confidence score, timestamp. Powers flakiness reports and quarantine system. Console, HTML, and JSON output formats.

5. **AI Test Generation** *(Phase 4)* — Page crawler (static + Playwright), semantic element classifier, and codegen producing POM + pytest files. Optional Ollama integration.

---

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.10+ |
| Browser engine | Playwright |
| Test framework | pytest (plugin architecture) |
| Similarity algorithms | Jaccard, Levenshtein, LCS (pure Python, zero deps) |
| Storage | SQLite (stdlib, WAL mode) |
| AI (optional, Phase 4+) | Ollama (local LLMs only) |
| Linting | Ruff |
| Type checking | pyright (strict) + mypy (strict) |
| CI | GitHub Actions |
| License | BSD-3-Clause |

---

## Project Structure

```
breadcrumb/
├── .github/workflows/     # CI pipeline
├── benchmarks/            # Reproducible perf benchmarks
├── breadcrumb/            # Core library source
├── tests/                 # Test suite
├── pyproject.toml         # Project config, deps, tool settings
├── CHANGELOG.md
├── CONTRIBUTING.md
└── CLAUDE.md              # This file
```

---

## Usage Patterns

### Basic Wrapper
```python
from breadcrumb import crumb

page = crumb(browser.new_page())   # wrap — that's it
page.locator("#login-btn").click() # fingerprinted on first run, healed on subsequent runs
```

### pytest Plugin
```python
def test_login(heal_page):
    heal_page.goto("https://myapp.com")
    heal_page.locator("#login-btn").click()  # zero extra syntax
```
Run with: `pytest --breadcrumb --breadcrumb-report`

---

## Performance Benchmarks

| Benchmark | Result |
|---|---|
| Single-pair similarity score | ~0.009 ms |
| Heal over 100 candidates | ~2 ms |
| Heal over 1,000 candidates | ~14 ms |
| Fingerprint INSERT (SQLite WAL) | ~0.29 ms/op |
| Fingerprint SELECT by key | ~0.006 ms/op |

Healing a typical page (30–100 elements) adds **under 15 ms** per broken locator.

---

## Dev Setup

```bash
git clone https://github.com/FaraazSuffla/breadcrumb.git
cd breadcrumb
pip install -e ".[dev]"
playwright install chromium
pre-commit install
pytest
```

### Optional installs
```bash
pip install -e ".[playwright]"  # Playwright only
pip install -e ".[ai]"          # Ollama for Phase 5
pip install -e ".[docs]"        # MkDocs + Material theme
```

---

## Conventions

- **Type safety is non-negotiable** — pyright strict + mypy strict on every commit
- **No external runtime dependencies** — similarity algorithms are pure Python
- **Never silently heal** — confidence threshold must be exceeded or the test fails normally
- **Local-only by design** — no cloud calls, no API keys required for core functionality
- Ruff for linting/formatting

---

## What's Next (Priority Order)

1. **Phase 5** — MCP server + MkDocs documentation site
2. **PyPI publish** — After Phase 5 is stable

---

## Architectural Inspiration

- [Scrapling](https://github.com/D4Vinci/Scrapling) (BSD) — Adaptive element tracking, smart similarity algorithms
- [Playwright](https://github.com/microsoft/playwright) (Apache-2.0) — Browser automation engine
