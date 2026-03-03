"""Similarity scoring algorithms for comparing element fingerprints.

Implements the weighted multi-signal scoring system from the blueprint:
    - Tag match:          exact comparison           (weight: 0.15)
    - Text similarity:    Levenshtein fuzzy ratio    (weight: 0.25)
    - Attribute overlap:  Jaccard similarity         (weight: 0.25)
    - DOM path distance:  Longest Common Subsequence (weight: 0.15)
    - Sibling similarity: Context window comparison  (weight: 0.15)
    - Position proximity: Euclidean distance (bbox)  (weight: 0.05)

All algorithms are pure Python with zero external dependencies.
Each function returns a float in [0.0, 1.0] where 1.0 = perfect match.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from breadcrumb.core.fingerprint import BoundingBox, ElementFingerprint


# ---------------------------------------------------------------------------
# Individual similarity functions
# ---------------------------------------------------------------------------


def tag_similarity(a: str, b: str) -> float:
    """Exact tag name match. Returns 1.0 if equal, 0.0 otherwise."""
    return 1.0 if a == b else 0.0


def levenshtein_distance(s: str, t: str) -> int:
    """Compute Levenshtein (edit) distance between two strings.

    Uses classic DP with O(min(m,n)) space.
    """
    if len(s) < len(t):
        return levenshtein_distance(t, s)

    if len(t) == 0:
        return len(s)

    previous_row = list(range(len(t) + 1))
    for i, c1 in enumerate(s):
        current_row = [i + 1]
        for j, c2 in enumerate(t):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (0 if c1 == c2 else 1)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def text_similarity(a: str, b: str) -> float:
    """Fuzzy text similarity using Levenshtein ratio.

    Returns [0.0, 1.0]. Two empty strings = 1.0, one empty = 0.0.
    Equivalent to fuzz.ratio() without external dependencies.
    """
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0

    max_len = max(len(a), len(b))
    dist = levenshtein_distance(a, b)
    return 1.0 - (dist / max_len)


def jaccard_similarity(
    set_a: frozenset[tuple[str, str]], set_b: frozenset[tuple[str, str]]
) -> float:
    """Jaccard similarity coefficient: J(A, B) = |A n B| / |A u B|.

    Used for comparing attribute sets. Returns 0.0 when both sets are empty.
    """
    if not set_a and not set_b:
        return 0.0

    intersection = len(set_a & set_b)
    union = len(set_a | set_b)

    if union == 0:
        return 0.0

    return intersection / union


def lcs_length(a: Sequence[str], b: Sequence[str]) -> int:
    """Length of the Longest Common Subsequence of two string sequences.

    Standard DP with O(min(m,n)) space.
    """
    if len(a) < len(b):
        a, b = b, a

    if len(b) == 0:
        return 0

    previous = [0] * (len(b) + 1)
    for item_a in a:
        current = [0] * (len(b) + 1)
        for j, item_b in enumerate(b):
            if item_a == item_b:
                current[j + 1] = previous[j] + 1
            else:
                current[j + 1] = max(current[j], previous[j + 1])
        previous = current

    return previous[-1]


def dom_path_similarity(a: tuple[str, ...], b: tuple[str, ...]) -> float:
    """Structural similarity of two DOM paths using LCS ratio."""
    if not a and not b:
        return 0.0

    max_len = max(len(a), len(b))
    if max_len == 0:
        return 0.0

    return lcs_length(a, b) / max_len


def sibling_similarity(a: tuple[str, ...], b: tuple[str, ...]) -> float:
    """Context window similarity of sibling tags using LCS ratio."""
    if not a and not b:
        return 0.0

    max_len = max(len(a), len(b))
    if max_len == 0:
        return 0.0

    return lcs_length(a, b) / max_len


def position_similarity(
    a: BoundingBox | None,
    b: BoundingBox | None,
    max_distance: float = 500.0,
) -> float:
    """Proximity score from Euclidean distance between bbox centers.

    Linear decay from 1.0 (same position) to 0.0 (max_distance apart).
    Returns 0.0 if either bbox is None.
    """
    if a is None or b is None:
        return 0.0

    cx_a, cy_a = a.center
    cx_b, cy_b = b.center
    distance = math.sqrt((cx_a - cx_b) ** 2 + (cy_a - cy_b) ** 2)

    return max(0.0, 1.0 - distance / max_distance)


# ---------------------------------------------------------------------------
# Composite scoring
# ---------------------------------------------------------------------------

# Default weights from the blueprint (Page 4)
DEFAULT_WEIGHTS: dict[str, float] = {
    "tag": 0.15,
    "text": 0.25,
    "attributes": 0.25,
    "dom_path": 0.15,
    "siblings": 0.15,
    "position": 0.05,
}


@dataclass
class ScoringResult:
    """Detailed result of a similarity comparison.

    Attributes:
        total: Weighted composite score in [0.0, 1.0].
        breakdown: Individual signal scores before weighting.
        weights: Weights used for this scoring.
    """

    total: float
    breakdown: dict[str, float]
    weights: dict[str, float]

    def __repr__(self) -> str:
        parts = [f"{k}={v:.3f}" for k, v in sorted(self.breakdown.items())]
        return f"ScoringResult(total={self.total:.4f}, {', '.join(parts)})"


def compute_similarity(
    stored: ElementFingerprint,
    candidate: ElementFingerprint,
    weights: dict[str, float] | None = None,
) -> ScoringResult:
    """Score a candidate element against a stored fingerprint.

    This is the core function from the blueprint pseudocode (Page 4).
    Each signal is scored independently, then combined with configurable weights.

    Args:
        stored: The fingerprint saved during a passing test run.
        candidate: A fingerprint captured from a current DOM element.
        weights: Override default signal weights.

    Returns:
        ScoringResult with composite score and per-signal breakdown.
    """
    w = dict(DEFAULT_WEIGHTS)
    if weights is not None:
        w.update(weights)

    breakdown: dict[str, float] = {
        "tag": tag_similarity(stored.tag, candidate.tag),
        "text": text_similarity(stored.text, candidate.text),
        "attributes": jaccard_similarity(stored.attributes, candidate.attributes),
        "dom_path": dom_path_similarity(stored.dom_path, candidate.dom_path),
        "siblings": sibling_similarity(stored.siblings, candidate.siblings),
        "position": position_similarity(stored.bbox, candidate.bbox),
    }

    total = sum(breakdown[k] * w[k] for k in breakdown)

    return ScoringResult(total=total, breakdown=breakdown, weights=w)
