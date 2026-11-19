"""Style rules on what a change adds: banned comment wording, file growth, crowded packages and
comment density."""

import re
from collections import Counter
from fnmatch import fnmatch

from . import leaks
from .config import Config
from .diff import FileDiff
from .findings import Finding

COMMENT_MARKERS = {".py": "#", ".pyi": "#", ".sh": "#", ".toml": "#", ".yaml": "#", ".yml": "#"}
DEFAULT_MARKER = "//"
DOCSTRING = re.compile(r'"""|\'\'\'')
BANNER = re.compile(r"^\s*[-=*#~]{4,}")
DENSITY_MIN_LINES = 20
DENSITY_LIMIT = 0.3
HIDDEN = "comment wording (not shown: the line holds a possible secret)"


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
                shown = HIDDEN if leaks.kinds(subject) else f"comment wording `{subject[:60]}`"
                findings.append(Finding(file.path, line_no, shown))
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


def grown(
    files: tuple[FileDiff, ...], lengths: dict[str, int], config: Config
) -> list[tuple[str, int, int]]:
    """Files already over the limit that this change grew further: (path, lines, growth)."""
    return [
        (path, length, growth)
        for path, length, growth in _sizes(files, lengths, config)
        if length - growth > config.max_lines and growth > config.size_growth
    ]


def growing(files: tuple[FileDiff, ...], lengths: dict[str, int], config: Config) -> list[str]:
    """Name files already over the limit that this change grew further, as split candidates."""
    return [
        f"{path} ({length} lines, +{growth})"
        for path, length, growth in grown(files, lengths, config)
    ]


def package(path: str) -> str:
    """Return the directory holding `path`, "" for the repository root."""
    return path.rpartition("/")[0]


def is_module(path: str, config: Config) -> bool:
    """Whether `path` counts toward its package's module limit: a code file the size limits do not
    exempt, other than an `__init__`."""
    exempt = any(fnmatch(path, glob) for glob in config.size_exempt)
    is_init = path.rpartition("/")[2].startswith("__init__.")
    return path.endswith(config.code_suffixes) and not exempt and not is_init


def _crowding(
    files: tuple[FileDiff, ...], modules: dict[str, int], config: Config
) -> list[tuple[str, str, int, int]]:
    """Return (package, first new module, modules, added) for every package this change added
    modules to that now holds more than the limit."""
    added: Counter[str] = Counter()
    first: dict[str, str] = {}
    for file in files:
        if file.is_new and is_module(file.path, config):
            added[package(file.path)] += 1
            first.setdefault(package(file.path), file.path)
    return [
        (name, first[name], modules[name], count)
        for name, count in sorted(added.items())
        if modules.get(name, 0) > config.max_modules
    ]


def crowded(files: tuple[FileDiff, ...], modules: dict[str, int], config: Config) -> list[Finding]:
    """Flag packages this change pushed over the module limit."""
    return [
        Finding(
            path,
            1,
            f"{name or '.'}/ now holds {count} modules (limit {config.max_modules}); "
            "group related modules into a subpackage",
        )
        for name, path, count, added in _crowding(files, modules, config)
        if count - added <= config.max_modules
    ]


def still_crowded(
    files: tuple[FileDiff, ...], modules: dict[str, int], config: Config
) -> list[str]:
    """Name packages already over the module limit that this change added modules to."""
    return [
        f"{name or '.'}/ ({count} modules, +{added})"
        for name, _, count, added in _crowding(files, modules, config)
        if count - added > config.max_modules
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
