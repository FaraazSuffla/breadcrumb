# Architecture

## Four Layers

Breadcrumb is built on four well-separated layers, each with a clear responsibility:

```
┌─────────────────────────────────────────────────────────────────┐
│  Test Code (pytest / raw Playwright)                            │
├─────────────────────────────────────────────────────────────────┤
│  Layer 4 — Reporting & Intelligence                             │
│  TestTracker · TestAnalyzer · QuarantineManager                 │
│  ReportConsole · ReportHTML · ReportJSON                        │
│  PageCrawler · ElementClassifier · TestCodeGenerator            │
│  MCP Server (7 tools)                                           │
├─────────────────────────────────────────────────────────────────┤
│  Layer 3 — Playwright Wrapper                                   │
│  HealablePage · HealableLocator · crumb() · heal_page fixture   │
├─────────────────────────────────────────────────────────────────┤
│  Layer 2 — Similarity Engine                                    │
│  Healer · SimilarityScorer                                      │
│  Jaccard · Levenshtein · LCS · Euclidean                        │
├─────────────────────────────────────────────────────────────────┤
│  Layer 1 — Fingerprint + Storage                                │
│  ElementFingerprint · BoundingBox · FingerprintStore (SQLite)   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Package Structure

```
breadcrumb/
├── __init__.py           # Public API: crumb, HealablePage, HealableLocator
├── core/
│   ├── fingerprint.py    # ElementFingerprint, BoundingBox (frozen dataclasses)
│   ├── similarity.py     # Six scoring algorithms (pure Python)
│   ├── healer.py         # Scoring pipeline + candidate selection
│   └── storage.py        # FingerprintStore (SQLite, WAL mode)
├── playwright/
│   ├── extractor.py      # JS-based DOM extraction
│   └── page_wrapper.py   # HealablePage, HealableLocator
├── plugins/
│   └── pytest_plugin.py  # heal_page fixture + --breadcrumb flags
├── flaky/
│   ├── tracker.py        # TestTracker, schema migration v1→v2
│   ├── analyzer.py       # TestAnalyzer: flip-rate, EWMA, classification
│   └── quarantine.py     # QuarantineManager: auto-quarantine/release
├── report/
│   ├── console.py        # ReportConsole
│   ├── html.py           # ReportHTML (interactive dashboard)
│   └── json.py           # ReportJSON
├── generate/
│   ├── crawler.py        # PageCrawler (static + Playwright)
│   ├── classifier.py     # ElementClassifier (heuristic roles)
│   └── codegen.py        # TestCodeGenerator (POM + pytest)
├── mcp/
│   ├── __init__.py
│   └── server.py         # MCP server with 7 tools
└── cli/
    └── main.py           # Click CLI: report/doctor/generate/init/mcp
```

---

## Data Schema

### Schema v1 (core)

```sql
CREATE TABLE schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE fingerprints (
    test_id          TEXT NOT NULL,
    locator          TEXT NOT NULL,
    fingerprint_json TEXT NOT NULL,   -- JSON-serialised ElementFingerprint
    updated_at       REAL NOT NULL,   -- Unix timestamp
    PRIMARY KEY (test_id, locator)
);

CREATE TABLE healing_events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    test_id       TEXT NOT NULL,
    locator       TEXT NOT NULL,
    confidence    REAL NOT NULL,
    original_json TEXT NOT NULL,   -- fingerprint before heal
    healed_json   TEXT NOT NULL,   -- fingerprint after heal
    timestamp     REAL NOT NULL
);
```

### Schema v2 additions (flaky tracking)

```sql
CREATE TABLE test_runs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    test_id          TEXT NOT NULL,
    status           TEXT NOT NULL,   -- passed/failed/error/skipped
    duration_ms      REAL,
    healing_occurred INTEGER NOT NULL DEFAULT 0,
    error_type       TEXT,
    environment      TEXT,
    timestamp        REAL NOT NULL
);

CREATE TABLE quarantine (
    test_id           TEXT PRIMARY KEY,
    reason            TEXT NOT NULL,
    quarantined_at    REAL NOT NULL,
    auto_unquarantine INTEGER NOT NULL DEFAULT 1
);
```

Migration from v1 → v2 is idempotent and handled automatically by `migrate_schema()`.

---

## Similarity Scoring Detail

```
Final score = weighted_mean(
    tag_match          × 0.25,
    id_match           × 0.25,
    text_similarity    × 0.20,   # Levenshtein
    class_similarity   × 0.10,   # Jaccard
    attr_similarity    × 0.05,   # Jaccard
    path_similarity    × 0.10,   # LCS
    sibling_similarity × 0.03,   # LCS
    position_score     × 0.02,   # 1 − norm_euclidean_distance
)
```

All algorithms are implemented in `breadcrumb/core/similarity.py` with **zero
external dependencies** — the only imports are from the Python standard library.

---

## Performance Benchmarks

Measured on Windows 11, Python 3.12, i7 processor.

| Operation | Result |
|---|---|
| Single-pair similarity score | ~0.009 ms |
| Heal over 100 candidates | ~2 ms |
| Heal over 1,000 candidates | ~14 ms |
| Fingerprint INSERT (SQLite WAL) | ~0.29 ms/op |
| Fingerprint SELECT by key | ~0.006 ms/op |

Healing a typical page (30–100 elements) adds **under 15 ms** per broken locator.

---

## Design Principles

1. **Type safety is non-negotiable** — pyright strict + mypy strict on every commit
2. **No external runtime dependencies** — similarity algorithms are pure Python
3. **Never silently heal** — confidence threshold must be exceeded or the test fails normally
4. **Local-only by design** — no cloud calls, no API keys required for core functionality
5. **Append-only heal log** — every heal event is preserved for auditing
6. **Idempotent migrations** — schema changes are safe to run multiple times
