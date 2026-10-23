"""Hook entry points: read the event from stdin, act on the repository, answer on stdout."""

import json
import sys
from pathlib import Path

from . import config, gate, state
from .diff import added_lines, find_root, snapshot


def _session_start(root: Path, event: dict) -> dict:
    """Record what was already uncommitted, so the session answers only for its own changes, and
    show the split backlog so oversized files stay in view without blocking any turn."""
    settings = config.load(root)
    if state.load_session(root, event["session_id"]) is None:
        baseline = added_lines(snapshot(root).files, settings.review_suffixes)
        state.save_session(root, event["session_id"], state.Session(baseline=dict(baseline)))
    backlog = _current_backlog(root, settings.max_lines)
    if not backlog:
        return {}
    listed = "; ".join(f"{path} ({e['lines']} lines, since {e['since']})" for path, e in backlog)
    note = (
        f"devgate split backlog -- over {settings.max_lines} lines and still growing; split one "
        f"before adding to it: {listed}"
    )
    return {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": note}}


def _current_backlog(root: Path, max_lines: int) -> list[tuple[str, dict]]:
    """The backlog less files that were split or removed since, with their current lengths."""
    entries: dict[str, dict] = {}
    for path, entry in state.backlog(root).items():
        try:
            lines = len((root / path).read_text().splitlines())
        except (OSError, UnicodeDecodeError):
            continue
        if lines > max_lines:
            entries[path] = {**entry, "lines": lines}
    state.save_backlog(root, entries)
    return sorted(entries.items(), key=lambda kv: -kv[1]["lines"])


def _subagent_stop(root: Path, event: dict) -> dict:
    """Mark the current change as reviewed once the reviewer has reported."""
    if event.get("agent_type") == gate.REVIEWER and event.get("last_assistant_message"):
        settings = config.load(root)
        state.save_reviewed(root, added_lines(snapshot(root).files, settings.review_suffixes))
    return {}


def _stop(root: Path, event: dict) -> dict:
    """Block the stop while checks fail, review is missing or the report lacks its evidence."""
    settings = config.load(root)
    if not settings.enabled:
        return {}
    snap = snapshot(root)
    session = state.load_session(root, event["session_id"])
    if session is None:
        # A session the gate never saw start: adopt its current change rather than judge it.
        baseline = dict(added_lines(snap.files, settings.review_suffixes))
        state.save_session(root, event["session_id"], state.Session(baseline, snap.fingerprint))
        return {}
    decision = gate.evaluate(root, snap, session, settings, event.get("last_assistant_message", ""))
    session.checked = decision.checked or session.checked
    if decision.reason and session.blocks < settings.max_blocks:
        session.blocks += 1
        state.save_session(root, event["session_id"], session)
        return {"decision": "block", "reason": decision.reason}
    notice = decision.notice
    if decision.reason:
        notice = f"devgate: gave up after {session.blocks} attempts; still open:\n{decision.reason}"
    session.passed, session.blocks = snap.fingerprint, 0
    state.save_session(root, event["session_id"], session)
    return {"systemMessage": notice} if notice else {}


HANDLERS = {"stop": _stop, "session-start": _session_start, "subagent-stop": _subagent_stop}


def main(argv: list[str]) -> int:
    """Dispatch one hook event; never fail the session because the gate itself broke."""
    try:
        event = json.load(sys.stdin)
        root = find_root(Path(event.get("cwd") or "."))
        if root is None:
            return 0
        reply = HANDLERS[argv[1]](root, event)
    except Exception as error:  # noqa: BLE001 - a broken gate must not wedge the session
        print(f"devgate: {type(error).__name__}: {error}", file=sys.stderr)
        return 0
    if reply:
        print(json.dumps(reply))
    return 0
