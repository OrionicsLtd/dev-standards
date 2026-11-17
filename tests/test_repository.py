"""Routing evals and lint run against this repository's own skills, agents and eval files."""

from collections.abc import Callable
from itertools import combinations
from pathlib import Path

import pytest

from evalcases import (
    Case,
    EvalFile,
    as_param,
    coverage_problems,
    duplicate_prompts,
    known_pair_reason,
    load_evals,
    missing_negatives,
)
from repo_files import (
    length_problems,
    load_skills,
    name_problems,
    reference_problems,
    reviewer_problems,
)
from tfidf import collides, fit, pair_scores, rank, routes_to

ROOT = Path(__file__).resolve().parents[1]
DESCRIPTION_LIMIT = 1024
COLLISION_CEILING = 0.35
ALLOWED_NAMES = frozenset({"osv-scanner", "exclude-newer"})
NEARBY_PAIRS = (
    ("dependency-safety", "security-advisories"),
    ("testing", "spec-writing"),
    ("docs-maintenance", "spec-writing"),
)

SKILLS = load_skills(ROOT)
NAMES = frozenset(skill.name for skill in SKILLS)
INDEX = fit({skill.name: skill.description for skill in SKILLS})
EVALS: tuple[EvalFile, ...] = load_evals(ROOT / "evals", NAMES)


def _required_negatives() -> tuple[tuple[str, str], ...]:
    both_ways = tuple(pair for a, b in NEARBY_PAIRS for pair in ((a, b), (b, a)))
    standards = tuple(("coding-standards", name) for name in sorted(NAMES - {"coding-standards"}))
    return both_ways + standards


def _pair_param(a: str, b: str, score: float) -> object:
    reason = known_pair_reason(EVALS, a, b)
    marks = pytest.mark.xfail(strict=True, reason=reason) if reason else ()
    return pytest.param(a, b, score, id=f"{a}/{b}", marks=marks)


def _route_failure(case: Case) -> str:
    top = ", ".join(f"{name} {score:.3f}" for name, score in rank(INDEX, case.prompt)[:3])
    return f"{case.prompt!r} should route to {case.expected}; top three: {top}"


@pytest.mark.parametrize("case", [as_param(case) for file in EVALS for case in file.prompts])
def test_prompt_routes_to_its_skill(case: Case) -> None:
    assert routes_to(rank(INDEX, case.prompt), case.expected), _route_failure(case)


@pytest.mark.parametrize("case", [as_param(case) for file in EVALS for case in file.negatives])
def test_negative_routes_to_its_winner(case: Case) -> None:
    assert routes_to(rank(INDEX, case.prompt), case.expected), _route_failure(case)


@pytest.mark.parametrize(("a", "b", "score"), [_pair_param(*pair) for pair in pair_scores(INDEX)])
def test_descriptions_stay_apart(a: str, b: str, score: float) -> None:
    assert not collides(score, COLLISION_CEILING), f"{a} and {b} descriptions score {score:.3f}"


def test_every_pair_of_skills_is_scored() -> None:
    scored = {(a, b) for a, b, _ in pair_scores(INDEX)}

    assert scored == set(combinations(sorted(NAMES), 2))


def test_every_skill_has_an_eval_file() -> None:
    eval_names = {path.stem for path in (ROOT / "evals").glob("*.json")}

    assert coverage_problems(NAMES, eval_names) == ()


def test_eval_prompts_are_unique() -> None:
    assert duplicate_prompts(EVALS) == ()


def test_required_collisions_have_negatives() -> None:
    assert missing_negatives(EVALS, _required_negatives()) == ()


CHECKS: dict[str, Callable[[], tuple[str, ...]]] = {
    "names": lambda: name_problems(ROOT),
    "lengths": lambda: length_problems(SKILLS, DESCRIPTION_LIMIT),
    "references": lambda: reference_problems(ROOT, ALLOWED_NAMES),
}


@pytest.mark.parametrize("check", CHECKS)
def test_repository_is_clean(check: str) -> None:
    assert CHECKS[check]() == ()


def test_reviewer_name_agrees() -> None:
    assert reviewer_problems(ROOT) == ()
