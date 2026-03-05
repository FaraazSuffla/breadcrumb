"""Core module -- fingerprinting, similarity scoring, healing, and storage."""

from breadcrumb.core.fingerprint import BoundingBox, ElementFingerprint
from breadcrumb.core.healer import Healer, HealResult
from breadcrumb.core.similarity import ScoringResult, compute_similarity
from breadcrumb.core.storage import FingerprintStore, HealingEvent

__all__ = [
    "BoundingBox",
    "ElementFingerprint",
    "FingerprintStore",
    "HealResult",
    "Healer",
    "HealingEvent",
    "ScoringResult",
    "compute_similarity",
]
