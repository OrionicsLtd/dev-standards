"""Hook entry points: parse the command, read the event from stdin, answer on stdout."""

import json
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from . import guard, nudge

DEFAULT_TOKENS = 300_000
DEFAULT_LINES = 400
# ASCII digits only: int() would also take "+5", "1_000" and other scripts' digits.
NUMBER = re.compile(r"[0-9]+")

Handler = Callable[[dict[str, Any], int], dict[str, Any]]


def _nudge(event: dict[str, Any], threshold: int) -> dict[str, Any]:
    """Tell Claude the context is full once it holds more than `threshold` tokens."""
    transcript = event.get("transcript_path")
    tokens = nudge.last_tokens(Path(transcript)) if transcript else None
    text = nudge.note(tokens, threshold) if tokens is not None else None
    if text is None:
        return {}
    return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": text}}


def _read_guard(event: dict[str, Any], threshold: int) -> dict[str, Any]:
    """Deny a whole read of a text file longer than `threshold` lines."""
    reason = guard.refusal(event, threshold)
    if reason is None:
        return {}
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


COMMANDS: dict[str, tuple[str, int, Handler]] = {
    "nudge": ("--tokens", DEFAULT_TOKENS, _nudge),
    "read-guard": ("--lines", DEFAULT_LINES, _read_guard),
}


def _parse(args: list[str]) -> tuple[Handler, int]:
    """The handler and threshold for `<command> [<flag> N]`; a ValueError for anything else."""
    if not args or args[0] not in COMMANDS:
        given = " ".join(args) or "nothing"
        raise ValueError(f"expected one of {', '.join(COMMANDS)}, got {given}")
    flag, threshold, handler = COMMANDS[args[0]]
    if len(args) == 1:
        return handler, threshold
    if len(args) != 3 or args[1] != flag or not NUMBER.fullmatch(args[2]) or int(args[2]) == 0:
        raise ValueError(f"expected `{args[0]} [{flag} N]`, N a positive integer; got {args[1:]}")
    return handler, int(args[2])


def main(argv: list[str]) -> int:
    """Answer one hook event; never fail the session because the hook itself broke. Exit 2 would
    block the prompt or the tool, so every error ends in exit 0 and a line on stderr."""
    try:
        handler, threshold = _parse(argv[1:])
        reply = handler(json.load(sys.stdin), threshold)
    except Exception as error:  # noqa: BLE001 - a broken hook must not block the prompt or tool
        print(f"context: {type(error).__name__}: {error}", file=sys.stderr)
        return 0
    if reply:
        print(json.dumps(reply))
    return 0
