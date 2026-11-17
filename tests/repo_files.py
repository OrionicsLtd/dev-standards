"""Read this repository's skills, agents and reviewer wiring, and lint them.

Each check returns a tuple of problem strings, empty when the repository is clean.
"""

import ast
import json
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

FENCE = "---"
FOLDED = (">-", ">")
SKILL_FILE = "SKILL.md"
GATE = Path("hooks/devgate/gate.py")
SETTINGS = Path("settings.example.json")
DEVGATE_SUBAGENT_STOP = re.compile(r'run_devgate\.py"?\s+subagent-stop\b')
SKILL_PATH = re.compile(r"skills/([a-z0-9-]+)/")
AGENT_PATH = re.compile(r"agents/([a-z0-9-]+)\.md")
NAME_TOKEN = re.compile(r"`([a-z0-9]+(?:-[a-z0-9]+)+)`")


@dataclass(frozen=True)
class Doc:
    """A skill or agent: the name it is filed under, its file and its description."""

    name: str
    path: Path
    description: str


def parse_frontmatter(text: str) -> dict[str, str] | None:
    """The `key: value` pairs between the opening `---` fences, or None without them.

    Handles the two forms the repository uses: plain values and `>-` / `>` folded blocks.
    """
    lines = text.splitlines()
    if not lines or lines[0] != FENCE or FENCE not in lines[1:]:
        return None
    fields: dict[str, list[str]] = {}
    key = ""
    for line in lines[1 : lines.index(FENCE, 1)]:
        if line.startswith(" ") and key:
            fields[key].append(line.strip())
            continue
        key, _, value = line.partition(":")
        value = value.strip()
        fields[key] = [] if value in FOLDED else [value]
    return {name: " ".join(parts) for name, parts in fields.items()}


def _skill_dirs(root: Path) -> list[Path]:
    return sorted(path for path in (root / "skills").iterdir() if path.is_dir())


def _agent_files(root: Path) -> list[Path]:
    return sorted((root / "agents").glob("*.md"))


def _doc(name: str, path: Path) -> Doc | None:
    fields = parse_frontmatter(path.read_text()) if path.is_file() else None
    if not fields or not fields.get("name") or not fields.get("description"):
        return None
    return Doc(name, path, fields["description"])


def load_skills(root: Path) -> tuple[Doc, ...]:
    """Skills with a readable `SKILL.md`, by directory name; `name_problems` reports the rest."""
    docs = (_doc(path.name, path / SKILL_FILE) for path in _skill_dirs(root))
    return tuple(doc for doc in docs if doc)


def _relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _name_problem(root: Path, path: Path, expected: str, *, needs_description: bool) -> str | None:
    where = _relative(root, path)
    if not path.is_file():
        return f"{where}: missing"
    fields = parse_frontmatter(path.read_text())
    if fields is None:
        return f"{where}: no frontmatter"
    if fields.get("name") != expected:
        return f"{where}: name {fields.get('name')!r} should be {expected!r}"
    if needs_description and not fields.get("description"):
        return f"{where}: no description"
    return None


def name_problems(root: Path) -> tuple[str, ...]:
    """Skills whose name differs from their directory, agents whose name differs from their file."""
    skills = (
        _name_problem(root, path / SKILL_FILE, path.name, needs_description=True)
        for path in _skill_dirs(root)
    )
    agents = (
        _name_problem(root, path, path.stem, needs_description=False) for path in _agent_files(root)
    )
    return tuple(problem for problem in (*skills, *agents) if problem)


def length_problems(skills: Iterable[Doc], limit: int) -> tuple[str, ...]:
    """Skill descriptions longer than `limit` characters."""
    return tuple(
        f"{skill.name}: description is {len(skill.description)} characters, over {limit}"
        for skill in skills
        if len(skill.description) > limit
    )


def _referring_files(root: Path) -> Iterator[Path]:
    yield from sorted((root / "skills").rglob("*.md"))
    yield from _agent_files(root)
    yield from (path for path in (root / "CLAUDE.md", root / "README.md") if path.is_file())


def reference_problems(root: Path, allowed: frozenset[str]) -> tuple[str, ...]:
    """References to skills, agents or hyphenated names that do not exist."""
    skills = {path.name for path in _skill_dirs(root)}
    agents = {path.stem for path in _agent_files(root)}
    names = skills | agents | allowed
    problems = []
    for path in _referring_files(root):
        where = _relative(root, path)
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            problems += [
                f"{where}:{number}: skills/{name}/ is not a skill directory"
                for name in SKILL_PATH.findall(line)
                if name not in skills
            ]
            problems += [
                f"{where}:{number}: agents/{name}.md is not an agent file"
                for name in AGENT_PATH.findall(line)
                if name not in agents
            ]
            problems += [
                f"{where}:{number}: `{name}` is not a skill, agent or allowed name"
                for name in NAME_TOKEN.findall(line)
                if name not in names
            ]
    return tuple(problems)


def _gate_reviewer(source: str) -> str | None:
    for node in ast.parse(source).body:
        if (
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "REVIEWER" for target in node.targets
            )
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            return node.value.value
    return None


def _devgate_matchers(settings: dict) -> list[str | None]:
    return [
        entry.get("matcher")
        for entry in settings.get("hooks", {}).get("SubagentStop", [])
        if any(DEVGATE_SUBAGENT_STOP.search(hook.get("command", "")) for hook in entry["hooks"])
    ]


def reviewer_problems(root: Path) -> tuple[str, ...]:
    """Disagreements between gate.py's REVIEWER, its agent file and the SubagentStop matcher."""
    reviewer = _gate_reviewer((root / GATE).read_text())
    if reviewer is None:
        return (f"{GATE}: no string REVIEWER assignment",)
    problems = []
    agent = root / "agents" / f"{reviewer}.md"
    if problem := _name_problem(root, agent, reviewer, needs_description=False):
        problems.append(problem)
    matchers = _devgate_matchers(json.loads((root / SETTINGS).read_text()))
    if not matchers:
        problems.append(f"{SETTINGS}: no SubagentStop entry runs devgate's subagent-stop")
    problems += [
        f"{SETTINGS}: SubagentStop matcher {matcher!r} does not match {reviewer!r}"
        for matcher in matchers
        if not _matches(matcher, reviewer)
    ]
    return tuple(problems)


def _matches(matcher: str | None, name: str) -> bool:
    try:
        return matcher is not None and re.fullmatch(matcher, name) is not None
    except re.error:
        return False
