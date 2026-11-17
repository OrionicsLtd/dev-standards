"""Load the routing eval files in `evals/` and check them as a set."""

import json
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

FILE_KEYS = frozenset({"prompts", "negatives", "known_pair_collisions"})
PROMPT_KEYS = frozenset({"prompt", "known_collision"})
NEGATIVE_KEYS = frozenset({"prompt", "winner", "known_collision"})


@dataclass(frozen=True)
class Case:
    """One prompt from `source`'s eval file and the skill it must route to."""

    source: str
    prompt: str
    expected: str
    known_collision: str | None


@dataclass(frozen=True)
class EvalFile:
    """A skill's eval file: its prompts, its negatives and the overlaps it accepts."""

    skill: str
    prompts: tuple[Case, ...]
    negatives: tuple[Case, ...]
    known_pairs: Mapping[str, str]


def _text(value: Any, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{what} must be a non-empty string")
    return value


def _object(value: Any, allowed: frozenset[str], required: frozenset[str], what: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{what} must be an object")
    if unknown := set(value) - allowed:
        raise ValueError(f"{what} has unknown keys {sorted(unknown)}")
    if missing := required - set(value):
        raise ValueError(f"{what} is missing {sorted(missing)}")
    return value


def _other_skill(name: Any, skill: str, skills: frozenset[str], what: str) -> str:
    if not isinstance(name, str) or name not in skills or name == skill:
        raise ValueError(f"{what} {name!r} must name another skill")
    return name


def _reason(entry: dict, what: str) -> str | None:
    if "known_collision" not in entry:
        return None
    return _text(entry["known_collision"], f"{what} known_collision")


def _prompt(entry: Any, skill: str) -> Case:
    if isinstance(entry, str):
        return Case(skill, _text(entry, "prompt"), skill, None)
    entry = _object(entry, PROMPT_KEYS, PROMPT_KEYS, "prompt entry")
    return Case(skill, _text(entry["prompt"], "prompt"), skill, _reason(entry, "prompt"))


def _negative(entry: Any, skill: str, skills: frozenset[str]) -> Case:
    entry = _object(entry, NEGATIVE_KEYS, frozenset({"prompt", "winner"}), "negative")
    winner = _other_skill(entry["winner"], skill, skills, "winner")
    return Case(
        skill, _text(entry["prompt"], "negative prompt"), winner, _reason(entry, "negative")
    )


def _list(value: Any, what: str) -> list:
    if not isinstance(value, list):
        raise ValueError(f"{what} must be a list")
    return value


def _parse(raw: Any, skill: str, skills: frozenset[str]) -> EvalFile:
    raw = _object(raw, FILE_KEYS, frozenset({"prompts"}), "the file")
    prompts = tuple(_prompt(entry, skill) for entry in _list(raw["prompts"], "prompts"))
    if not prompts:
        raise ValueError("prompts must not be empty")
    negatives = _list(raw.get("negatives", []), "negatives")
    pairs = raw.get("known_pair_collisions", {})
    if not isinstance(pairs, dict):
        raise ValueError("known_pair_collisions must be an object")
    return EvalFile(
        skill,
        prompts,
        tuple(_negative(entry, skill, skills) for entry in negatives),
        {
            _other_skill(other, skill, skills, "known pair"): _text(reason, "pair reason")
            for other, reason in pairs.items()
        },
    )


def load_eval(path: Path, skills: frozenset[str]) -> EvalFile:
    """Read and validate one eval file; any problem raises ValueError naming the file."""
    try:
        return _parse(json.loads(path.read_text()), path.stem, skills)
    except ValueError as error:
        raise ValueError(f"{path.name}: {error}") from error


def load_evals(directory: Path, skills: frozenset[str]) -> tuple[EvalFile, ...]:
    """Every `*.json` eval file in `directory`, in name order."""
    return tuple(load_eval(path, skills) for path in sorted(directory.glob("*.json")))


def coverage_problems(skills: Iterable[str], eval_names: Iterable[str]) -> tuple[str, ...]:
    """Skills with no eval file, and eval files named after no skill."""
    skills, eval_names = set(skills), set(eval_names)
    missing = (f"{name}: no eval file in evals/" for name in sorted(skills - eval_names))
    unknown = (f"evals/{name}.json: {name} is not a skill" for name in sorted(eval_names - skills))
    return (*missing, *unknown)


def duplicate_prompts(files: Iterable[EvalFile]) -> tuple[str, ...]:
    """Prompts that appear more than once among all prompts and negatives."""
    sources: defaultdict[str, list[str]] = defaultdict(list)
    for file in files:
        for case in (*file.prompts, *file.negatives):
            sources[case.prompt].append(case.source)
    return tuple(
        f"{prompt!r} appears {len(names)} times, in {', '.join(names)}"
        for prompt, names in sources.items()
        if len(names) > 1
    )


def missing_negatives(
    files: Iterable[EvalFile], required: Iterable[tuple[str, str]]
) -> tuple[str, ...]:
    """Required (skill, winner) pairs with no negative in that skill's eval file."""
    present = {(case.source, case.expected) for file in files for case in file.negatives}
    return tuple(
        f"evals/{skill}.json needs a negative that {winner} wins"
        for skill, winner in required
        if (skill, winner) not in present
    )


def known_pair_reason(files: Iterable[EvalFile], a: str, b: str) -> str | None:
    """The reason either skill's eval file gives for accepting the pair's overlap."""
    reasons = {
        (file.skill, other): why for file in files for other, why in file.known_pairs.items()
    }
    return reasons.get((a, b)) or reasons.get((b, a))


def as_param(case: Case) -> Any:
    """A pytest parameter for `case`, a strict expected failure when it is a known collision."""
    marks = (
        pytest.mark.xfail(strict=True, reason=case.known_collision) if case.known_collision else ()
    )
    return pytest.param(case, id=f"{case.source}: {case.prompt}", marks=marks)
