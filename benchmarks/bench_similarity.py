"""Benchmarks for the similarity scoring algorithms.

Measures time to:
- Score a single candidate pair
- Score N candidates against one stored fingerprint (batch heal scenario)

Run with:
    python benchmarks/bench_similarity.py
"""

from __future__ import annotations

import statistics
import time
from typing import Callable

from breadcrumb.core.fingerprint import BoundingBox, ElementFingerprint
from breadcrumb.core.similarity import compute_similarity


def _make_fp(
    tag: str = "button",
    text: str = "submit",
    n_attrs: int = 5,
    path_depth: int = 6,
    n_siblings: int = 4,
    with_bbox: bool = True,
    locator: str = "#btn",
    test_id: str = "bench_test",
) -> ElementFingerprint:
    attrs = frozenset(
        (f"attr-{i}", f"value-{i}") for i in range(n_attrs)
    )
    dom_path = tuple(f"tag-{i}" for i in range(path_depth))
    siblings = tuple(f"sibling-{i}" for i in range(n_siblings))
    bbox = BoundingBox(x=100.0, y=200.0, width=80.0, height=40.0) if with_bbox else None
    return ElementFingerprint(
        tag=tag,
        text=text,
        attributes=attrs,
        dom_path=dom_path,
        siblings=siblings,
        bbox=bbox,
        locator=locator,
        test_id=test_id,
    )


def _timeit(fn: Callable[[], None], iterations: int = 1000) -> float:
    """Return mean time in milliseconds over N iterations."""
    times = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        fn()
        times.append((time.perf_counter() - t0) * 1000)
    return statistics.mean(times)


def bench_single_pair() -> None:
    stored = _make_fp()
    candidate = _make_fp(text="log in", n_attrs=4)

    mean_ms = _timeit(lambda: compute_similarity(stored, candidate))
    print(f"  Single pair score:          {mean_ms:.4f} ms  (1 000 iterations)")


def bench_batch_candidates(n: int) -> None:
    stored = _make_fp()
    candidates = [_make_fp(text=f"item {i}", n_attrs=i % 8) for i in range(n)]

    def _score_all() -> None:
        scores = [compute_similarity(stored, c) for c in candidates]
        scores.sort(key=lambda s: s.total, reverse=True)

    mean_ms = _timeit(_score_all, iterations=200)
    print(f"  Batch score ({n:>5} candidates): {mean_ms:.3f} ms  (200 iterations)")


def bench_no_bbox() -> None:
    stored = _make_fp(with_bbox=False)
    candidate = _make_fp(with_bbox=False)

    mean_ms = _timeit(lambda: compute_similarity(stored, candidate))
    print(f"  No-bbox pair score:         {mean_ms:.4f} ms  (1 000 iterations)")


def bench_identical_fingerprints() -> None:
    fp = _make_fp()
    mean_ms = _timeit(lambda: compute_similarity(fp, fp))
    print(f"  Identical pair (max score): {mean_ms:.4f} ms  (1 000 iterations)")


def bench_empty_fingerprints() -> None:
    empty = ElementFingerprint(
        tag="div", text="", attributes=frozenset(), dom_path=(), siblings=()
    )
    mean_ms = _timeit(lambda: compute_similarity(empty, empty))
    print(f"  Empty pair score:           {mean_ms:.4f} ms  (1 000 iterations)")


if __name__ == "__main__":
    print("=" * 55)
    print("Breadcrumb — Similarity Scoring Benchmarks")
    print("=" * 55)
    bench_identical_fingerprints()
    bench_empty_fingerprints()
    bench_no_bbox()
    bench_single_pair()
    bench_batch_candidates(100)
    bench_batch_candidates(500)
    bench_batch_candidates(1000)
    bench_batch_candidates(5000)
    print("=" * 55)
