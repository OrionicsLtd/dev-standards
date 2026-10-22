"""Style rules on the lines a change adds: banned comment wording, file growth, comment density."""

import re
from dataclasses import dataclass
from fnmatch import fnmatch

from .config import Config
from .diff import FileDiff

COMMENT_MARKERS = {".py": "#", ".pyi": "#", ".sh": "#", ".toml": "#", ".yaml": "#", ".yml": "#"}
DEFAULT_MARKER = "//"
DOCSTRING = re.compile(r'"""|\'\'\'')
BANNER = re.compile(r"^\s*[-=*#~]{4,}")
DENSITY_MIN_LINES = 20
DENSITY_LIMIT = 0.3


@dataclass(frozen=True)
class Finding:
    """One rule a file breaks, located well enough to fix without searching."""

    path: str
    line: int
    message: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.message}"


def _comment(text: str, marker: str) -> str | None:
    """Return the comment part of a source line, ignoring markers inside string literals."""
    quote = ""
    for index, char in enumerate(text):
        if quote:
            quote = "" if char == quote and text[index - 1] != "\\" else quote
        elif char in "\"'`":
            quote = char
        elif text.startswith(marker, index):
            return text[index + len(marker) :]
    return None


def prose(file: FileDiff) -> list[tuple[int, str, bool]]:
    """Return (line, text, is_comment) for every added comment and docstring line."""
    marker = COMMENT_MARKERS.get("." + file.path.rsplit(".", 1)[-1], DEFAULT_MARKER)
    in_docstring, found = False, []
    for line_no, text in file.added:
        quotes = len(DOCSTRING.findall(text)) if file.path.endswith((".py", ".pyi")) else 0
        if in_docstring or quotes:
            found.append((line_no, text, False))
            in_docstring = in_docstring != (quotes % 2 == 1)
            continue
        comment = _comment(text, marker)
        if comment is not None:
            found.append((line_no, comment, True))
    return found


def banned(files: tuple[FileDiff, ...], config: Config) -> list[Finding]:
    """Flag banner comments, and comments or docstrings using planning or conversation wording."""
    patterns = [re.compile(pattern, re.IGNORECASE) for pattern in config.banned]
    findings = []
    for file in files:
        if not file.path.endswith(config.code_suffixes):
            continue
        for line_no, text, is_comment in prose(file):
            subject = text.strip()
            if is_comment and BANNER.match(subject):
                findings.append(Finding(file.path, line_no, "section-banner comment"))
            elif any(pattern.search(subject) for pattern in patterns):
                findings.append(Finding(file.path, line_no, f"comment wording `{subject[:60]}`"))
    return findings


def _sizes(
    files: tuple[FileDiff, ...], lengths: dict[str, int], config: Config
) -> list[tuple[str, int, int]]:
    """Return (path, length, growth) for every non-exempt code file now over the size limit."""
    sizes = []
    for file in files:
        length = lengths.get(file.path, 0)
        exempt = any(fnmatch(file.path, glob) for glob in config.size_exempt)
        if not exempt and file.path.endswith(config.code_suffixes) and length > config.max_lines:
            sizes.append((file.path, length, len(file.added) - file.removed))
    return sizes


def oversized(
    files: tuple[FileDiff, ...], lengths: dict[str, int], config: Config
) -> list[Finding]:
    """Flag code files this change pushed over the size limit."""
    return [
        Finding(path, 1, f"{length} lines; split it along its seams")
        for path, length, growth in _sizes(files, lengths, config)
        if length - growth <= config.max_lines
    ]


def growing(files: tuple[FileDiff, ...], lengths: dict[str, int], config: Config) -> list[str]:
    """Name files already over the limit that this change grew further, as split candidates."""
    return [
        f"{path} ({length} lines, +{growth})"
        for path, length, growth in _sizes(files, lengths, config)
        if length - growth > config.max_lines and growth > config.size_growth
    ]


def dense(files: tuple[FileDiff, ...], config: Config) -> list[str]:
    """Name files whose added lines are unusually comment-heavy, for the reviewer to judge."""
    notes = []
    for file in files:
        if not file.path.endswith(config.code_suffixes) or len(file.added) < DENSITY_MIN_LINES:
            continue
        comments = sum(1 for _, _, is_comment in prose(file) if is_comment)
        ratio = comments / len(file.added)
        if ratio > DENSITY_LIMIT:
            notes.append(f"{file.path}: {comments} of {len(file.added)} added lines are comments")
    return notes
