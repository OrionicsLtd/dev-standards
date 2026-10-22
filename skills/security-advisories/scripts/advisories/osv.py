"""Run osv-scanner over a repository and reduce its report to vulnerable packages and fixes."""

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .versions import key, newer

# osv-scanner exits 1 when it found vulnerabilities and 128 when there was nothing to scan.
SCANNER_OK = {0, 1}
NOTHING_TO_SCAN = 128


@dataclass(frozen=True)
class Advisory:
    """One vulnerability, with the duplicate records other databases keep for it folded in."""

    ids: tuple[str, ...]
    summary: str
    severity: float | None
    fixed: str | None

    @property
    def cves(self) -> tuple[str, ...]:
        return tuple(i for i in self.ids if i.startswith("CVE-"))

    @property
    def malicious(self) -> bool:
        """OpenSSF malicious-package records: the version itself is the attack, not a bug."""
        return any(i.startswith("MAL-") for i in self.ids)


@dataclass(frozen=True)
class Vulnerable:
    """A package version with at least one advisory against it."""

    ecosystem: str
    name: str
    version: str
    source: str
    advisories: tuple[Advisory, ...]

    @property
    def target(self) -> str | None:
        """The lowest version that fixes every advisory, or None while any has no fix."""
        fixes = [a.fixed for a in self.advisories if a.fixed is not None]
        if not fixes or len(fixes) < len(self.advisories):
            return None
        return max(fixes, key=key)


def scan(path: Path) -> dict[str, Any]:
    """Run osv-scanner recursively over `path` and return its JSON report."""
    command = ["osv-scanner", "scan", "source", "-r", "--format", "json", str(path)]
    done = subprocess.run(command, capture_output=True, text=True)
    if done.returncode == NOTHING_TO_SCAN:
        return {"results": []}
    if done.returncode not in SCANNER_OK:
        raise RuntimeError(f"osv-scanner failed ({done.returncode}): {done.stderr.strip()[-500:]}")
    return json.loads(done.stdout)


def _intervals(vuln: dict[str, Any], name: str) -> list[tuple[str, str | None]]:
    """Return the (introduced, fixed) intervals a record gives for this package."""
    intervals = []
    for affected in vuln.get("affected", []):
        if affected.get("package", {}).get("name", "").lower() != name.lower():
            continue
        for rng in affected.get("ranges", []):
            if rng.get("type") == "GIT":
                continue
            start: str | None = None
            for event in rng.get("events", []):
                if "introduced" in event:
                    start = event["introduced"]
                elif "fixed" in event and start is not None:
                    intervals.append((start, event["fixed"]))
                    start = None
            if start is not None:
                intervals.append((start, None))
    return intervals


def fixed_version(vuln: dict[str, Any], name: str, version: str) -> str | None:
    """The fix for the interval containing `version`; None when that interval has no fix."""
    for start, fix in _intervals(vuln, name):
        if (start == "0" or not newer(start, version)) and (fix is None or newer(fix, version)):
            return fix
    later = [fix for _, fix in _intervals(vuln, name) if fix and newer(fix, version)]
    return min(later, key=key) if later else None


def _advisories(entry: dict[str, Any]) -> tuple[Advisory, ...]:
    name, version = entry["package"]["name"], entry["package"]["version"]
    records = {vuln["id"]: vuln for vuln in entry.get("vulnerabilities", [])}
    groups: list[dict[str, Any]] = entry.get("groups") or [{"ids": [i]} for i in records]
    advisories = []
    for group in groups:
        members = [records[i] for i in group["ids"] if i in records]
        if not members:
            continue
        fixes = [fixed_version(record, name, version) for record in members]
        known = [fix for fix in fixes if fix]
        severity = group.get("max_severity")
        advisories.append(
            Advisory(
                ids=tuple(sorted(set(group.get("aliases", []) + group["ids"]))),
                summary=next((m.get("summary", "") for m in members if m.get("summary")), ""),
                severity=float(severity) if severity else None,
                fixed=max(known, key=key) if known else None,
            )
        )
    return tuple(advisories)


def _relative(path: str, root: Path | None) -> str:
    if root is None:
        return path
    try:
        return str(Path(path).relative_to(root))
    except ValueError:
        return path


def parse(report: dict[str, Any], root: Path | None = None) -> list[Vulnerable]:
    """Reduce an osv-scanner report to one entry per vulnerable package version."""
    found = []
    for result in report.get("results", []):
        source = _relative(result.get("source", {}).get("path", ""), root)
        for entry in result.get("packages", []):
            advisories = _advisories(entry)
            if advisories:
                package = entry["package"]
                found.append(
                    Vulnerable(
                        package.get("ecosystem", ""),
                        package["name"],
                        package["version"],
                        source,
                        advisories,
                    )
                )
    return found
