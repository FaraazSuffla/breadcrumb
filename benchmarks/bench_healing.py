"""Benchmarks for the full heal() cycle.

Measures:
- End-to-end heal() time: load fingerprint + score N candidates + return result
- Effect of candidate pool size on heal time
- Threshold boundary performance

Run with:
    python benchmarks/bench_healing.py
"""

from __future__ import annotations

import statistics
import tempfile
import time
from pathlib import Path

from breadcrumb.core.fingerprint import BoundingBox, ElementFingerprint
from breadcrumb.core.healer import Healer
from breadcrumb.core.storage import FingerprintStore


def _make_fp(
    tag: str = "button",
    text: str = "submit",
    i: int = 0,
    locator: str = "#login-btn",
    test_id: str = "bench",
) -> ElementFingerprint:
    return ElementFingerprint(
        tag=tag,
        text=text,
        attributes=frozenset({
            ("id", f"element-{i}"),
            ("class", "btn primary"),
            ("data-testid", f"elem-{i}"),
        }),
        dom_path=("html", "body", "div", "form", tag),
        siblings=("input", "label"),
        bbox=BoundingBox(x=float(i % 800), y=float(i * 5 % 600), width=80.0, height=40.0),
        locator=locator,
        test_id=test_id,
    )


def _make_candidate_pool(n: int, match_index: int = 0) -> list[ElementFingerprint]:
    """N candidates where index match_index is the correct match (button/submit)."""
    candidates = []
    for i in range(n):
        if i == match_index:
            candidates.append(_make_fp(tag="button", text="submit", i=i))
        else:
            candidates.append(_make_fp(
                tag="div" if i % 3 == 0 else "span",
                text=f"noise element {i}",
                i=i,
                locator=f"#noise-{i}",
            ))
    return candidates


def bench_heal_cycle(n_candidates: int, iterations: int = 100) -> None:
    """Measure full heal() cycle with a given candidate pool size."""
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "bench.db"
        store = FingerprintStore(db)
        healer = Healer(store=store, threshold=0.4)

        stored = _make_fp(locator="#login-btn", test_id="bench")
        healer.save(stored)

        candidates = _make_candidate_pool(n_candidates, match_index=0)

        times = []
        for _ in range(iterations):
            t0 = time.perf_counter()
            result = healer.heal(
                test_id="bench",
                locator="#login-btn",
                candidates=candidates,
            )
            times.append((time.perf_counter() - t0) * 1000)

        assert result.healed, f"Healing failed with {n_candidates} candidates"

        mean_ms = statistics.mean(times)
        p95_ms = sorted(times)[int(0.95 * len(times))]
        print(
            f"  Heal cycle ({n_candidates:>5} candidates): "
            f"{mean_ms:.3f} ms avg  |  {p95_ms:.3f} ms p95  ({iterations} iters)"
        )
        store.close()


def bench_no_stored_fingerprint(n_candidates: int = 500) -> None:
    """Heal call when no fingerprint exists (fast path — should exit early)."""
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "bench.db"
        store = FingerprintStore(db)
        healer = Healer(store=store, threshold=0.5)
        candidates = _make_candidate_pool(n_candidates)

        times = []
        for _ in range(200):
            t0 = time.perf_counter()
            healer.heal(test_id="missing", locator="#ghost", candidates=candidates)
            times.append((time.perf_counter() - t0) * 1000)

        mean_ms = statistics.mean(times)
        print(f"  No stored fingerprint (early exit): {mean_ms:.4f} ms avg  (200 iters)")
        store.close()


def bench_empty_candidates() -> None:
    """Heal call with empty candidate list (fast path)."""
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "bench.db"
        store = FingerprintStore(db)
        healer = Healer(store=store, threshold=0.5)
        stored = _make_fp(locator="#btn", test_id="bench2")
        healer.save(stored)

        times = []
        for _ in range(500):
            t0 = time.perf_counter()
            healer.heal(test_id="bench2", locator="#btn", candidates=[])
            times.append((time.perf_counter() - t0) * 1000)

        mean_ms = statistics.mean(times)
        print(f"  Empty candidates (early exit):      {mean_ms:.4f} ms avg  (500 iters)")
        store.close()


if __name__ == "__main__":
    print("=" * 65)
    print("Breadcrumb — Full Heal Cycle Benchmarks")
    print("=" * 65)
    bench_empty_candidates()
    bench_no_stored_fingerprint()
    bench_heal_cycle(50)
    bench_heal_cycle(100)
    bench_heal_cycle(250)
    bench_heal_cycle(500)
    bench_heal_cycle(1000)
    bench_heal_cycle(2000)
    print("=" * 65)
