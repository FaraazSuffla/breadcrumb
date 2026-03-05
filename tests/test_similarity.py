"""Tests for breadcrumb.core.similarity."""

from __future__ import annotations

import pytest

from breadcrumb.core.fingerprint import BoundingBox, ElementFingerprint
from breadcrumb.core.similarity import (
    DEFAULT_WEIGHTS,
    compute_similarity,
    dom_path_similarity,
    jaccard_similarity,
    lcs_length,
    levenshtein_distance,
    position_similarity,
    sibling_similarity,
    tag_similarity,
    text_similarity,
)


# ---------------------------------------------------------------------------
# Tag similarity
# ---------------------------------------------------------------------------


class TestTagSimilarity:
    def test_exact_match(self) -> None:
        assert tag_similarity("button", "button") == 1.0

    def test_mismatch(self) -> None:
        assert tag_similarity("button", "div") == 0.0

    def test_empty(self) -> None:
        assert tag_similarity("", "") == 1.0


# ---------------------------------------------------------------------------
# Levenshtein distance
# ---------------------------------------------------------------------------


class TestLevenshteinDistance:
    def test_identical(self) -> None:
        assert levenshtein_distance("hello", "hello") == 0

    def test_empty_strings(self) -> None:
        assert levenshtein_distance("", "") == 0

    def test_one_empty(self) -> None:
        assert levenshtein_distance("abc", "") == 3
        assert levenshtein_distance("", "abc") == 3

    def test_substitution(self) -> None:
        assert levenshtein_distance("cat", "car") == 1

    def test_insertion(self) -> None:
        assert levenshtein_distance("cat", "cats") == 1

    def test_deletion(self) -> None:
        assert levenshtein_distance("cats", "cat") == 1

    def test_completely_different(self) -> None:
        assert levenshtein_distance("abc", "xyz") == 3

    def test_sign_in_vs_log_in(self) -> None:
        dist = levenshtein_distance("sign in", "log in")
        assert dist == 3


# ---------------------------------------------------------------------------
# Text similarity
# ---------------------------------------------------------------------------


class TestTextSimilarity:
    def test_identical(self) -> None:
        assert text_similarity("submit", "submit") == 1.0

    def test_both_empty(self) -> None:
        assert text_similarity("", "") == 1.0

    def test_one_empty(self) -> None:
        assert text_similarity("hello", "") == 0.0
        assert text_similarity("", "hello") == 0.0

    def test_similar(self) -> None:
        score = text_similarity("sign in", "log in")
        assert 0.3 < score < 0.8

    def test_very_different(self) -> None:
        score = text_similarity("submit", "cancel")
        assert score < 0.5

    def test_close_match(self) -> None:
        score = text_similarity("submit", "Submit")
        assert score > 0.7


# ---------------------------------------------------------------------------
# Jaccard similarity
# ---------------------------------------------------------------------------


class TestJaccardSimilarity:
    def test_identical(self) -> None:
        s = frozenset({("id", "btn"), ("class", "primary")})
        assert jaccard_similarity(s, s) == 1.0

    def test_disjoint(self) -> None:
        a = frozenset({("id", "a")})
        b = frozenset({("id", "b")})
        assert jaccard_similarity(a, b) == 0.0

    def test_overlap(self) -> None:
        a = frozenset({("id", "btn"), ("class", "primary"), ("type", "submit")})
        b = frozenset({("id", "btn"), ("class", "secondary")})
        assert jaccard_similarity(a, b) == 1 / 4

    def test_both_empty(self) -> None:
        assert jaccard_similarity(frozenset(), frozenset()) == 0.0

    def test_one_empty(self) -> None:
        s = frozenset({("id", "btn")})
        assert jaccard_similarity(s, frozenset()) == 0.0


# ---------------------------------------------------------------------------
# LCS length
# ---------------------------------------------------------------------------


class TestLCSLength:
    def test_identical(self) -> None:
        assert lcs_length(["a", "b", "c"], ["a", "b", "c"]) == 3

    def test_empty(self) -> None:
        assert lcs_length([], []) == 0
        assert lcs_length(["a"], []) == 0

    def test_no_common(self) -> None:
        assert lcs_length(["a", "b"], ["c", "d"]) == 0

    def test_subsequence(self) -> None:
        assert lcs_length(["a", "b", "c", "d"], ["b", "d"]) == 2

    def test_dom_path_example(self) -> None:
        path_a = ["html", "body", "div", "form", "button"]
        path_b = ["html", "body", "main", "div", "form", "button"]
        assert lcs_length(path_a, path_b) == 5


# ---------------------------------------------------------------------------
# DOM path similarity
# ---------------------------------------------------------------------------


class TestDomPathSimilarity:
    def test_identical(self) -> None:
        path = ("html", "body", "div", "button")
        assert dom_path_similarity(path, path) == 1.0

    def test_both_empty(self) -> None:
        assert dom_path_similarity((), ()) == 0.0

    def test_partial_match(self) -> None:
        a = ("html", "body", "div", "form", "button")
        b = ("html", "body", "main", "form", "button")
        score = dom_path_similarity(a, b)
        assert 0.5 < score < 1.0


# ---------------------------------------------------------------------------
# Sibling similarity
# ---------------------------------------------------------------------------


class TestSiblingSimilarity:
    def test_identical(self) -> None:
        sibs = ("input", "label", "button")
        assert sibling_similarity(sibs, sibs) == 1.0

    def test_both_empty(self) -> None:
        assert sibling_similarity((), ()) == 0.0

    def test_partial(self) -> None:
        a = ("input", "label", "button")
        b = ("input", "span", "button")
        score = sibling_similarity(a, b)
        assert 0.5 < score < 1.0


# ---------------------------------------------------------------------------
# Position similarity
# ---------------------------------------------------------------------------


class TestPositionSimilarity:
    def test_same_position(self) -> None:
        bbox = BoundingBox(x=100, y=200, width=50, height=30)
        assert position_similarity(bbox, bbox) == 1.0

    def test_none_bbox(self) -> None:
        bbox = BoundingBox(x=100, y=200, width=50, height=30)
        assert position_similarity(None, bbox) == 0.0
        assert position_similarity(bbox, None) == 0.0
        assert position_similarity(None, None) == 0.0

    def test_far_apart(self) -> None:
        a = BoundingBox(x=0, y=0, width=10, height=10)
        b = BoundingBox(x=1000, y=1000, width=10, height=10)
        assert position_similarity(a, b) == 0.0

    def test_moderate_distance(self) -> None:
        a = BoundingBox(x=100, y=100, width=50, height=30)
        b = BoundingBox(x=200, y=100, width=50, height=30)
        score = position_similarity(a, b)
        assert 0.5 < score < 1.0


# ---------------------------------------------------------------------------
# Composite scoring
# ---------------------------------------------------------------------------


class TestComputeSimilarity:
    def _make_fp(self, **overrides: object) -> ElementFingerprint:
        defaults: dict[str, object] = {
            "tag": "button",
            "text": "submit",
            "attributes": frozenset({("id", "btn"), ("class", "primary")}),
            "dom_path": ("html", "body", "form", "button"),
            "siblings": ("input", "label"),
            "bbox": BoundingBox(x=100, y=200, width=80, height=40),
        }
        defaults.update(overrides)
        return ElementFingerprint(**defaults)  # type: ignore[arg-type]

    def test_identical_elements(self) -> None:
        fp = self._make_fp()
        result = compute_similarity(fp, fp)
        assert result.total == pytest.approx(1.0, abs=0.01)
        assert all(
            v == pytest.approx(1.0, abs=0.01) for v in result.breakdown.values()
        )

    def test_completely_different(self) -> None:
        a = self._make_fp()
        b = self._make_fp(
            tag="div",
            text="cancel",
            attributes=frozenset({("role", "alert")}),
            dom_path=("html", "body", "aside", "div"),
            siblings=("span",),
            bbox=BoundingBox(x=800, y=800, width=200, height=100),
        )
        result = compute_similarity(a, b)
        assert result.total < 0.4

    def test_id_rename_scenario(self) -> None:
        """Blueprint scenario: developer renames #login-btn to .auth-button."""
        stored = self._make_fp(
            tag="button",
            text="sign in",
            attributes=frozenset({("id", "login-btn"), ("class", "btn primary")}),
        )
        candidate = self._make_fp(
            tag="button",
            text="sign in",
            attributes=frozenset({("class", "auth-button btn")}),
        )
        result = compute_similarity(stored, candidate)
        assert result.total > 0.7

    def test_custom_weights(self) -> None:
        fp = self._make_fp()
        result = compute_similarity(
            fp,
            fp,
            weights={
                "tag": 1.0,
                "text": 0.0,
                "attributes": 0.0,
                "dom_path": 0.0,
                "siblings": 0.0,
                "position": 0.0,
            },
        )
        assert result.total == pytest.approx(1.0)

    def test_weights_in_result(self) -> None:
        fp = self._make_fp()
        custom = {"tag": 0.5, "text": 0.5}
        result = compute_similarity(fp, fp, weights=custom)
        assert result.weights["tag"] == 0.5
        assert result.weights["text"] == 0.5

    def test_default_weights_sum_to_one(self) -> None:
        total = sum(DEFAULT_WEIGHTS.values())
        assert total == pytest.approx(1.0)

    def test_scoring_result_repr(self) -> None:
        fp = self._make_fp()
        result = compute_similarity(fp, fp)
        r = repr(result)
        assert "ScoringResult" in r
        assert "total=" in r


# ---------------------------------------------------------------------------
# Coverage gaps: jaccard with both-empty-non-empty union=0, dom/sibling empty
# ---------------------------------------------------------------------------


class TestCoverageGaps:
    def test_jaccard_both_empty_returns_zero(self) -> None:
        # Both empty sets — union is 0, should return 0.0 (line 89)
        result = jaccard_similarity(frozenset(), frozenset())
        assert result == 0.0

    def test_dom_path_similarity_both_empty_returns_zero(self) -> None:
        # Both empty tuples — max_len == 0 branch (line 125)
        result = dom_path_similarity((), ())
        assert result == 0.0

    def test_sibling_similarity_both_empty_returns_zero(self) -> None:
        # Both empty tuples — max_len == 0 branch (line 137)
        result = sibling_similarity((), ())
        assert result == 0.0
