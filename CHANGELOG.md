# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- MCP server for IDE/AI assistant integration (Phase 5)
- MkDocs documentation site

## [0.1.0a1] - 2026-03-08

First pre-alpha release. All core functionality is complete and tested.

### Added

**Fingerprint engine (Phase 1)**
- Element fingerprinting capturing tag, id, classes, text content, attributes, DOM path, sibling context, and visual position
- Multi-signal similarity scoring: Jaccard (classes/attributes), Levenshtein (text), LCS (DOM path/siblings), Euclidean (position)
- Local SQLite storage in WAL mode (`.breadcrumb.db`), auto-created on first run with internal schema migrations
- Configurable confidence threshold (default 0.5) — below threshold tests fail normally, never silent mis-heal

**Playwright wrapper (Phase 2)**
- `HealablePage` and `HealableLocator` wrappers for the Playwright sync API
- `crumb()` one-line entry point: `page = crumb(browser.new_page(), test_id="...")`
- pytest plugin with `heal_page` fixture and `--breadcrumb` / `--breadcrumb-report` flags
- Heal event log: locator, confidence score, and timestamp recorded per interaction

**Flaky test tracking and reporting (Phase 3)**
- `TestTracker` — records pass/fail runs per test; EWMA flip-rate analyzer classifies tests as Stable / Intermittent / Flaky / Chronic
- `QuarantineManager` — auto-quarantines tests exceeding the flakiness threshold, auto-unquarantines on recovery
- Console, HTML, and JSON report renderers (`breadcrumb report`)

**CLI and AI generation (Phase 4)**
- `breadcrumb report` — healing summary in console, HTML, or JSON format
- `breadcrumb doctor` — database health check, stale fingerprint detection
- `breadcrumb init` — scaffold a new test project with conftest and sample test
- `breadcrumb generate <url>` — crawl a page, classify interactive elements, and emit Page Object Model + pytest skeleton; optional Ollama integration for richer generation

**Packaging**
- Project scaffolding: pyproject.toml, BSD-3-Clause license, GitHub Actions CI, CONTRIBUTING.md
- `py.typed` marker (PEP 561) — package is recognized as typed by pyright and mypy
