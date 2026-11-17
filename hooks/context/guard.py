"""Refuse a whole read of a long text file, pointing at grep and a sliced read instead."""

from pathlib import Path
from typing import Any

# Read returns these as images, rendered pages or notebook cells: line counts mean nothing.
SPECIAL_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".ipynb")
# As in git, a NUL byte near the start marks a file as binary.
BINARY_PROBE = 8192
CHUNK = 1 << 20
REASON = (
    "{path} has {lines} lines; grep for what you need, then read that slice with offset and "
    "limit. To read it whole on purpose, pass an explicit limit."
)


def count_lines(path: Path) -> int | None:
    """Lines in a text file, streamed; None for a binary, missing or unreadable path."""
    try:
        with path.open("rb") as handle:
            head = handle.read(BINARY_PROBE)
            if b"\0" in head:
                return None
            lines, last = head.count(b"\n"), head[-1:]
            while chunk := handle.read(CHUNK):
                lines += chunk.count(b"\n")
                last = chunk[-1:]
    except OSError:
        return None
    return lines + (1 if last not in (b"", b"\n") else 0)


def _shown(path: Path, file_path: str, cwd: Path) -> str:
    try:
        return path.resolve().relative_to(cwd.resolve()).as_posix()
    except ValueError:
        return file_path


def refusal(event: dict[str, Any], threshold: int) -> str | None:
    """Why this Read is refused, or None to let it run. Subagents are never refused: their context
    is thrown away when they finish."""
    tool_input = event.get("tool_input") or {}
    if event.get("tool_name") != "Read" or event.get("agent_id"):
        return None
    if tool_input.get("offset") is not None or tool_input.get("limit") is not None:
        return None
    file_path = tool_input.get("file_path")
    if not file_path or file_path.lower().endswith(SPECIAL_SUFFIXES):
        return None
    cwd = Path(event.get("cwd") or ".")
    path = cwd / file_path
    lines = count_lines(path)
    if lines is None or lines <= threshold:
        return None
    return REASON.format(path=_shown(path, file_path, cwd), lines=lines)
