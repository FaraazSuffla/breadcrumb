# Concepts

## How Self-Healing Works

Breadcrumb operates in two phases:

### Phase 1 — Learning (first run)

When a test interacts with an element via a locator (e.g. `page.locator("#login-btn").click()`),
Breadcrumb captures a **fingerprint** — a rich identity snapshot of that element — and stores
it in a local SQLite database (`.breadcrumb.db`).

### Phase 2 — Healing (subsequent runs)

When the same locator fails (because the app changed), Breadcrumb:

1. Queries all visible elements on the page.
2. Scores each candidate against the stored fingerprint using six signals.
3. If the best candidate exceeds the **confidence threshold** (default 0.5), the interaction
   proceeds with the healed element and a heal event is logged.
4. If no candidate meets the threshold, the test **fails normally** — Breadcrumb never silently
   picks the wrong element.

---

## Element Fingerprint

A fingerprint captures eight signals about a DOM element at the time of interaction:

| Signal | Description |
|---|---|
| `tag` | HTML tag name (e.g. `button`, `input`, `a`) |
| `text` | Visible text content, normalised (stripped, lowercased) |
| `attributes` | All HTML attributes as (name, value) pairs |
| `dom_path` | Ancestor tag names from `<html>` to this element |
| `siblings` | Tag names of immediate sibling elements |
| `bbox` | Bounding box (x, y, width, height) at fingerprint time |
| `locator` | Original locator string |
| `test_id` | The test that created this fingerprint |

Fingerprints are **immutable frozen dataclasses** — hashable, cacheable, and safe to store.

---

## Similarity Scoring

When healing, Breadcrumb scores each candidate element against the stored fingerprint
using six independent signals:

| Signal | Algorithm | Weight |
|---|---|---|
| Tag match | Exact match | High |
| ID match | Exact match | High |
| Text similarity | Levenshtein distance | Medium |
| Class/attribute overlap | Jaccard similarity | Medium |
| DOM path match | Longest Common Subsequence (LCS) | Medium |
| Sibling match | LCS | Low |
| Position distance | Euclidean distance (normalised) | Low |

All algorithms are **pure Python** with zero external dependencies.

The final score is a weighted combination of all signals, in the range [0.0, 1.0].

---

## Confidence Threshold

The confidence threshold controls how certain Breadcrumb must be before healing.

- **Default:** `0.5`
- **Range:** `0.0` – `1.0`
- **Below threshold:** the locator failure propagates normally (test fails)
- **At or above threshold:** the interaction is redirected to the best candidate

```python
page = crumb(raw_page, test_id="my_test", threshold=0.7)
```

Raising the threshold reduces false-positive heals at the cost of more failures.
Lowering it heals more aggressively — useful when fingerprints are sparse.

---

## Storage

Breadcrumb stores all data in a single SQLite file (`.breadcrumb.db`) in the
current working directory. No cloud, no API keys, no external services.

Key design properties:

- **WAL mode** — fast concurrent reads during parallel test runs
- **Auto-created** on first use
- **Schema versioning** — internal migration from v1 to v2 when Phase 3 tables are needed
- **Append-only heal log** — every heal event is recorded; never overwritten

---

## Flakiness Classification

After several test runs, Breadcrumb classifies each test by its flip-rate
(the fraction of consecutive runs that change outcome):

| Classification | Flip-rate |
|---|---|
| **Stable** | 0.0 — never changes |
| **Intermittent** | 0.0 – 0.2 — rarely changes |
| **Flaky** | 0.2 – 0.5 — often changes |
| **Chronic** | > 0.5 — mostly unstable |

Flaky and Chronic tests are **auto-quarantined** — they still run but failures
don't block CI. Tests are automatically released from quarantine when they
recover to Stable or Intermittent.

An **EWMA (exponentially weighted moving average)** variant gives more weight
to recent flip behaviour, useful for detecting newly flaky tests.
