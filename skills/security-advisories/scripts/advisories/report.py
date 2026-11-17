"""Render findings as short Markdown tables, most urgent first."""

from collections import defaultdict
from typing import Any

from .osv import Advisory, Vulnerable
from .runtimes import Assessment

SUMMARY_CHARS = 70
SUMMARY_PACKAGES = 5
SUMMARY_ADVISORIES = 3
# Below this, an exploitation probability is noise next to the severity score.
EPSS_SHOWN = 0.01


def _urgency(advisory: Advisory, kev: dict[str, Any]) -> tuple[int, int, float]:
    exploited = any(c in kev for c in advisory.cves)
    return (int(advisory.malicious), int(exploited), advisory.severity or 0.0)


def _rank(package: Vulnerable, kev: dict[str, Any]) -> tuple[int, int, float]:
    urgencies = [_urgency(a, kev) for a in package.advisories]
    return (
        max(u[0] for u in urgencies),
        max(u[1] for u in urgencies),
        max(u[2] for u in urgencies),
    )


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


def _counts(found: list[Vulnerable], kev: dict[str, Any]) -> str:
    ranks = [_rank(package, kev) for package in found]
    malicious = sum(rank[0] for rank in ranks)
    exploited = sum(rank[1] for rank in ranks)
    return (
        f"{len(found)} vulnerable packages: {malicious} malicious, "
        f"{exploited} exploited in the wild."
    )


def _advisories(
    package: Vulnerable, kev: dict[str, Any], epss: dict[str, float], summary: bool
) -> str:
    advisories = package.advisories
    if summary:
        advisories = tuple(sorted(advisories, key=lambda a: _urgency(a, kev), reverse=True))
    shown = advisories[:SUMMARY_ADVISORIES] if summary else advisories
    lines = [_advisory(a, kev, epss) for a in shown]
    if len(shown) < len(advisories):
        lines.append(f"+{len(advisories) - len(shown)} more")
    return "<br>".join(lines)


def dependencies(
    found: list[Vulnerable], kev: dict[str, Any], epss: dict[str, float], summary: bool = False
) -> str:
    """One row per vulnerable package, most urgent first: what it is, what fixes it, and why it
    matters. A `summary` keeps the most urgent packages and advisories, counting the rest."""
    if not found:
        return "## Dependencies\n\nNo known vulnerabilities in the scanned lockfiles.\n"
    ranked = sorted(found, key=lambda p: _rank(p, kev), reverse=True)
    shown = ranked[:SUMMARY_PACKAGES] if summary else ranked
    rows = [
        "| Package | Installed → fix | Advisories | Lockfile |",
        "| --- | --- | --- | --- |",
    ]
    for package in shown:
        target = package.target or "no fix for every advisory"
        advisories = _advisories(package, kev, epss, summary)
        rows.append(
            f"| {package.ecosystem} `{package.name}` | {package.version} → {target} "
            f"| {advisories} | {package.source} |"
        )
    hidden = len(ranked) - len(shown)
    more = f"\n{hidden} more in the full report.\n" if hidden else ""
    return f"## Dependencies\n\n{_counts(found, kev)}\n\n" + "\n".join(rows) + "\n" + more


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


def _exploited_heading(days: int) -> str:
    return f"## Actively exploited (last {days} days)\n\n"


def exploited_summary(entries: list[dict[str, Any]], days: int) -> str:
    """How many entries CISA added recently, and the products each vendor had listed."""
    if not entries:
        return _exploited_heading(days) + "None added.\n"
    products: dict[str, set[str]] = defaultdict(set)
    for entry in entries:
        products[entry["vendorProject"]].add(entry["product"])
    vendors = "; ".join(f"{v} ({', '.join(sorted(p))})" for v, p in sorted(products.items()))
    return _exploited_heading(days) + f"{len(entries)} added. By vendor: {vendors}\n"


def exploited(entries: list[dict[str, Any]], days: int) -> str:
    """Vulnerabilities CISA added to its exploited catalog in the last `days` days."""
    if not entries:
        return _exploited_heading(days) + "None added.\n"
    rows = [
        "| Added | Vendor / product | CVE | Vulnerability | Due |",
        "| --- | --- | --- | --- | --- |",
    ]
    for entry in sorted(entries, key=lambda e: e["dateAdded"], reverse=True):
        rows.append(
            f"| {entry['dateAdded']} | {entry['vendorProject']} / {entry['product']} "
            f"| {entry['cveID']} | {entry['vulnerabilityName']} | {entry['dueDate']} |"
        )
    return _exploited_heading(days) + "\n".join(rows) + "\n"
