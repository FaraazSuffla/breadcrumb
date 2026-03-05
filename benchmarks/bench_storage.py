"""Benchmarks for SQLite storage read/write performance.

Measures:
- Single fingerprint write latency
- Single fingerprint read latency
- Bulk write throughput
- Healing event recording latency
- Query performance at scale

Run with:
    python benchmarks/bench_storage.py
"""

from __future__ import annotations

import statistics
import tempfile
import time
from pathlib import Path

from breadcrumb.core.fingerprint import BoundingBox, ElementFingerprint
from breadcrumb.core.storage import FingerprintStore, HealingEvent


def _make_fp(i: int = 0) -> ElementFingerprint:
    return ElementFingerprint(
        tag="button",
        text=f"button text {i}",
        attributes=frozenset({("id", f"btn-{i}"), ("class", "btn primary"), ("data-testid", f"test-{i}")}),
        dom_path=("html", "body", "div", "form", "button"),
        siblings=("input", "label", "span"),
        bbox=BoundingBox(x=float(i * 10), y=100.0, width=80.0, height=40.0),
        locator=f"#btn-{i}",
        test_id=f"test_{i % 50}",
    )


def _make_event(i: int, fp: ElementFingerprint) -> HealingEvent:
    return HealingEvent(
        test_id=fp.test_id,
        locator=fp.locator,
        confidence=0.85,
        original_fingerprint=fp.to_dict(),
        healed_fingerprint=fp.to_dict(),
        timestamp=time.time(),
    )


def bench_single_write(store: FingerprintStore, iterations: int = 200) -> None:
    times = []
    for i in range(iterations):
        fp = ElementFingerprint(
            tag="button",
            text="click me",
            attributes=frozenset({("id", f"unique-{i}")}),
            dom_path=("html", "body", "button"),
            siblings=(),
            locator=f"#unique-{i}",
            test_id="bench_write",
        )
        t0 = time.perf_counter()
        store.save_fingerprint(fp)
        times.append((time.perf_counter() - t0) * 1000)
    mean_ms = statistics.mean(times)
    print(f"  Single write (INSERT):   {mean_ms:.3f} ms avg  ({iterations} ops)")


def bench_single_read(store: FingerprintStore, iterations: int = 500) -> None:
    # Pre-populate
    fp = ElementFingerprint(
        tag="button",
        text="read target",
        attributes=frozenset({("id", "read-btn")}),
        dom_path=("html", "body", "button"),
        siblings=(),
        locator="#read-btn",
        test_id="bench_read",
    )
    store.save_fingerprint(fp)

    times = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        store.load_fingerprint("bench_read", "#read-btn")
        times.append((time.perf_counter() - t0) * 1000)
    mean_ms = statistics.mean(times)
    print(f"  Single read (SELECT):    {mean_ms:.3f} ms avg  ({iterations} ops)")


def bench_bulk_write(store: FingerprintStore, n: int) -> None:
    fps = [_make_fp(i) for i in range(n)]
    t0 = time.perf_counter()
    for fp in fps:
        store.save_fingerprint(fp)
    elapsed = (time.perf_counter() - t0) * 1000
    print(f"  Bulk write ({n:>5} fps):   {elapsed:.1f} ms total  ({elapsed / n:.3f} ms/op)")


def bench_healing_event_insert(store: FingerprintStore, n: int = 200) -> None:
    fp = _make_fp(0)
    store.save_fingerprint(fp)
    events = [_make_event(i, fp) for i in range(n)]

    t0 = time.perf_counter()
    for ev in events:
        store.record_healing(ev)
    elapsed = (time.perf_counter() - t0) * 1000
    print(f"  Healing events ({n:>4}):   {elapsed:.1f} ms total  ({elapsed / n:.3f} ms/op)")


def bench_get_all_fingerprints(store: FingerprintStore) -> None:
    count = len(store.get_all_fingerprints())
    t0 = time.perf_counter()
    store.get_all_fingerprints()
    elapsed = (time.perf_counter() - t0) * 1000
    print(f"  get_all_fingerprints ({count}): {elapsed:.2f} ms")


def bench_get_healing_events(store: FingerprintStore) -> None:
    count = len(store.get_healing_events())
    t0 = time.perf_counter()
    store.get_healing_events()
    elapsed = (time.perf_counter() - t0) * 1000
    print(f"  get_healing_events ({count:>3}): {elapsed:.2f} ms")


if __name__ == "__main__":
    print("=" * 55)
    print("Breadcrumb — Storage Benchmarks")
    print("=" * 55)

    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "bench.db"
        store = FingerprintStore(db)

        bench_single_write(store)
        bench_single_read(store)
        store.clear()

        bench_bulk_write(store, 100)
        bench_bulk_write(store, 500)
        bench_bulk_write(store, 1000)

        bench_get_all_fingerprints(store)
        bench_healing_event_insert(store, 200)
        bench_get_healing_events(store)

        store.close()

    print("=" * 55)
