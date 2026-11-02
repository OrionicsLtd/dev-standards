"""Decide whether a turn may end: checks, style rules, independent review, then the report."""

import hashlib
import re
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path

from . import checks, state, style
from .config import Config
from .diff import FileDiff, Snapshot, added_lines, line_key

REVIEWER = "diff-reviewer"
EVIDENCE = re.compile(r"^\W*(not verified|unverified)\b", re.IGNORECASE | re.MULTILINE)


@dataclass(frozen=True)
class Decision:
    """`reason` blocks the stop and goes to Claude; `notice` is shown to the user; `checked` is the
    code fingerprint the checks passed at, if they ran and passed; `settled` is false while the
    verdict waits on a running review, so the same change is judged again once it reports."""

    reason: str = ""
    notice: str = ""
    checked: str = ""
    settled: bool = True


def code_fingerprint(files: tuple[FileDiff, ...], config: Config) -> str:
    """Hash only the code part of the change, so doc edits don't re-run the checks."""
    digest = hashlib.sha256()
    for file in files:
        if file.path.endswith(config.code_suffixes):
            digest.update(f"{file.path}\0{file.removed}\0".encode())
            digest.update("\n".join(text for _, text in file.added).encode())
    return digest.hexdigest()


def _lengths(root: Path, files: tuple[FileDiff, ...]) -> dict[str, int]:
    lengths = {}
    for file in files:
        try:
            lengths[file.path] = len((root / file.path).read_text().splitlines())
        except (OSError, UnicodeDecodeError):
            continue
    return lengths


def _style(
    mine: tuple[FileDiff, ...],
    touched: tuple[FileDiff, ...],
    lengths: dict[str, int],
    config: Config,
) -> str:
    findings = style.banned(mine, config) + style.oversized(touched, lengths, config)
    return "Style rules (see CLAUDE.md):\n" + "\n".join(map(str, findings)) if findings else ""


def own_lines(
    snap: Snapshot, session: state.Session, written: Counter[str], config: Config
) -> Counter[str]:
    """Added lines this session is answerable for: as many copies of each as its own edits wrote,
    less those already there when it started. Another session sharing the checkout answers for
    its own."""
    return (added_lines(snap.files, config.review_suffixes) - Counter(session.baseline)) & written


def _own_files(snap: Snapshot, own: Counter[str]) -> tuple[FileDiff, ...]:
    """The changed files this session wrote to, each cut down to the lines it wrote."""
    left = own.copy()
    files = []
    for file in snap.files:
        added = []
        for no, text in file.added:
            key = line_key(file.path, text)
            if left[key] > 0:
                left[key] -= 1
                added.append((no, text))
        if added:
            files.append(replace(file, added=tuple(added)))
    return tuple(files)


def _review_request(pending: Counter[str], mine: tuple[FileDiff, ...], config: Config) -> str:
    paths = sorted({key.split("\0", 1)[0] for key in pending})
    notes = style.dense(mine, config)
    lines = [
        f"{sum(pending.values())} added lines have not been independently reviewed "
        f"({', '.join(paths[:8])}{' …' if len(paths) > 8 else ''}).",
        f"Run the `{REVIEWER}` agent. Give it the user's request in their words and the path of "
        "any spec or design doc this work implements. Fix what it confirms, or say in your report "
        "why a finding does not apply.",
    ]
    if notes:
        lines.append("Ask it to look hard at these comment-heavy files: " + "; ".join(notes))
    return "\n".join(lines)


def _summary(results: list[checks.Result], candidates: list[str]) -> str:
    ran = [r for r in results if not r.skipped]
    lines = []
    if ran:
        marks = " · ".join(f"{r.name} {'✓' if r.passed else '✗'}" for r in ran)
        lines.append(f"devgate: {marks} ({sum(r.seconds for r in ran):.0f}s)")
    if candidates:
        lines.append("devgate: split candidates: " + "; ".join(candidates))
    return "\n".join(lines)


def evaluate(
    root: Path,
    snap: Snapshot,
    session: state.Session,
    written: Counter[str],
    config: Config,
    message: str,
    reviewing: bool,
) -> Decision:
    """Return whether the turn may end; checks re-run only when code changed since they passed.

    While a review is running the turn may end without a report: the reviewer's report starts a
    new turn, and the change is judged in full at its end."""
    own = own_lines(snap, session, written, config)
    if snap.fingerprint == session.passed or not own:
        return Decision()
    mine = _own_files(snap, own)
    paths = {file.path for file in mine}
    touched = tuple(file for file in snap.files if file.path in paths)
    fingerprint = code_fingerprint(touched, config)
    results: list[checks.Result] = []
    if fingerprint != session.checked:
        changed = tuple(sorted(path for path in paths if (root / path).is_file()))
        results = checks.run_all(config.checks, root, changed, config.timeout)
    problems = [f"`{r.name}` failed:\n{r.output}" for r in results if not r.passed]
    lengths = _lengths(root, touched)
    problems += filter(None, [_style(mine, touched, lengths, config)])
    if problems:
        return Decision(reason="Fix these before finishing:\n\n" + "\n\n".join(problems))
    # Files already oversized that grew further never block: they go on the split backlog, which
    # every session start shows, and in the notice.
    grown = style.grown(touched, lengths, config)
    state.note_oversized(root, {path: length for path, length, _ in grown})
    candidates = style.growing(touched, lengths, config)
    if reviewing:
        waiting = f"devgate: `{REVIEWER}` is still running; the report is checked once it is back."
        notice = "\n".join(filter(None, [_summary(results, candidates), waiting]))
        return Decision(notice=notice, checked=fingerprint, settled=False)
    pending = own - state.reviewed(root)
    if sum(pending.values()) >= config.review_threshold:
        reason = _review_request(pending, mine, config)
        return Decision(reason=reason, checked=fingerprint)
    if not EVIDENCE.search(message):
        return Decision(
            reason="The report must end with a `Not verified:` line naming what was not checked "
            "(or `Not verified: nothing`), after the commands run and the requirements covered.",
            checked=fingerprint,
        )
    return Decision(notice=_summary(results, candidates), checked=fingerprint)
