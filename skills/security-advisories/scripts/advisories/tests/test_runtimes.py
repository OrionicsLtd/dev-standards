"""Runtime discovery and release-line assessment, with feed data supplied inline."""

import subprocess
from pathlib import Path

from advisories.runtimes import Runtime, assess, discover

NODE_CYCLES = [{"cycle": "24", "latest": "24.22.1", "eol": "2028-04-30"}]
NODE_RELEASES = [
    {"version": "v24.22.1", "security": True},
    {"version": "v24.22.0", "security": False},
    {"version": "v22.23.4", "security": True},
]
PYTHON_CYCLES = [
    {"cycle": "3.12", "latest": "3.12.15", "eol": "2028-10-31"},
    {"cycle": "3.8", "latest": "3.8.20", "eol": "2024-10-07"},
]


def test_node_missing_a_security_release_is_urgent() -> None:
    result = assess(Runtime("node", "24.18.0", "machine"), NODE_CYCLES, NODE_RELEASES)
    assert result.urgent and "24.22.1" in result.status


def test_node_on_the_security_release_is_current() -> None:
    result = assess(Runtime("node", "24.22.1", "machine"), NODE_CYCLES, NODE_RELEASES)
    assert result.status == "current" and not result.urgent


def test_line_pin_is_not_compared_by_patch() -> None:
    assert assess(Runtime("node", "24", "Dockerfile"), NODE_CYCLES, NODE_RELEASES).status == (
        "pins the release line only"
    )
    assert assess(Runtime("python", "3.12", ".python-version"), PYTHON_CYCLES, []).status == (
        "pins the release line only"
    )


def test_end_of_life_and_stale_patch() -> None:
    assert assess(Runtime("python", "3.8.10", "x"), PYTHON_CYCLES, []).urgent
    stale = assess(Runtime("python", "3.12.3", "x"), PYTHON_CYCLES, [])
    assert stale.status == "behind the latest patch" and not stale.urgent


def test_discover_reads_pins_and_skips_ignored_dockerfiles(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / ".gitignore").write_text("vendor/\n")
    (tmp_path / ".nvmrc").write_text("v22.23.4\n")
    (tmp_path / "Dockerfile").write_text("FROM python:3.12-slim AS base\nFROM python:3.12-slim\n")
    (tmp_path / "vendor").mkdir()
    (tmp_path / "vendor" / "Dockerfile").write_text("FROM node:16\n")
    found = [r for r in discover(tmp_path) if not r.where.startswith("this machine")]
    assert found == [Runtime("node", "22.23.4", ".nvmrc"), Runtime("python", "3.12", "Dockerfile")]
