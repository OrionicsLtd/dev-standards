"""Hook entry points: read the event from stdin, act on the repository, answer on stdout."""

import json
import sys
import time
from collections import Counter
from pathlib import Path

from . import config, gate, state
from .diff import added_lines, find_root, snapshot


def _change(root: Path, settings: config.Config) -> Counter[str]:
    """Added lines of the change as it stands that count toward review."""
    return added_lines(snapshot(root).files, settings.review_suffixes)


def _session_start(root: Path, event: dict) -> dict:
    """Record what was already uncommitted, so the session answers only for its own changes, and
    show the split backlog so oversized files stay in view without blocking any turn."""
    settings = config.load(root)
    if state.load_session(root, event["session_id"]) is None:
        baseline = _change(root, settings)
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


def _review_start(root: Path, event: dict) -> dict:
    """Record the change a background reviewer was launched on, so edits made while it runs stay
    unreviewed. A foreground reviewer holds the session until it reports, so it needs no record."""
    response = event.get("tool_response")
    launched = isinstance(response, dict) and response.get("status") == "async_launched"
    if launched and event.get("tool_input", {}).get("subagent_type") == gate.REVIEWER:
        settings = config.load(root)
        state.start_review(root, response["agentId"], _change(root, settings), time.time())
    return {}


def _subagent_stop(root: Path, event: dict) -> dict:
    """Add the lines the reviewer was given to the reviewed set. A reviewer may end on a tool call
    rather than text, so its final message is not required. Without a launch record (a foreground
    run, or no PostToolUse hook) the change as it stands now is what it saw."""
    if event.get("agent_type") == gate.REVIEWER:
        settings = config.load(root)
        current = _change(root, settings)
        agent_id = event.get("agent_id", "")
        seen = state.finish_review(root, agent_id, time.time(), settings.review_expiry)
        state.stamp_reviewed(root, current if seen is None else seen, current)
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
    message = event.get("last_assistant_message", "")
    reviewing = state.reviewing(root, time.time(), settings.review_expiry)
    decision = gate.evaluate(root, snap, session, settings, message, reviewing)
    session.checked = decision.checked or session.checked
    if decision.reason and session.blocks < settings.max_blocks:
        session.blocks += 1
        state.save_session(root, event["session_id"], session)
        return {"decision": "block", "reason": decision.reason}
    notice = decision.notice
    if decision.reason:
        notice = f"devgate: gave up after {session.blocks} attempts; still open:\n{decision.reason}"
    if decision.settled:
        session.passed, session.blocks = snap.fingerprint, 0
    state.save_session(root, event["session_id"], session)
    return {"systemMessage": notice} if notice else {}


HANDLERS = {
    "stop": _stop,
    "session-start": _session_start,
    "review-start": _review_start,
    "subagent-stop": _subagent_stop,
}


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
