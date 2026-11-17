"""Command line: `scan` a repository, or list what is being exploited `hot` right now.

Each prints a short summary and writes the full report to a file, so a long report never
lands in the caller's terminal or context.
"""

import argparse
import datetime
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import feeds, osv, report, runtimes

DEFAULT_DAYS = 30


@dataclass(frozen=True)
class Output:
    """What a command prints, and the full report it writes to a file."""

    summary: str
    details: str


def _optional(fetch: Any, *args: Any) -> tuple[Any, str]:
    """Fetch a feed, returning an empty result and a note when it is unavailable."""
    try:
        return fetch(*args), ""
    except feeds.FeedError as error:
        return None, f"> Feed unavailable, results incomplete: {error}\n"


def scan(root: Path) -> Output:
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
    unavailable = "".join(dict.fromkeys(n for n in notes if n))
    runtime_section = report.runtimes(assessments)

    def render(summary: bool) -> str:
        packages = report.dependencies(found, kev or {}, epss or {}, summary)
        return "\n".join(s for s in [unavailable, packages, runtime_section] if s)

    return Output(render(summary=True), render(summary=False))


def hot(days: int) -> Output:
    """Report what CISA added to its exploited catalog in the last `days` days."""
    since = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    recent = [e for e in feeds.kev().values() if e["dateAdded"] >= since]
    return Output(report.exploited_summary(recent, days), report.exploited(recent, days))


def _report_file(command: str, output: Path | None) -> Path:
    if output is not None:
        return output
    with tempfile.NamedTemporaryFile(
        prefix=f"advisories-{command}-", suffix=".md", delete=False
    ) as handle:
        return Path(handle.name)


def main(argv: list[str]) -> int:
    """Parse arguments and print the requested report."""
    parser = argparse.ArgumentParser(prog="advisories", description=__doc__)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--output", type=Path, help="where to write the full report (default: a new temp file)"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    scan_cmd = commands.add_parser(
        "scan", parents=[common], help="vulnerable dependencies and runtimes"
    )
    scan_cmd.add_argument("path", nargs="?", default=".", type=Path)
    hot_cmd = commands.add_parser(
        "hot", parents=[common], help="vulnerabilities exploited in the wild recently"
    )
    hot_cmd.add_argument("--days", type=int, default=DEFAULT_DAYS)
    args = parser.parse_args(argv)
    try:
        output = scan(args.path.resolve()) if args.command == "scan" else hot(args.days)
        path = _report_file(args.command, args.output)
        path.write_text(output.details)
    except (feeds.FeedError, RuntimeError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"{output.summary}\nFull report: {path}")
    return 0
