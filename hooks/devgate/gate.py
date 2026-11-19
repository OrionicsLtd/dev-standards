"""Decide whether a turn may end: checks, style rules, independent review, then the report."""

import hashlib
import re
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path

from . import checks, leaks, state, style, suppressions
from .config import Config
from .diff import FileDiff, Snapshot, added_lines, git, line_key

REVIEWER = "diff-reviewer"
EVIDENCE = re.compile(r"^\W*(not verified|unverified)\b", re.IGNORECASE | re.MULTILINE)
EVERY_FILE = ("",)  # every path ends with ""
FIX = "Fix these before finishing:\n\n"


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


def _modules(root: Path, files: tuple[FileDiff, ...], config: Config) -> dict[str, int]:
    """Count the modules in every package these files add a module to. Files git ignores, such
    as a generated `_version.py`, are not part of the package's design and don't count."""
    counts = {}
    new = {
        style.package(file.path)
        for file in files
        if file.is_new and style.is_module(file.path, config)
    }
    for name in new:
        listed = git(
            root, "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", name or "."
        )
        children = {
            path
            for path in listed.split("\0")
            if path and style.package(path) == name and (root / path).is_file()
        }
        counts[name] = sum(style.is_module(path, config) for path in children)
    return counts


def _style(
    mine: tuple[FileDiff, ...],
    touched: tuple[FileDiff, ...],
    lengths: dict[str, int],
    modules: dict[str, int],
    config: Config,
) -> str:
    findings = (
        style.banned(mine, config)
        + style.oversized(touched, lengths, config)
        + style.crowded(mine, modules, config)
        + suppressions.unexplained(mine)
    )
    return "Style rules (see CLAUDE.md):\n" + "\n".join(map(str, findings)) if findings else ""


def _secrets(written: tuple[FileDiff, ...]) -> str:
    findings = leaks.leaks(written)
    if not findings:
        return ""
    return "Possible secrets (the text is not repeated here):\n" + "\n".join(map(str, findings))


def own_lines(
    snap: Snapshot, session: state.Session, written: Counter[str], suffixes: tuple[str, ...]
) -> Counter[str]:
    """Added lines this session is answerable for in files with these suffixes: as many copies of
    each as its own edits wrote, less those already there when it started. Another session
    sharing the checkout answers for its own."""
    return (added_lines(snap.files, suffixes) - Counter(session.baseline)) & written


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


def _review_request(
    pending: Counter[str], mine: tuple[FileDiff, ...], crowded: list[str], config: Config
) -> str:
    paths = sorted({key.split("\0", 1)[0] for key in pending})
    notes = style.dense(mine, config)
    lines = [
        f"{sum(pending.values())} added lines have not been independently reviewed "
        f"({', '.join(paths[:8])}{' …' if len(paths) > 8 else ''}).",
        f"Run the `{REVIEWER}` agent. Give it the user's request in their words, the path of any "
        "spec or design doc this work implements, and the evidence (the commands run and their "
        "results); never your own summary or reasons the change is right. Fix what it confirms, "
        "or say in your report why a finding does not apply.",
    ]
    if notes:
        lines.append("Ask it to look hard at these comment-heavy files: " + "; ".join(notes))
    if crowded:
        lines.append(
            "Ask it whether the new modules belong in a subpackage: "
            + "; ".join(crowded)
            + f" already held more than {config.max_modules} modules."
        )
    return "\n".join(lines)


def _mark(result: checks.Result) -> str:
    if result.missing:
        return "– not installed"
    return "✓" if result.passed else "✗"


def _name_missing(missing: list[str], unverified: str) -> str:
    """Ask for the missing checks that the report's `Not verified` part does not name."""
    unnamed = [
        name
        for name in missing
        if not re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", unverified, re.IGNORECASE)
    ]
    if not unnamed:
        return ""
    names = ", ".join(f"`{name}`" for name in unnamed)
    return (
        f"These checks did not run because their tools are not installed: {names}. Install them "
        "and finish again, or name each one in the report's `Not verified:` line."
    )


def _summary(results: list[checks.Result], candidates: list[str], crowded: list[str]) -> str:
    ran = [r for r in results if not r.skipped]
    lines = []
    if ran:
        marks = " · ".join(f"{r.name} {_mark(r)}" for r in ran)
        lines.append(f"devgate: {marks} ({sum(r.seconds for r in ran):.0f}s)")
    if candidates:
        lines.append("devgate: split candidates: " + "; ".join(candidates))
    if crowded:
        lines.append("devgate: crowded packages: " + "; ".join(crowded))
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
    anywhere = own_lines(snap, session, written, EVERY_FILE)
    if snap.fingerprint == session.passed or not anywhere:
        return Decision()
    secrets = _secrets(_own_files(snap, anywhere))
    own = own_lines(snap, session, written, config.review_suffixes)
    if not own:
        return Decision(reason=FIX + secrets) if secrets else Decision()
    mine = _own_files(snap, own)
    paths = {file.path for file in mine}
    touched = tuple(file for file in snap.files if file.path in paths)
    fingerprint = code_fingerprint(touched, config)
    results: list[checks.Result] = []
    if fingerprint != session.checked:
        changed = tuple(sorted(path for path in paths if (root / path).is_file()))
        results = checks.run_all(config.checks, root, changed, config.timeout)
    failed = [r for r in results if not r.passed and not r.missing]
    problems = [f"`{r.name}` failed:\n{leaks.redact(r.output)}" for r in failed]
    lengths = _lengths(root, touched)
    modules = _modules(root, mine, config)
    problems += filter(None, [_style(mine, touched, lengths, modules, config), secrets])
    if problems:
        return Decision(reason=FIX + "\n\n".join(problems))
    # While a tool is missing the checks stay unrecorded: every stop until the report names it,
    # and the first after any later code change, runs them again, so an install is picked up.
    missing = [r.name for r in results if r.missing]
    checked = "" if missing else fingerprint
    # Files already oversized that grew further never block: they go on the split backlog, which
    # every session start shows, and in the notice.
    grown = style.grown(touched, lengths, config)
    state.note_oversized(root, {path: length for path, length, _ in grown})
    candidates = style.growing(touched, lengths, config)
    crowded = style.still_crowded(mine, modules, config)
    if reviewing:
        waiting = f"devgate: `{REVIEWER}` is still running; the report is checked once it is back."
        notice = "\n".join(filter(None, [_summary(results, candidates, crowded), waiting]))
        return Decision(notice=notice, checked=checked, settled=False)
    pending = own - state.reviewed(root)
    if sum(pending.values()) >= config.review_threshold:
        reason = _review_request(pending, mine, crowded, config)
        return Decision(reason=reason, checked=checked)
    evidence = EVIDENCE.search(message)
    if not evidence:
        return Decision(
            reason="The report must end with a `Not verified:` line naming what was not checked "
            "(or `Not verified: nothing`), after the commands run and the requirements covered.",
            checked=checked,
        )
    if unnamed := _name_missing(missing, message[evidence.start() :]):
        return Decision(reason=unnamed)
    return Decision(notice=_summary(results, candidates, crowded), checked=checked)
