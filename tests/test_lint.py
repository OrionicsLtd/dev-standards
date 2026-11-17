"""Unit tests for the repository lint checks, run on small repositories in a temp dir."""

import json
from pathlib import Path

import pytest

from repo_files import (
    Doc,
    length_problems,
    load_skills,
    name_problems,
    parse_frontmatter,
    reference_problems,
    reviewer_problems,
)

GATE = 'REVIEWER = "{name}"\n\n\ndef unrelated() -> str:\n    return "other"\n'
DEVGATE_STOP = 'python3 -I "$HOME/.claude/hooks/run_devgate.py" subagent-stop'


def _put(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _doc(name: str, description: str = "Does a thing.") -> str:
    return f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n"


def _settings(*entries: tuple[str, str]) -> str:
    stops = [
        {"matcher": matcher, "hooks": [{"type": "command", "command": command}]}
        for matcher, command in entries
    ]
    return json.dumps({"hooks": {"SubagentStop": stops}})


def _reviewer_repo(
    root: Path, *, gate: str, agent: str, entries: tuple[tuple[str, str], ...]
) -> Path:
    _put(root, "hooks/devgate/gate.py", GATE.format(name=gate))
    _put(root, f"agents/{agent}.md", _doc(agent))
    _put(root, "settings.example.json", _settings(*entries))
    return root


def test_parse_frontmatter_reads_folded_and_plain_values() -> None:
    text = (
        "---\nname: testing\ndescription: >-\n  Write and organise tests.\n"
        "  Use whenever writing tests.\ntools: Read, Grep\n---\n\n# Testing\n"
    )

    assert parse_frontmatter(text) == {
        "name": "testing",
        "description": "Write and organise tests. Use whenever writing tests.",
        "tools": "Read, Grep",
    }


def test_parse_frontmatter_returns_none_without_frontmatter() -> None:
    assert parse_frontmatter("# Just a heading\n") is None
    assert parse_frontmatter("---\nname: unterminated\n") is None


def test_load_skills_keys_by_directory_and_skips_broken_files(tmp_path: Path) -> None:
    _put(tmp_path, "skills/alpha/SKILL.md", _doc("alpha", "Alpha things."))
    _put(tmp_path, "skills/broken/SKILL.md", "no frontmatter\n")
    (tmp_path / "skills/empty").mkdir()

    assert load_skills(tmp_path) == (
        Doc("alpha", tmp_path / "skills/alpha/SKILL.md", "Alpha things."),
    )


def test_name_checks_report_mismatch_and_missing_frontmatter(tmp_path: Path) -> None:
    _put(tmp_path, "skills/good/SKILL.md", _doc("good"))
    _put(tmp_path, "skills/x/SKILL.md", _doc("y"))
    (tmp_path / "skills/no-file").mkdir()
    _put(tmp_path, "skills/bare/SKILL.md", "# No frontmatter\n")
    _put(tmp_path, "skills/blank/SKILL.md", "---\nname: blank\n---\n")
    _put(tmp_path, "agents/a.md", _doc("b"))
    _put(tmp_path, "agents/fine.md", _doc("fine"))

    problems = name_problems(tmp_path)

    assert len(problems) == 5
    for fragment in ("skills/x", "skills/no-file", "skills/bare", "skills/blank", "agents/a.md"):
        assert any(fragment in problem for problem in problems), fragment


def test_long_descriptions_are_reported(tmp_path: Path) -> None:
    fits = Doc("fits", tmp_path / "fits.md", "x" * 1024)
    over = Doc("over", tmp_path / "over.md", "x" * 1025)

    problems = length_problems((fits, over), limit=1024)

    assert len(problems) == 1
    assert "over" in problems[0] and "1025" in problems[0]


def test_dead_references_are_reported(tmp_path: Path) -> None:
    _put(tmp_path, "skills/real-skill/SKILL.md", _doc("real-skill"))
    _put(tmp_path, "agents/real-agent.md", _doc("real-agent"))
    _put(
        tmp_path,
        "README.md",
        "See `real-skill` and `real-agent`, run `osv-scanner`, read `testing`.\n"
        "Link to skills/real-skill/SKILL.md and agents/real-agent.md.\n"
        "Placeholders: skills/<name>/ and agents/<name>.md.\n"
        "Gone: `ghost-skill`.\n",
    )
    _put(tmp_path, "CLAUDE.md", "Follow skills/ghost/SKILL.md.\n")
    _put(tmp_path, "skills/real-skill/notes/extra.md", "Ask agents/ghost.md.\n")
    _put(tmp_path, "TODO.md", "Out of scope: `another-ghost`.\n")

    problems = reference_problems(tmp_path, allowed=frozenset({"osv-scanner"}))

    assert sorted(problems) == sorted(
        (
            "README.md:4: `ghost-skill` is not a skill, agent or allowed name",
            "CLAUDE.md:1: skills/ghost/ is not a skill directory",
            "skills/real-skill/notes/extra.md:1: agents/ghost.md is not an agent file",
        )
    )


def test_reviewer_name_agrees_in_a_consistent_repo(tmp_path: Path) -> None:
    root = _reviewer_repo(
        tmp_path, gate="rev", agent="rev", entries=(("rev", DEVGATE_STOP), ("x", "echo hi"))
    )

    assert reviewer_problems(root) == ()


@pytest.mark.parametrize(
    ("gate", "agent", "entries", "fragment"),
    [
        pytest.param("rev", "other", (("rev", DEVGATE_STOP),), "agents/rev.md", id="no-agent"),
        pytest.param("rev", "rev", (("other", DEVGATE_STOP),), "other", id="matcher-misses"),
        pytest.param("rev", "rev", (("re", DEVGATE_STOP),), "re", id="matcher-is-a-prefix"),
        pytest.param("rev", "rev", (("rev", "echo hi"),), "subagent-stop", id="no-devgate-entry"),
        pytest.param("rev", "rev", (("rev[", DEVGATE_STOP),), "rev[", id="invalid-matcher"),
    ],
)
def test_reviewer_name_mismatch_is_reported(
    tmp_path: Path,
    gate: str,
    agent: str,
    entries: tuple[tuple[str, str], ...],
    fragment: str,
) -> None:
    root = _reviewer_repo(tmp_path, gate=gate, agent=agent, entries=entries)

    problems = reviewer_problems(root)

    assert len(problems) == 1
    assert fragment in problems[0]


def test_reviewer_matcher_alternation_is_accepted(tmp_path: Path) -> None:
    root = _reviewer_repo(tmp_path, gate="rev", agent="rev", entries=(("rev|other", DEVGATE_STOP),))

    assert reviewer_problems(root) == ()


def test_reviewer_agent_name_must_match_gate(tmp_path: Path) -> None:
    root = _reviewer_repo(tmp_path, gate="rev", agent="rev", entries=(("rev", DEVGATE_STOP),))
    _put(root, "agents/rev.md", _doc("renamed"))

    problems = reviewer_problems(root)

    assert len(problems) == 1
    assert "renamed" in problems[0]


def test_reviewer_missing_from_gate_is_reported(tmp_path: Path) -> None:
    root = _reviewer_repo(tmp_path, gate="rev", agent="rev", entries=(("rev", DEVGATE_STOP),))
    _put(root, "hooks/devgate/gate.py", "OTHER = 1\n")

    problems = reviewer_problems(root)

    assert len(problems) == 1
    assert "REVIEWER" in problems[0]
