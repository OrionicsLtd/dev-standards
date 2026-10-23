"""Per-repository gate settings: detected from the repo's tooling, overridable per repo."""

import shutil
import tomllib
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

OVERRIDE = Path(".claude/devgate.toml")

CODE_SUFFIXES = (".py", ".pyi", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".sol", ".sh", ".java")
REVIEW_SUFFIXES = (*CODE_SUFFIXES, ".md", ".toml", ".yaml", ".yml")

# Comments and docstrings must read as if they were always part of the codebase: no planning
# vocabulary and no conversation.
BANNED = (
    r"\bWP ?\d+\b",
    r"\bPhase[- ]?\d+\b",
    r"\bProposal[- ]?\d+\b",
    r"\bspec ?§",
    r"\bper the (spec|plan|design doc)\b",
    r"\bas (requested|discussed|scoped|agreed)\b",
    r"\b(you|the user) (asked|wanted|requested)\b",
    r"\bpost-?mortem\b",
    r"\bwar[- ]?story\b",
    r"\bTODO\b.*\breview\b",
    r"\(P[0-3]\)",
)


@dataclass(frozen=True)
class Check:
    """One command to run. `{py}` expands to the changed Python files; `filtered` keeps only
    failure lines that name a changed file, so problems already present elsewhere don't block."""

    name: str
    cmd: str
    filtered: bool = False


@dataclass(frozen=True)
class Config:
    """Everything the gate needs to know about one repository."""

    enabled: bool = True
    checks: tuple[Check, ...] = ()
    max_lines: int = 400
    size_growth: int = 20
    size_exempt: tuple[str, ...] = ("tests/*", "*/tests/*", "test_*", "*_test.*", "*.md")
    review_threshold: int = 200
    banned: tuple[str, ...] = BANNED
    max_blocks: int = 3
    timeout: int = 300
    code_suffixes: tuple[str, ...] = CODE_SUFFIXES
    review_suffixes: tuple[str, ...] = REVIEW_SUFFIXES


def _runner(root: Path) -> str:
    """Return the command prefix that runs tools inside the project's environment."""
    if (root / "uv.lock").exists():
        return "uv run --quiet "
    if (root / "poetry.lock").exists():
        return "poetry run "
    if (root / ".venv/bin").is_dir():
        return str(root / ".venv/bin") + "/"
    return ""


def _has(root: Path, tool: dict[str, Any], key: str, *files: str) -> bool:
    return key in tool or any((root / name).exists() for name in files)


def detect(root: Path) -> tuple[Check, ...]:
    """Derive Python checks from the tools the repository already configures."""
    pyproject = root / "pyproject.toml"
    tool = tomllib.loads(pyproject.read_text()).get("tool", {}) if pyproject.exists() else {}
    run = _runner(root)
    checks: list[Check] = []
    if _has(root, tool, "ruff", "ruff.toml", ".ruff.toml"):
        checks += [
            Check("ruff", f"{run}ruff check --quiet {{py}}"),
            Check("ruff-format", f"{run}ruff format --check --quiet {{py}}"),
        ]
    if _has(root, tool, "pyright", "pyrightconfig.json"):
        checks.append(Check("pyright", f"{run}pyright", filtered=True))
    if _has(root, tool, "mypy", "mypy.ini", ".mypy.ini"):
        checks.append(Check("mypy", f"{run}mypy {{py}}", filtered=True))
    python_project = pyproject.exists() or (root / "setup.py").exists()
    has_pytest = _has(root, tool, "pytest", "pytest.ini", "conftest.py", "tests")
    if python_project and has_pytest and (run or shutil.which("pytest")):
        checks.append(Check("pytest", f"{run}pytest -q -x --no-header -p no:cacheprovider"))
    return tuple(checks)


def load(root: Path) -> Config:
    """Return the repository's config: detected checks, then any override file on top."""
    config = Config(checks=detect(root))
    override = root / OVERRIDE
    if not override.exists():
        return config
    raw = tomllib.loads(override.read_text())
    if "checks" in raw:
        raw["checks"] = tuple(Check(**entry) for entry in raw["checks"])
    if "extra_banned" in raw:
        raw["banned"] = (*config.banned, *raw.pop("extra_banned"))
    tuples = {key: tuple(value) for key, value in raw.items() if isinstance(value, list)}
    return replace(config, **{**raw, **tuples})
