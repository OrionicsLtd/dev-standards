"""Render findings as short Markdown tables, most urgent first."""

from typing import Any

from .osv import Advisory, Vulnerable
from .runtimes import Assessment

SUMMARY_CHARS = 70
# Below this, an exploitation probability is noise next to the severity score.
EPSS_SHOWN = 0.01


def _rank(package: Vulnerable, kev: dict[str, Any]) -> tuple[int, int, float]:
    malicious = any(a.malicious for a in package.advisories)
    exploited = any(c in kev for a in package.advisories for c in a.cves)
    severity = max((a.severity or 0.0) for a in package.advisories)
    return (int(malicious), int(exploited), severity)


def _advisory(advisory: Advisory, kev: dict[str, Any], epss: dict[str, float]) -> str:
    label = advisory.cves[0] if advisory.cves else advisory.ids[0]
    marks = []
    if advisory.malicious:
        marks.append("MALICIOUS")
    if any(c in kev for c in advisory.cves):
        marks.append("exploited")
    score = max((epss.get(c, 0.0) for c in advisory.cves), default=0.0)
    if score >= EPSS_SHOWN:
        marks.append(f"EPSS {score:.0%}")
    severity = f"{advisory.severity:.1f}" if advisory.severity is not None else "?"
    note = f" ({', '.join(marks)})" if marks else ""
    return f"{label} {severity}{note}: {advisory.summary[:SUMMARY_CHARS]}"


def dependencies(found: list[Vulnerable], kev: dict[str, Any], epss: dict[str, float]) -> str:
    """One row per vulnerable package: what it is, what fixes it, and why it matters."""
    if not found:
        return "## Dependencies\n\nNo known vulnerabilities in the scanned lockfiles.\n"
    rows = [
        "| Package | Installed → fix | Advisories | Lockfile |",
        "| --- | --- | --- | --- |",
    ]
    for package in sorted(found, key=lambda p: _rank(p, kev), reverse=True):
        target = package.target or "no fix for every advisory"
        advisories = "<br>".join(_advisory(a, kev, epss) for a in package.advisories)
        rows.append(
            f"| {package.ecosystem} `{package.name}` | {package.version} → {target} "
            f"| {advisories} | {package.source} |"
        )
    return "## Dependencies\n\n" + "\n".join(rows) + "\n"


def runtimes(assessments: list[Assessment]) -> str:
    """Runtimes with their release-line status, urgent ones first."""
    if not assessments:
        return "## Runtimes\n\nNo runtimes found.\n"
    rows = [
        "| Runtime | Version | Latest in line | Status | Where |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in sorted(assessments, key=lambda a: a.urgent, reverse=True):
        status = f"**{item.status}**" if item.urgent else item.status
        rt = item.runtime
        rows.append(f"| {rt.name} | {rt.version} | {item.latest} | {status} | {rt.where} |")
    return "## Runtimes\n\n" + "\n".join(rows) + "\n"


def exploited(entries: list[dict[str, Any]], days: int) -> str:
    """Vulnerabilities CISA added to its exploited catalog in the last `days` days."""
    if not entries:
        return f"## Actively exploited (last {days} days)\n\nNone added.\n"
    rows = [
        "| Added | Vendor / product | CVE | Vulnerability | Due |",
        "| --- | --- | --- | --- | --- |",
    ]
    for entry in sorted(entries, key=lambda e: e["dateAdded"], reverse=True):
        rows.append(
            f"| {entry['dateAdded']} | {entry['vendorProject']} / {entry['product']} "
            f"| {entry['cveID']} | {entry['vulnerabilityName']} | {entry['dueDate']} |"
        )
    return f"## Actively exploited (last {days} days)\n\n" + "\n".join(rows) + "\n"
