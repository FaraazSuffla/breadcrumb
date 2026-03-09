# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0a2] - 2026-03-09

### Added

**MCP server (Phase 5)**
- `breadcrumb.mcp.server` — Model Context Protocol server exposing seven breadcrumb tools
  to Claude Code, Claude Desktop, and other MCP-compatible AI assistants
- `breadcrumb mcp` CLI command starts the server over stdio transport
- Tools: `breadcrumb_stats`, `breadcrumb_report`, `breadcrumb_doctor`,
  `breadcrumb_healing_events`, `breadcrumb_flaky_tests`, `breadcrumb_generate_tests`,
  `breadcrumb_list_fingerprints`
- New optional extra: `mcp = ["mcp>=1.0"]`

**MkDocs documentation site (Phase 5)**
- Full documentation site built with MkDocs + Material theme + mkdocstrings
- Pages: index, getting-started, concepts, CLI reference, MCP server, architecture, API reference, changelog
- GitHub Actions workflow (`docs.yml`) deploys to GitHub Pages on every push to `main`

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
