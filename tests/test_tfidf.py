"""Unit tests for the TF-IDF ranker that stands in for skill routing."""

import math

import pytest

from tfidf import collides, fit, pair_scores, rank, routes_to, tokenize

CORPUS = {"a": "alpha beta", "b": "beta gamma"}
# Two descriptions, so n = 2: "alpha" and "gamma" have df 1, "beta" has df 2.
IDF_RARE = math.log(3 / 2) + 1
NORM = math.sqrt(IDF_RARE**2 + 1)


def test_tokenize_lowercases_drops_stopwords_and_folds_plurals() -> None:
    assert tokenize("Use this WHENEVER a pyproject.toml changes") == ("pyproject", "toml", "change")
    assert tokenize("dependencies tests class bus readmes") == (
        "dependency",
        "test",
        "class",
        "bus",
        "readme",
    )


def test_tokenize_drops_plurals_of_stopwords() -> None:
    assert tokenize("It needs retries and uses its cache") == ("retry", "cache")


def test_fit_weights_match_hand_computed_idf() -> None:
    assert pair_scores(fit(CORPUS)) == (("a", "b", pytest.approx(1 / NORM**2)),)
    assert math.isclose(1 / NORM**2, 0.336097, abs_tol=1e-6)


def test_rank_ignores_unknown_words() -> None:
    ranking = rank(fit(CORPUS), "alpha zeta")

    assert ranking == (("a", pytest.approx(IDF_RARE / NORM)), ("b", 0.0))
    assert math.isclose(IDF_RARE / NORM, 0.814802, abs_tol=1e-6)


def test_rank_breaks_ties_by_name() -> None:
    ranking = rank(fit({"b": "beta gamma", "a": "alpha beta"}), "beta")

    assert ranking == (("a", pytest.approx(1 / NORM)), ("b", pytest.approx(1 / NORM)))
    assert math.isclose(1 / NORM, 0.579739, abs_tol=1e-6)


@pytest.mark.parametrize(
    ("prompt", "skill", "expected"),
    [
        ("alpha", "a", True),
        ("gamma", "b", True),
        ("alpha", "b", False),
        ("beta", "a", False),
        ("beta", "b", False),
        ("zeta", "a", False),
        ("zeta", "b", False),
    ],
)
def test_routes_to_rejects_ties_and_zero_scores(prompt: str, skill: str, expected: bool) -> None:
    assert routes_to(rank(fit(CORPUS), prompt), skill) is expected


def test_pair_scores_rate_identical_descriptions_one_and_disjoint_zero() -> None:
    scores = pair_scores(fit({"y": "lint the code", "x": "lint the code", "z": "write a spec"}))

    assert scores == (
        ("x", "y", pytest.approx(1.0)),
        ("x", "z", 0.0),
        ("y", "z", 0.0),
    )


@pytest.mark.parametrize(
    ("score", "expected"), [(0.35, True), (0.36, True), (0.3499, False), (0.0, False)]
)
def test_collides_at_and_above_the_ceiling(score: float, expected: bool) -> None:
    assert collides(score, ceiling=0.35) is expected
