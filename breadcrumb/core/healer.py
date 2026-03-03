"""Self-healing orchestrator -- ties fingerprint, similarity, and storage together.

The Healer sits between test code and the browser. When a locator resolves
normally, it fingerprints the element and saves it. When a locator fails,
it retrieves the stored fingerprint, scores all visible candidates, and
returns the best match above the confidence threshold.

This module is browser-agnostic. The Playwright-specific wrapper (Phase 2)
will call these methods with fingerprints extracted from live pages.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from breadcrumb.core.fingerprint import ElementFingerprint
from breadcrumb.core.similarity import ScoringResult, compute_similarity
from breadcrumb.core.storage import FingerprintStore, HealingEvent

logger = logging.getLogger("breadcrumb.healer")

DEFAULT_CONFIDENCE_THRESHOLD = 0.5


@dataclass
class HealResult:
    """Result of a healing attempt.

    Attributes:
        healed: True if a suitable replacement was found.
        candidate: The best-matching fingerprint, or None if healing failed.
        score: The ScoringResult of the best match, or None.
        all_scores: All candidates scored, sorted by total descending.
    """

    healed: bool
    candidate: ElementFingerprint | None
    score: ScoringResult | None
    all_scores: list[tuple[ElementFingerprint, ScoringResult]]


class Healer:
    """Self-healing engine that finds replacement elements when locators break.

    Usage::

        healer = Healer()
        healer.save(fingerprint)          # on passing run
        result = healer.heal(             # on failing run
            test_id="test_login",
            locator="#login-btn",
            candidates=[fp1, fp2, ...],
        )
    """

    def __init__(
        self,
        store: FingerprintStore | None = None,
        threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        weights: dict[str, float] | None = None,
    ) -> None:
        self._store = store or FingerprintStore()
        self._threshold = threshold
        self._weights = weights

    @property
    def store(self) -> FingerprintStore:
        """Access the underlying fingerprint store."""
        return self._store

    @property
    def threshold(self) -> float:
        """Current confidence threshold for healing."""
        return self._threshold

    def save(self, fingerprint: ElementFingerprint) -> None:
        """Save a fingerprint from a passing test run."""
        self._store.save_fingerprint(fingerprint)
        logger.debug(
            "Saved fingerprint: test=%s locator=%s tag=%s",
            fingerprint.test_id,
            fingerprint.locator,
            fingerprint.tag,
        )

    def heal(
        self,
        test_id: str,
        locator: str,
        candidates: list[ElementFingerprint],
    ) -> HealResult:
        """Attempt to find a replacement element for a broken locator.

        Steps:
            1. Load the stored fingerprint for (test_id, locator).
            2. Score each candidate against the stored fingerprint.
            3. Return the best match if above threshold, otherwise fail.
            4. Log the healing event to the database.
        """
        stored = self._store.load_fingerprint(test_id, locator)

        if stored is None:
            logger.info(
                "No stored fingerprint for test=%s locator=%s",
                test_id,
                locator,
            )
            return HealResult(
                healed=False,
                candidate=None,
                score=None,
                all_scores=[],
            )

        if not candidates:
            logger.info(
                "No candidates provided for healing test=%s locator=%s",
                test_id,
                locator,
            )
            return HealResult(
                healed=False,
                candidate=None,
                score=None,
                all_scores=[],
            )

        # Score all candidates
        scored: list[tuple[ElementFingerprint, ScoringResult]] = []
        for candidate in candidates:
            result = compute_similarity(stored, candidate, self._weights)
            scored.append((candidate, result))

        # Sort by total score descending
        scored.sort(key=lambda x: x[1].total, reverse=True)

        best_candidate, best_score = scored[0]

        if best_score.total < self._threshold:
            logger.info(
                "Best candidate scored %.4f, below threshold %.4f",
                best_score.total,
                self._threshold,
            )
            return HealResult(
                healed=False,
                candidate=best_candidate,
                score=best_score,
                all_scores=scored,
            )

        # Healing succeeded -- record the event
        logger.info(
            "Healed test=%s locator=%s -> tag=%s confidence=%.4f",
            test_id,
            locator,
            best_candidate.tag,
            best_score.total,
        )

        event = HealingEvent(
            test_id=test_id,
            locator=locator,
            confidence=best_score.total,
            original_fingerprint=stored.to_dict(),
            healed_fingerprint=best_candidate.to_dict(),
            timestamp=time.time(),
        )
        self._store.record_healing(event)

        # Update stored fingerprint to the healed element
        updated = ElementFingerprint.from_dict(
            {**best_candidate.to_dict(), "locator": locator, "test_id": test_id},
        )
        self._store.save_fingerprint(updated)

        return HealResult(
            healed=True,
            candidate=best_candidate,
            score=best_score,
            all_scores=scored,
        )
