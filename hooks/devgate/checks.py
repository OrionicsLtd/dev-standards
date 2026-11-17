"""Run the repository's configured checks and keep only the output worth reading."""

import re
import shlex
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from .config import Check

MAX_OUTPUT_LINES = 25
# How `uv run` reports a tool absent from the environment: it exits non-zero rather than
# raising FileNotFoundError, and the message names no changed file, so filtering would pass it.
SPAWN_FAILED = re.compile(r"^error: Failed to spawn: `([^`]+)`", re.MULTILINE)


@dataclass(frozen=True)
class Result:
    """Outcome of one check: `output` holds the failure lines, empty when it passed. A `missing`
    check could not run because its tool is not installed: neither passed nor failed."""

    name: str
    passed: bool
    seconds: float
    output: str = ""
    skipped: bool = False
    missing: bool = False


def _missing(check: Check, tool: str, seconds: float) -> Result:
    return Result(check.name, False, seconds, f"{tool} not installed", missing=True)


def _relevant(output: str, changed: tuple[str, ...]) -> str:
    """Keep the lines that mention a changed file."""
    return "\n".join(line for line in output.splitlines() if any(p in line for p in changed))


def _tail(output: str) -> str:
    lines = output.strip().splitlines()
    if len(lines) <= MAX_OUTPUT_LINES:
        return "\n".join(lines)
    return "\n".join(
        [f"... {len(lines) - MAX_OUTPUT_LINES} earlier lines", *lines[-MAX_OUTPUT_LINES:]]
    )


def run(check: Check, root: Path, changed: tuple[str, ...], timeout: int) -> Result:
    """Run one check against the changed files."""
    python = tuple(path for path in changed if path.endswith((".py", ".pyi")))
    if "{py}" in check.cmd and not python:
        return Result(check.name, True, 0.0, skipped=True)
    argv = [
        arg for part in shlex.split(check.cmd) for arg in (python if part == "{py}" else (part,))
    ]
    started = time.monotonic()
    try:
        done = subprocess.run(argv, cwd=root, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return Result(check.name, False, timeout, f"timed out after {timeout}s")
    except FileNotFoundError as error:
        return _missing(check, error.filename or argv[0], 0.0)
    seconds = time.monotonic() - started
    if done.returncode == 0:
        return Result(check.name, True, seconds)
    output = done.stdout + done.stderr
    unspawned = [tool for tool in SPAWN_FAILED.findall(output) if tool in argv]
    if unspawned:
        return _missing(check, unspawned[0], seconds)
    if check.filtered:
        output = _relevant(output, changed)
        if not output:
            return Result(check.name, True, seconds)
    return Result(check.name, False, seconds, _tail(output))


def run_all(
    checks: tuple[Check, ...], root: Path, changed: tuple[str, ...], timeout: int
) -> list[Result]:
    """Run every check in order; later checks still run after an earlier one fails."""
    return [run(check, root, changed, timeout) for check in checks]
