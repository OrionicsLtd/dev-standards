"""How full the context window is, read from the session transcript, and the nudge past a limit."""

import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

BLOCK = 64 * 1024
# What the model re-reads on the next request; output tokens are excluded.
USAGE_KEYS = ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
NOTE = (
    "~{k}k tokens in use; if this request is a new task, propose a new session and write the "
    "handoff first."
)


def live_tokens(usage: dict[str, Any]) -> int | None:
    """Tokens of context one request carried, or None when a count is not an integer."""
    values = [usage.get(key, 0) for key in USAGE_KEYS]
    # `type` rather than isinstance: a bool is an int.
    if any(type(value) is not int for value in values):
        return None
    return sum(values)


def _lines_backwards(path: Path) -> Iterator[bytes]:
    """The file's lines, last first, read in blocks so a long session costs no more to scan.
    Bytes are joined before any decoding, so a character split across blocks survives."""
    with path.open("rb") as handle:
        position = handle.seek(0, os.SEEK_END)
        # Pieces of the line being assembled, last piece first; joined once, so a line of many
        # blocks costs no more than its length.
        pieces: list[bytes] = []
        while position > 0:
            step = min(BLOCK, position)
            position -= step
            handle.seek(position)
            parts = handle.read(step).split(b"\n")
            pieces.append(parts[-1])
            if len(parts) > 1:
                yield b"".join(reversed(pieces))
                yield from reversed(parts[1:-1])
                pieces = [parts[0]]
        yield b"".join(reversed(pieces))


def _tokens(entry: Any) -> int | None:
    """The live context of a main-session assistant entry with usable usage, else None."""
    if not isinstance(entry, dict) or entry.get("type") != "assistant":
        return None
    message = entry.get("message")
    if entry.get("isSidechain") is True or not isinstance(message, dict):
        return None
    usage = message.get("usage")
    tokens = live_tokens(usage) if isinstance(usage, dict) else None
    # Synthetic entries, such as API errors, carry zero usage.
    return tokens if tokens is not None and tokens > 0 else None


def _is_compaction(entry: Any) -> bool:
    return (
        isinstance(entry, dict)
        and entry.get("type") == "system"
        and entry.get("subtype") == "compact_boundary"
    )


def last_tokens(transcript: Path) -> int | None:
    """Live context at the session's last model request, or None when unknown. The transcript
    format is internal to Claude Code, so anything unexpected reads as unknown."""
    try:
        for line in _lines_backwards(transcript):
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if _is_compaction(entry):
                # Usage recorded before a compaction no longer describes the window.
                return None
            if (tokens := _tokens(entry)) is not None:
                return tokens
    except OSError:
        return None
    return None


def note(tokens: int, threshold: int) -> str | None:
    """The nudge, once the context holds more than `threshold` tokens."""
    return NOTE.format(k=round(tokens / 1000)) if tokens > threshold else None
