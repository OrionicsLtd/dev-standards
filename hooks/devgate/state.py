"""Gate state, kept inside the repository's git directory so it is never committed.

Reviewed lines are shared by every session in the worktree; the baseline, the lines its edits
wrote, the last passing fingerprint and the block count belong to one session.
"""

import fcntl
import json
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

from .diff import git


@dataclass
class Session:
    """What one session has already been held to."""

    baseline: dict[str, int] = field(default_factory=dict)
    passed: str = ""
    checked: str = ""
    blocks: int = 0


def directory(root: Path) -> Path:
    """Return the gate's state directory for this worktree, creating it if needed."""
    path = Path(git(root, "rev-parse", "--absolute-git-dir").strip()) / "devgate"
    path.mkdir(exist_ok=True)
    return path


def _read(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def load_session(root: Path, session_id: str) -> Session | None:
    """Return the session's state, or None if the gate has not seen this session."""
    data = _read(directory(root) / f"session-{session_id}.json")
    return Session(**data) if data else None


def save_session(root: Path, session_id: str, session: Session) -> None:
    """Persist the session's state."""
    (directory(root) / f"session-{session_id}.json").write_text(json.dumps(asdict(session)))


def reviewed(root: Path) -> Counter[str]:
    """Return the added lines a reviewer has already seen."""
    return Counter(_read(directory(root) / "reviewed.json"))


@contextmanager
def _updating(root: Path, name: str) -> Iterator[dict]:
    """Yield a state file's contents for update, then write them back. Parallel subagents fire their
    hooks concurrently, so the update holds a lock and the write replaces the file atomically."""
    folder = directory(root)
    with (folder / f"{name}.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        data = _read(folder / name)
        yield data
        scratch = folder / f"{name}.tmp"
        scratch.write_text(json.dumps(data))
        scratch.replace(folder / name)


def stamp_reviewed(root: Path, seen: Counter[str], current: Counter[str]) -> None:
    """Add the lines a reviewer saw to the reviewed set, keeping only lines still in the change.
    Reviewers can report out of order, so earlier stamps are kept rather than replaced."""
    with _updating(root, "reviewed.json") as data:
        kept = (Counter(data) | seen) & current
        data.clear()
        data.update(kept)


def record_written(
    root: Path, session_id: str, added: Counter[str], removed: Counter[str] | None = None
) -> None:
    """Count the lines one of the session's own edits added and removed. Parallel tool calls and
    subagents of one session record at the same time."""
    with _updating(root, f"written-{session_id}.json") as data:
        kept = Counter(data) + added - (removed or Counter())
        data.clear()
        data.update(kept)


def written(root: Path, session_id: str) -> Counter[str]:
    """Return how many copies of each line the session's own edits wrote, keyed like
    `diff.line_key`."""
    return Counter(_read(directory(root) / f"written-{session_id}.json"))


def start_review(root: Path, agent_id: str, lines: Counter[str], now: float) -> None:
    """Record the change a background reviewer was launched on."""
    with _updating(root, "reviews.json") as table:
        table[agent_id] = {"started": now, "lines": dict(lines)}


def reviewing(root: Path, now: float, expiry: int) -> bool:
    """Whether a reviewer launched within `expiry` seconds has yet to report."""
    table = _read(directory(root) / "reviews.json")
    return any(now - entry["started"] < expiry for entry in table.values())


def finish_review(root: Path, agent_id: str, now: float, expiry: int) -> Counter[str] | None:
    """Return the lines this reviewer was launched on, if its launch was recorded, and forget
    launches older than `expiry` that never reported."""
    with _updating(root, "reviews.json") as table:
        entry = table.pop(agent_id, None)
        for stale in [key for key, other in table.items() if now - other["started"] >= expiry]:
            del table[stale]
    return Counter(entry["lines"]) if entry else None


def backlog(root: Path) -> dict[str, dict]:
    """Files waiting to be split: path -> {"lines", "since"}."""
    return _read(directory(root) / "oversized.json")


def save_backlog(root: Path, entries: dict[str, dict]) -> None:
    """Replace the split backlog."""
    (directory(root) / "oversized.json").write_text(json.dumps(entries, indent=1, sort_keys=True))


def note_oversized(root: Path, sizes: dict[str, int], today: str | None = None) -> None:
    """Add or refresh oversized files on the split backlog, keeping when each was first seen."""
    if not sizes:
        return
    entries = backlog(root)
    day = today or date.today().isoformat()
    for path, lines in sizes.items():
        entries[path] = {"lines": lines, "since": entries.get(path, {}).get("since", day)}
    save_backlog(root, entries)
