"""Runtimes on this machine and pinned by the repository, checked against their release lines."""

import datetime
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .versions import key, line, newer

VERSION = re.compile(r"(\d+(?:\.\d+)+|\d+)")
COMMANDS = {
    "node": ["node", "--version"],
    "python": ["python3", "--version"],
    "go": ["go", "version"],
}
PIN_FILES = {".nvmrc": "node", ".node-version": "node", ".python-version": "python"}
DOCKER_FROM = re.compile(r"^\s*FROM\s+(?:\S+/)?(node|python|golang):(\d+(?:\.\d+)*)", re.I | re.M)
EOL_PRODUCT = {"node": "nodejs", "python": "python", "go": "go"}
CYCLE_DEPTH = {"node": 1, "python": 2, "go": 2}


@dataclass(frozen=True)
class Runtime:
    """A runtime version and where it was found."""

    name: str
    version: str
    where: str


@dataclass(frozen=True)
class Assessment:
    """How a runtime version compares with the newest release of its line."""

    runtime: Runtime
    latest: str
    status: str
    urgent: bool


def _installed(name: str, command: list[str]) -> Runtime | None:
    if not shutil.which(command[0]):
        return None
    done = subprocess.run(command, capture_output=True, text=True)
    match = VERSION.search(done.stdout + done.stderr)
    return (
        Runtime(name, match.group(1), f"this machine ({shutil.which(command[0])})")
        if match
        else None
    )


def _dockerfiles(root: Path) -> list[Path]:
    """Dockerfiles the repository owns: tracked or untracked, but never git-ignored."""
    command = ["git", "ls-files", "-co", "--exclude-standard", "--", "*Dockerfile*"]
    done = subprocess.run(command, cwd=root, capture_output=True, text=True)
    if done.returncode == 0:
        return sorted(root / name for name in done.stdout.splitlines())
    skip = {".git", "node_modules", ".venv"}
    return sorted(p for p in root.rglob("Dockerfile*") if not skip & set(p.parts))


def discover(root: Path) -> list[Runtime]:
    """Find runtime versions installed locally and pinned in the repository."""
    found = [r for name, cmd in COMMANDS.items() if (r := _installed(name, cmd))]
    for filename, name in PIN_FILES.items():
        pin = root / filename
        if pin.is_file() and (match := VERSION.search(pin.read_text())):
            found.append(Runtime(name, match.group(1), filename))
    for dockerfile in _dockerfiles(root):
        for image, tag in DOCKER_FROM.findall(dockerfile.read_text(errors="ignore")):
            name = "go" if image.lower() == "golang" else image.lower()
            found.append(Runtime(name, tag, str(dockerfile.relative_to(root))))
    return list(dict.fromkeys(found))


def _cycle(runtime: Runtime, cycles: list[dict[str, Any]]) -> dict[str, Any] | None:
    wanted = line(runtime.version, CYCLE_DEPTH[runtime.name])
    return next((c for c in cycles if line(str(c["cycle"]), len(wanted)) == wanted), None)


def assess(
    runtime: Runtime, cycles: list[dict[str, Any]], node: list[dict[str, Any]]
) -> Assessment:
    """Compare a runtime with its release line: end of life, missing security releases, then age."""
    cycle = _cycle(runtime, cycles)
    if cycle is None:
        return Assessment(runtime, "?", "release line not found", False)
    latest = str(cycle.get("latest", "?"))
    eol = cycle.get("eol")
    if isinstance(eol, str) and eol <= datetime.date.today().isoformat():
        return Assessment(runtime, latest, f"end of life since {eol}", True)
    if len(runtime.version.split(".")) <= CYCLE_DEPTH[runtime.name]:
        return Assessment(runtime, latest, "pins the release line only", False)
    if runtime.name == "node":
        major = line(runtime.version, 1)
        fixes = [
            r["version"].lstrip("v")
            for r in node
            if r.get("security") and line(r["version"].lstrip("v"), 1) == major
        ]
        missing = [f for f in fixes if newer(f, runtime.version)]
        if missing:
            return Assessment(
                runtime, latest, f"security release {max(missing, key=key)} missing", True
            )
    if newer(latest, runtime.version):
        return Assessment(runtime, latest, "behind the latest patch", False)
    return Assessment(runtime, latest, "current", False)
