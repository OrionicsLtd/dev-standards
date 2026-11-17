"""Unit tests for running checks: a tool that is not installed is neither a pass nor a failure."""

from pathlib import Path

import pytest

from devgate.checks import Result, run
from devgate.config import Check
from devgate.gate import _summary

SPAWN_ERROR = """#!/bin/sh
echo "error: Failed to spawn: \\`$3\\`" >&2
echo "Caused by: No such file or directory (os error 2)" >&2
exit 2
"""


def _runner(tmp_path: Path, body: str) -> Path:
    script = tmp_path / "fake-uv"
    script.write_text(body)
    script.chmod(0o755)
    return script


def test_missing_binary_is_not_a_pass(tmp_path: Path) -> None:
    result = run(Check("lint", "no-such-tool-xyz {py}"), tmp_path, ("a.py",), 10)
    assert result.missing and not result.passed and not result.skipped
    assert result.output == "no-such-tool-xyz not installed"


def test_runner_that_cannot_spawn_the_tool_is_missing(tmp_path: Path) -> None:
    fake = _runner(tmp_path, SPAWN_ERROR)
    check = Check("pyright", f"{fake} run --quiet pyright", filtered=True)
    result = run(check, tmp_path, ("a.py",), 10)
    assert result.missing and not result.passed
    assert result.output == "pyright not installed"


def test_spawn_failure_for_the_tool_is_found_after_others(tmp_path: Path) -> None:
    body = "#!/bin/sh\necho 'error: Failed to spawn: `other`' >&2\n" + SPAWN_ERROR.split("\n", 1)[1]
    fake = _runner(tmp_path, body)
    result = run(Check("pyright", f"{fake} run --quiet pyright"), tmp_path, ("a.py",), 10)
    assert result.missing and result.output == "pyright not installed"


@pytest.mark.parametrize(
    "body",
    [
        "#!/bin/sh\necho boom >&2\nexit 2\n",
        "#!/bin/sh\necho 'error: Failed to spawn: `other`' >&2\nexit 2\n",
    ],
)
def test_other_runner_errors_are_failures(tmp_path: Path, body: str) -> None:
    fake = _runner(tmp_path, body)
    result = run(Check("pyright", f"{fake} run --quiet pyright"), tmp_path, ("a.py",), 10)
    assert not result.missing and not result.passed


def test_summary_lists_missing_checks() -> None:
    results = [
        Result("ruff", True, 1.0),
        Result("pyright", False, 0.0, "pyright not installed", missing=True),
        Result("mypy", True, 0.0, skipped=True),
    ]
    assert _summary(results, []) == "devgate: ruff ✓ · pyright – not installed (1s)"
