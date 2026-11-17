"""Suppressions on the lines a change adds must name the rule they silence and say why."""

import re
from collections.abc import Iterator
from dataclasses import dataclass

from .diff import FileDiff
from .findings import Finding

PYTHON = (".py", ".pyi")
MAX_CALL_LINES = 20
# Each group names the rule in EXPLAINED; spellings follow what each tool accepts.
COMMENT_FORM = re.compile(
    r"#\s*(?:(?P<noqa>(?:(?:ruff|flake8):\s*)?noqa)|(?P<type>type:\s*ignore)"
    r"|(?P<pyright>pyright:\s*ignore)|(?P<pragma>pragma[:\s]?\s*no\s*(?:cover|branch)))\b",
    re.IGNORECASE,
)
SEPARATOR = r"\s*[-–—:#]\s*"
NOQA_CODES = r"[A-Z]+[0-9]+(?:[\s,]+[A-Z]+[0-9]+)*"
# What must follow each comment form, ending at the start of its reason.
EXPLAINED = {
    "noqa": re.compile(rf":\s*{NOQA_CODES}{SEPARATOR}"),
    "type": re.compile(r"\[\s*[^\]\s][^\]]*\]\s*#\s*"),
    "pyright": re.compile(rf"\[\s*[^\]\s][^\]]*\]{SEPARATOR}"),
    "pragma": re.compile(SEPARATOR),
}
PYTEST_FORM = re.compile(
    r"(?:\bpytest\.)?\bmark\.(?:skipif|skip|xfail)\b|\bpytest\.(?:skip|xfail)\b"
)
KEYWORD = re.compile(r"^\s*(\w+)\s*=(?!=)")
STRING = re.compile(r"^[rRbBuUfF]{0,2}(\"\"\"|'''|\"|')(.*)\1$", re.DOTALL)
LETTER = re.compile(r"[^\W\d_]")


@dataclass(frozen=True)
class Line:
    """One added line split for matching: its code with string contents blanked, and comment."""

    number: int
    code: str
    blanked: str
    comment: str | None


def split(text: str, open_quote: str = "") -> tuple[str, str | None, str]:
    """Return the code with string contents blanked (same length), the comment, and the triple
    quote still open at the end of the line."""
    blanked, quote, index = [], open_quote, 0
    while index < len(text):
        char = text[index]
        if quote and char == "\\":
            step = min(2, len(text) - index)
            blanked.append(" " * step)
            index += step
        elif quote and text.startswith(quote, index):
            blanked.append(quote)
            index, quote = index + len(quote), ""
        elif quote:
            blanked.append(" ")
            index += 1
        elif char == "#":
            return "".join(blanked), text[index + 1 :], ""
        elif char in "\"'":
            quote = char * 3 if text.startswith(char * 3, index) else char
            blanked.append(quote)
            index += len(quote)
        else:
            blanked.append(char)
            index += 1
    return "".join(blanked), None, quote if len(quote) == 3 else ""


def _lines(file: FileDiff) -> list[Line]:
    lines, quote, previous = [], "", None
    for number, text in file.added:
        if previous is not None and number != previous + 1:
            # Lines between hunks are unseen; assume they closed any open string.
            quote = ""
        blanked, comment, quote = split(text, quote)
        lines.append(Line(number, text[: len(blanked)], blanked, comment))
        previous = number
    return lines


def _has_reason(value: str) -> bool:
    """A reason is a non-empty expression; a string literal must say something."""
    value = value.strip()
    if not value or value == "None":
        return False
    literal = STRING.match(value)
    return bool(LETTER.search(literal.group(2))) if literal else True


def _comment_findings(line: Line) -> Iterator[str]:
    for match in COMMENT_FORM.finditer("#" + (line.comment or "")):
        key, text = next((key, text) for key, text in match.groupdict().items() if text)
        form = " ".join(text.lower().split())
        rest = match.string[match.end() :]
        explained = EXPLAINED[key].match(rest)
        if not explained or not LETTER.search(rest[explained.end() :]):
            needs = "a reason" if key == "pragma" else "the rule code and a reason"
            yield f"{form} needs {needs} on the same line"


def _arguments(lines: list[Line], start: int, column: int) -> list[str] | None:
    """Top-level arguments of the call whose `(` may follow `column` on `lines[start]`, read
    across consecutive added lines; None when no call follows."""
    window = []
    for line in lines[start : start + MAX_CALL_LINES]:
        if window and line.number != window[-1].number + 1:
            break
        window.append(line)
    code = "\n".join(line.code for line in window)
    blanked = "\n".join(line.blanked for line in window)
    after = blanked[column:]
    if not after.lstrip(" \t").startswith("("):
        return None
    begin = column + len(after) - len(after.lstrip(" \t")) + 1
    depth, arguments, last = 1, [], begin
    for index in range(begin, len(blanked)):
        char = blanked[index]
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
            if depth == 0:
                arguments.append(code[last:index])
                return [argument for argument in arguments if argument.strip()]
        elif char == "," and depth == 1:
            arguments.append(code[last:index])
            last = index + 1
    arguments.append(code[last:])
    return [argument for argument in arguments if argument.strip()]


def _explained_call(form: str, arguments: list[str] | None) -> bool:
    if not arguments:
        return False
    for position, argument in enumerate(arguments):
        keyword = KEYWORD.match(argument)
        if keyword and keyword.group(1) == "reason":
            return _has_reason(argument[keyword.end() :])
        if not keyword and position == 0 and "mark." not in form:
            return _has_reason(argument)
    return False


def _pytest_findings(lines: list[Line], start: int) -> Iterator[str]:
    for match in PYTEST_FORM.finditer(lines[start].blanked):
        form = match.group()
        if not _explained_call(form, _arguments(lines, start, match.end())):
            yield f"{form} needs a reason"


def unexplained(files: tuple[FileDiff, ...]) -> list[Finding]:
    """Flag suppressions added without the rule they silence and a reason on the same line."""
    findings = []
    for file in files:
        if not file.path.endswith(PYTHON):
            continue
        lines = _lines(file)
        for index, line in enumerate(lines):
            messages = [*_comment_findings(line), *_pytest_findings(lines, index)]
            findings += [Finding(file.path, line.number, message) for message in messages]
    return findings
