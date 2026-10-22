"""Gate state, kept inside the repository's git directory so it is never committed.

Reviewed lines are shared by every session in the worktree; the baseline, the last passing
fingerprint and the block count belong to one session.
"""

import json
from collections import Counter
from dataclasses import asdict, dataclass, field
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


def save_reviewed(root: Path, lines: Counter[str]) -> None:
    """Record the added lines a reviewer has just seen."""
    (directory(root) / "reviewed.json").write_text(json.dumps(dict(lines)))
