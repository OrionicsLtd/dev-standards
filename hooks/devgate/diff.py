"""Working-tree diff against HEAD, parsed into the lines each file adds."""

import hashlib
import re
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")
MAX_UNTRACKED_BYTES = 1_000_000


@dataclass(frozen=True)
class FileDiff:
    """Lines one file adds (with their new line numbers) and how many it removes."""

    path: str
    added: tuple[tuple[int, str], ...]
    removed: int
    is_new: bool


@dataclass(frozen=True)
class Snapshot:
    """The whole uncommitted change, with a fingerprint that changes whenever it does."""

    files: tuple[FileDiff, ...]
    fingerprint: str


def git(root: Path, *args: str) -> str:
    """Run a git command in `root` and return its stdout."""
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True)
    return result.stdout


def find_root(cwd: Path) -> Path | None:
    """Return the repository root containing `cwd`, or None outside a repository."""
    try:
        return Path(git(cwd, "rev-parse", "--show-toplevel").strip())
    except (subprocess.CalledProcessError, FileNotFoundError, NotADirectoryError):
        return None


def parse(text: str) -> list[FileDiff]:
    """Parse `git diff -U0` output into per-file added lines."""
    files: list[FileDiff] = []
    path, added, removed, is_new, in_hunk, line_no = "", [], 0, False, False, 0

    def flush() -> None:
        if path:
            files.append(FileDiff(path, tuple(added), removed, is_new))

    for line in text.splitlines():
        if line.startswith("diff --git "):
            flush()
            path, added, removed, is_new, in_hunk = "", [], 0, False, False
        elif not in_hunk and line.startswith("--- "):
            is_new = line == "--- /dev/null"
        elif not in_hunk and line.startswith("+++ "):
            # A deleted file's new side is /dev/null; it adds nothing worth tracking.
            path = "" if line == "+++ /dev/null" else line[6:]
        elif match := HUNK.match(line):
            in_hunk, line_no = True, int(match.group(1))
        elif in_hunk and line.startswith("+"):
            added.append((line_no, line[1:]))
            line_no += 1
        elif in_hunk and line.startswith("-"):
            removed += 1
    flush()
    return files


def _untracked(root: Path) -> list[FileDiff]:
    """Treat every untracked, non-ignored text file as entirely added."""
    names = git(root, "ls-files", "--others", "--exclude-standard", "-z").split("\0")
    files = []
    for name in filter(None, names):
        target = root / name
        if not target.is_file() or target.stat().st_size > MAX_UNTRACKED_BYTES:
            continue
        try:
            lines = target.read_text().splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        files.append(FileDiff(name, tuple(enumerate(lines, start=1)), 0, True))
    return files


def snapshot(root: Path) -> Snapshot:
    """Capture tracked changes against HEAD plus untracked files."""
    try:
        tracked = git(root, "diff", "HEAD", "-U0", "--no-color", "--no-ext-diff", "--no-renames")
    except subprocess.CalledProcessError:
        tracked = ""  # no commits yet: everything is untracked
    files = parse(tracked) + _untracked(root)
    digest = hashlib.sha256(tracked.encode())
    for file in files:
        if file.is_new and not file.removed:
            digest.update(file.path.encode())
            digest.update("\n".join(text for _, text in file.added).encode())
    return Snapshot(tuple(files), digest.hexdigest())


def added_lines(files: tuple[FileDiff, ...], suffixes: tuple[str, ...]) -> Counter[str]:
    """Count non-blank added lines, keyed by path and content, in files with these suffixes."""
    return Counter(
        f"{file.path}\0{text.strip()}"
        for file in files
        if file.path.endswith(suffixes)
        for _, text in file.added
        if text.strip()
    )
