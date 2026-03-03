"""Core module -- fingerprinting, similarity scoring, healing, and storage."""

from breadcrumb.core.fingerprint import BoundingBox, ElementFingerprint
from breadcrumb.core.healer import HealResult, Healer
from breadcrumb.core.similarity import ScoringResult, compute_similarity
from breadcrumb.core.storage import FingerprintStore, HealingEvent

__all__ = [
    "BoundingBox",
    "compute_similarity",
    "ElementFingerprint",
    "FingerprintStore",
    "HealingEvent",
    "HealResult",
    "Healer",
    "ScoringResult",
]
