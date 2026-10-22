"""Decide whether a turn may end: checks, style rules, independent review, then the report."""

import hashlib
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from . import checks, state, style
from .config import Config
from .diff import Snapshot, added_lines

REVIEWER = "diff-reviewer"
EVIDENCE = re.compile(r"^\W*(not verified|unverified)\b", re.IGNORECASE | re.MULTILINE)


@dataclass(frozen=True)
class Decision:
    """`reason` blocks the stop and goes to Claude; `notice` is shown to the user; `checked` is the
    code fingerprint the checks passed at, if they ran and passed."""

    reason: str = ""
    notice: str = ""
    checked: str = ""


def code_fingerprint(snap: Snapshot, config: Config) -> str:
    """Hash only the code part of the change, so doc edits don't re-run the checks."""
    digest = hashlib.sha256()
    for file in snap.files:
        if file.path.endswith(config.code_suffixes):
            digest.update(f"{file.path}\0{file.removed}\0".encode())
            digest.update("\n".join(text for _, text in file.added).encode())
    return digest.hexdigest()


def _lengths(root: Path, snap: Snapshot) -> dict[str, int]:
    lengths = {}
    for file in snap.files:
        try:
            lengths[file.path] = len((root / file.path).read_text().splitlines())
        except (OSError, UnicodeDecodeError):
            continue
    return lengths


def _style(snap: Snapshot, lengths: dict[str, int], config: Config) -> str:
    findings = style.banned(snap.files, config) + style.oversized(snap.files, lengths, config)
    return "Style rules (see CLAUDE.md):\n" + "\n".join(map(str, findings)) if findings else ""


def own_lines(snap: Snapshot, session: state.Session, config: Config) -> Counter[str]:
    """Added lines this session is answerable for: everything not already there when it started."""
    return added_lines(snap.files, config.review_suffixes) - Counter(session.baseline)


def unreviewed(root: Path, snap: Snapshot, session: state.Session, config: Config) -> Counter[str]:
    """Added lines that were neither present when the session started nor seen by a reviewer."""
    return own_lines(snap, session, config) - state.reviewed(root)


def _review_request(
    pending: Counter[str], snap: Snapshot, config: Config, candidates: list[str]
) -> str:
    paths = sorted({key.split("\0", 1)[0] for key in pending})
    notes = style.dense(snap.files, config)
    lines = [
        f"{sum(pending.values())} added lines have not been independently reviewed "
        f"({', '.join(paths[:8])}{' …' if len(paths) > 8 else ''}).",
        f"Run the `{REVIEWER}` agent in the foreground. Give it the user's request in their words "
        "and the path of any spec or design doc this work implements. Fix what it confirms, or say "
        "in your report why a finding does not apply.",
    ]
    if notes:
        lines.append("Ask it to look hard at these comment-heavy files: " + "; ".join(notes))
    if candidates:
        lines.append(
            "Already oversized and growing; ask it where each splits: " + "; ".join(candidates)
        )
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
    root: Path, snap: Snapshot, session: state.Session, config: Config, message: str
) -> Decision:
    """Return whether the turn may end; checks re-run only when code changed since they passed."""
    if snap.fingerprint == session.passed or not own_lines(snap, session, config):
        return Decision()
    fingerprint = code_fingerprint(snap, config)
    results: list[checks.Result] = []
    if fingerprint != session.checked:
        changed = tuple(file.path for file in snap.files if (root / file.path).is_file())
        results = checks.run_all(config.checks, root, changed, config.timeout)
    problems = [f"`{r.name}` failed:\n{r.output}" for r in results if not r.passed]
    lengths = _lengths(root, snap)
    problems += filter(None, [_style(snap, lengths, config)])
    if problems:
        return Decision(reason="Fix these before finishing:\n\n" + "\n\n".join(problems))
    candidates = style.growing(snap.files, lengths, config)
    pending = unreviewed(root, snap, session, config)
    if sum(pending.values()) >= config.review_threshold:
        reason = _review_request(pending, snap, config, candidates)
        return Decision(reason=reason, checked=fingerprint)
    if snap.files and not EVIDENCE.search(message):
        return Decision(
            reason="The report must end with a `Not verified:` line naming what was not checked "
            "(or `Not verified: nothing`), after the commands run and the requirements covered.",
            checked=fingerprint,
        )
    return Decision(notice=_summary(results, candidates), checked=fingerprint)
