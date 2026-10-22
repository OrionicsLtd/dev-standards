"""Command line: `scan` a repository, or list what is being exploited `hot` right now."""

import argparse
import datetime
import shutil
import sys
from pathlib import Path
from typing import Any

from . import feeds, osv, report, runtimes

DEFAULT_DAYS = 30


def _optional(fetch: Any, *args: Any) -> tuple[Any, str]:
    """Fetch a feed, returning an empty result and a note when it is unavailable."""
    try:
        return fetch(*args), ""
    except feeds.FeedError as error:
        return None, f"> Feed unavailable, results incomplete: {error}\n"


def scan(root: Path) -> str:
    """Report vulnerable dependencies and outdated runtimes for one repository."""
    if not shutil.which("osv-scanner"):
        raise SystemExit("osv-scanner is not installed: `brew install osv-scanner`")
    found = osv.parse(osv.scan(root), root)
    notes = []
    kev, note = _optional(feeds.kev)
    notes.append(note)
    cves = [c for p in found for a in p.advisories for c in a.cves]
    epss, note = _optional(feeds.epss, cves) if cves else ({}, "")
    notes.append(note)
    node, note = _optional(feeds.node_releases)
    notes.append(note)
    assessments = []
    for runtime in runtimes.discover(root):
        cycles, note = _optional(feeds.cycles, runtimes.EOL_PRODUCT[runtime.name])
        notes.append(note)
        if cycles is not None:
            assessments.append(runtimes.assess(runtime, cycles, node or []))
    sections = [
        "".join(dict.fromkeys(n for n in notes if n)),
        report.dependencies(found, kev or {}, epss or {}),
        report.runtimes(assessments),
    ]
    return "\n".join(s for s in sections if s)


def hot(days: int) -> str:
    """Report what CISA added to its exploited catalog in the last `days` days."""
    since = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    recent = [e for e in feeds.kev().values() if e["dateAdded"] >= since]
    return report.exploited(recent, days)


def main(argv: list[str]) -> int:
    """Parse arguments and print the requested report."""
    parser = argparse.ArgumentParser(prog="advisories", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    scan_cmd = commands.add_parser("scan", help="vulnerable dependencies and runtimes")
    scan_cmd.add_argument("path", nargs="?", default=".", type=Path)
    hot_cmd = commands.add_parser("hot", help="vulnerabilities exploited in the wild recently")
    hot_cmd.add_argument("--days", type=int, default=DEFAULT_DAYS)
    args = parser.parse_args(argv)
    try:
        output = scan(args.path.resolve()) if args.command == "scan" else hot(args.days)
    except (feeds.FeedError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(output)
    return 0
