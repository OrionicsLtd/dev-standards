"""Unit tests for loading and checking the routing eval files."""

import json
from pathlib import Path

import pytest

from evalcases import (
    Case,
    as_param,
    coverage_problems,
    duplicate_prompts,
    known_pair_reason,
    load_eval,
    missing_negatives,
)

SKILLS = frozenset({"alpha", "beta", "gamma"})


def _write(directory: Path, name: str, content: object) -> Path:
    path = directory / f"{name}.json"
    path.write_text(content if isinstance(content, str) else json.dumps(content))
    return path


def _eval(directory: Path, name: str, **content: object) -> Path:
    return _write(directory, name, {"prompts": [f"{name} default"], **content})


def test_load_reads_strings_objects_and_negatives(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "alpha",
        {
            "prompts": ["plain", {"prompt": "marked", "known_collision": "overlaps beta"}],
            "negatives": [
                {"prompt": "goes to beta", "winner": "beta"},
                {"prompt": "goes to gamma", "winner": "gamma", "known_collision": "why"},
            ],
            "known_pair_collisions": {"beta": "shared wording"},
        },
    )

    loaded = load_eval(path, SKILLS)

    assert loaded.skill == "alpha"
    assert loaded.prompts == (
        Case("alpha", "plain", "alpha", None),
        Case("alpha", "marked", "alpha", "overlaps beta"),
    )
    assert loaded.negatives == (
        Case("alpha", "goes to beta", "beta", None),
        Case("alpha", "goes to gamma", "gamma", "why"),
    )
    assert dict(loaded.known_pairs) == {"beta": "shared wording"}


@pytest.mark.parametrize(
    "content",
    [
        pytest.param("{not json", id="invalid-json"),
        pytest.param(["a list"], id="not-an-object"),
        pytest.param({"negatives": []}, id="missing-prompts"),
        pytest.param({"prompts": []}, id="empty-prompts"),
        pytest.param({"prompts": [""]}, id="empty-prompt"),
        pytest.param({"prompts": [3]}, id="prompt-not-a-string"),
        pytest.param({"prompts": [{"prompt": "x", "known_collision": ""}]}, id="empty-reason"),
        pytest.param({"prompts": [{"prompt": "x"}]}, id="prompt-object-without-reason"),
        pytest.param(
            {"prompts": [{"prompt": "x", "known_collision": "r", "why": "y"}]},
            id="unknown-prompt-key",
        ),
        pytest.param({"prompts": ["x"], "extra": 1}, id="unknown-key"),
        pytest.param({"prompts": ["x"], "negatives": {"prompt": "y"}}, id="negatives-not-list"),
        pytest.param({"prompts": ["x"], "negatives": [{"prompt": "y"}]}, id="missing-winner"),
        pytest.param(
            {"prompts": ["x"], "negatives": [{"prompt": "y", "winner": "ghost"}]},
            id="unknown-winner",
        ),
        pytest.param(
            {"prompts": ["x"], "negatives": [{"prompt": "y", "winner": ["beta"]}]},
            id="winner-not-a-string",
        ),
        pytest.param(
            {"prompts": ["x"], "negatives": [{"prompt": "y", "winner": "beta", "why": "z"}]},
            id="unknown-negative-key",
        ),
        pytest.param(
            {"prompts": ["x"], "negatives": [{"prompt": "y", "winner": "alpha"}]},
            id="self-winner",
        ),
        pytest.param(
            {"prompts": ["x"], "known_pair_collisions": {"ghost": "why"}}, id="unknown-pair-skill"
        ),
        pytest.param(
            {"prompts": ["x"], "known_pair_collisions": {"alpha": "why"}}, id="self-pair-skill"
        ),
        pytest.param(
            {"prompts": ["x"], "known_pair_collisions": {"beta": ""}}, id="empty-pair-reason"
        ),
    ],
)
def test_load_rejects_malformed_file(tmp_path: Path, content: object) -> None:
    path = _write(tmp_path, "alpha", content)

    with pytest.raises(ValueError, match="alpha.json"):
        load_eval(path, SKILLS)


def test_eval_coverage_names_missing_and_unknown_skills() -> None:
    problems = coverage_problems(skills={"a", "b"}, eval_names={"a", "c"})

    assert len(problems) == 2
    assert any("b" in problem and "no eval file" in problem for problem in problems)
    assert any("c" in problem and "not a skill" in problem for problem in problems)


def test_eval_coverage_accepts_matching_sets() -> None:
    assert coverage_problems(skills={"a", "b"}, eval_names={"b", "a"}) == ()


def test_duplicate_prompts_are_reported(tmp_path: Path) -> None:
    files = tuple(
        load_eval(path, SKILLS)
        for path in (
            _write(tmp_path, "alpha", {"prompts": ["across files", "within", "within"]}),
            _write(
                tmp_path,
                "beta",
                {
                    "prompts": ["across files", "prompt and negative"],
                    "negatives": [{"prompt": "prompt and negative", "winner": "gamma"}],
                },
            ),
            _write(tmp_path, "gamma", {"prompts": ["unique"]}),
        )
    )

    problems = duplicate_prompts(files)

    assert len(problems) == 3
    assert any("across files" in p and "alpha" in p and "beta" in p for p in problems)
    assert any("within" in p for p in problems)
    assert any("prompt and negative" in p for p in problems)


def test_required_negatives_are_reported_when_missing(tmp_path: Path) -> None:
    files = (
        load_eval(
            _eval(tmp_path, "alpha", negatives=[{"prompt": "to beta", "winner": "beta"}]),
            SKILLS,
        ),
        load_eval(_eval(tmp_path, "beta"), SKILLS),
    )

    problems = missing_negatives(files, required=(("alpha", "beta"), ("beta", "alpha")))

    assert len(problems) == 1
    assert "beta" in problems[0] and "alpha" in problems[0]


def test_known_pair_reason_reads_either_file(tmp_path: Path) -> None:
    files = (
        load_eval(_eval(tmp_path, "alpha", known_pair_collisions={"beta": "shared"}), SKILLS),
        load_eval(_eval(tmp_path, "beta"), SKILLS),
        load_eval(_eval(tmp_path, "gamma"), SKILLS),
    )

    assert known_pair_reason(files, "alpha", "beta") == "shared"
    assert known_pair_reason(files, "beta", "alpha") == "shared"
    assert known_pair_reason(files, "alpha", "gamma") is None


def test_known_collision_marks_case_as_strict_xfail() -> None:
    marked = as_param(Case("alpha", "p", "alpha", "r"))
    plain = as_param(Case("alpha", "p", "alpha", None))

    (mark,) = marked.marks
    assert mark.name == "xfail"
    assert mark.kwargs == {"strict": True, "reason": "r"}
    assert plain.marks == ()
    assert marked.id == "alpha: p"
