"""Flaky test analyzer.

Computes flip-rate scores and classifies tests by stability level using
techniques from the Apple "Modeling and ranking flaky tests" paper.
"""

from __future__ import annotations

import itertools

from breadcrumb.flaky.tracker import TestTracker


class TestAnalyzer:
    """Analyses test run history to detect and rank flaky tests.

    Classifications:
        Stable      — fliprate == 0.0
        Intermittent — 0.0 < fliprate <= 0.2
        Flaky        — 0.2 < fliprate <= 0.5
        Chronic      — fliprate > 0.5

    Usage::

        analyzer = TestAnalyzer(tracker)
        fliprate = analyzer.compute_fliprate("test_login")
        classification = analyzer.classify("test_login")
    """

    def __init__(self, tracker: TestTracker) -> None:
        self._tracker = tracker

    def compute_fliprate(self, test_id: str, window: int = 10) -> float:
        """Standard flip-rate: fraction of consecutive outcome changes.

        For n runs, there are n-1 consecutive pairs. Each pair where the
        outcome changes counts as a flip. Returns flips / (n-1).

        Returns 0.0 if fewer than 2 runs are available.
        """
        runs = self._tracker.get_runs(test_id, limit=window)
        if len(runs) < 2:
            return 0.0

        statuses = [r["status"] for r in runs]
        flips = sum(1 for a, b in itertools.pairwise(statuses) if a != b)
        return flips / (len(statuses) - 1)

    def compute_ewma_fliprate(
        self,
        test_id: str,
        alpha: float = 0.3,
        window: int = 20,
    ) -> float:
        """EWMA-weighted flip-rate (more recent flips weighted more heavily).

        Implements the exponentially weighted moving average approach from
        Apple's "Modeling and ranking flaky tests" paper. Alpha controls
        how much weight is given to recent vs older flips (higher = more
        recent-biased).

        Returns 0.0 if fewer than 2 runs are available.
        """
        runs = self._tracker.get_runs(test_id, limit=window)
        if len(runs) < 2:
            return 0.0

        statuses = [r["status"] for r in runs]
        # Pairs ordered oldest-to-newest (runs are DESC, so reverse)
        statuses = list(reversed(statuses))
        pairs = [a != b for a, b in itertools.pairwise(statuses)]

        # EWMA over the flip indicators
        ewma = float(pairs[0])
        for flip in pairs[1:]:
            ewma = alpha * float(flip) + (1 - alpha) * ewma
        return ewma

    def classify(self, test_id: str) -> str:
        """Classify a test by its flip-rate into a stability tier.

        Returns one of: 'Stable', 'Intermittent', 'Flaky', 'Chronic'.
        """
        rate = self.compute_fliprate(test_id)
        if rate == 0.0:
            return "Stable"
        if rate <= 0.2:
            return "Intermittent"
        if rate <= 0.5:
            return "Flaky"
        return "Chronic"

    def get_all_classifications(self) -> dict[str, str]:
        """Return {test_id: classification} for all known tests."""
        test_ids = self._tracker.get_all_test_ids()
        return {tid: self.classify(tid) for tid in test_ids}
