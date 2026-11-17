"""Unit tests for the rule that every suppression names its rule and gives a reason."""

from pathlib import Path

import pytest

from devgate.diff import FileDiff
from devgate.suppressions import unexplained

PACKAGE = Path(__file__).resolve().parents[1]


def _file(path: str, *lines: str) -> FileDiff:
    return FileDiff(path, tuple(enumerate(lines, start=1)), 0, True)


def _flagged(*lines: str, path: str = "a.py") -> list[int]:
    return [finding.line for finding in unexplained((_file(path, *lines),))]


@pytest.mark.parametrize(
    "line",
    [
        "x = 1  # noqa",
        "import y  # noqa: E402",
        "import y  # noqa: E402 -",
        "import y  # noqa: E402 - 42",
        "import y  # NOQA:E1",
        "import y  # noqa: e501 - why",
        "x = f()  # type: ignore",
        "x = f()  # type: ignore  # why",
        "x = f()  # type: ignore[arg-type]",
        "x = f()  # type: ignore[arg-type] - why",
        "x = f()  # type: ignore[] # why",
        "x = f()  # pyright: ignore",
        "x = f()  # pyright: ignore - why",
        "x = f()  # type:ignore",
        "x = f()  # pyright:ignore",
        "if win:  # pragma no cover",
        "if win:  # pragma:nocover",
        "if win:  # PRAGMA: NO COVER",
        "if win:  # pragma: no cover",
        "if win:  # pragma: no branch",
        "# ruff: noqa",
        "# ruff: noqa: E501",
        "# flake8: noqa",
    ],
)
def test_comment_suppression_without_code_or_reason_blocks(line: str) -> None:
    assert _flagged(line) == [1]


@pytest.mark.parametrize(
    "line",
    [
        "except Exception:  # noqa: BLE001 - a broken gate",
        "except Exception:  # NOQA: BLE001 - a broken gate",
        "import y  # noqa: E402, F401 — path setup",
        "import y  # noqa: E402 F401 - path setup",
        "URL = 'x'  # noqa: E501: long url",
        "URL = 'x'  # noqa: E501  # long url",
        "x = f()  # type: ignore[arg-type]  # stub is wrong",
        "x = o._p  # pyright: ignore[reportPrivateUsage] - test reaches in",
        "if win:  # pragma: no cover - platform branch",
        "if win:  # pragma no cover - platform branch",
        "x = f()  # type:ignore[arg-type]  # stub is wrong",
        "x = o._p  # pyright:ignore[reportPrivateUsage] - test reaches in",
        "# ruff: noqa: E501 - generated table",
        "x = 1  # plain comment",
    ],
)
def test_comment_suppression_with_code_and_reason_passes(line: str) -> None:
    assert _flagged(line) == []


@pytest.mark.parametrize(
    "line",
    [
        "@pytest.mark.skip",
        "@pytest.mark.skip()",
        '@pytest.mark.skip("why")',
        "@mark.xfail(strict=True)",
        '@pytest.mark.skipif(sys.platform == "win32")',
        '@pytest.mark.xfail(reason="")',
        "@pytest.mark.xfail(reason=None)",
        "pytestmark = pytest.mark.skip",
        '@pytest.mark.skipif(f(reason="x"))',
    ],
)
def test_pytest_mark_without_reason_blocks(line: str) -> None:
    assert _flagged(line, path="tests/test_a.py") == [1]


@pytest.mark.parametrize(
    "line",
    [
        '@pytest.mark.skip(reason="flaky upstream")',
        "@pytest.mark.xfail(strict=True, reason='bug 12')",
        "@pytest.mark.skipif(cond, reason=WHY)",
        "x = mark.skipped_x",
    ],
)
def test_pytest_mark_with_reason_passes(line: str) -> None:
    assert _flagged(line, path="tests/test_a.py") == []


@pytest.mark.parametrize(
    ("line", "blocks"),
    [
        ("    pytest.skip()", True),
        ('    pytest.xfail("")', True),
        ('    pytest.skip("no network")', False),
        ('    pytest.xfail(reason="known bug")', False),
    ],
)
def test_imperative_skip_needs_a_message(line: str, blocks: bool) -> None:
    assert _flagged(line, path="tests/test_a.py") == ([1] if blocks else [])


def test_wrapped_mark_is_judged_whole() -> None:
    assert _flagged("@pytest.mark.skip(", '    reason="slow",', ")") == []
    assert _flagged("x = 1", "@pytest.mark.xfail(", "    strict=True,", ")") == [2]
    assert _flagged("@pytest.mark.skip(", '    reason="a)b",', ")") == []
    assert _flagged("@pytest.mark.skip(", '    reason="slow",') == []


def test_wrapped_mark_is_read_for_at_most_twenty_lines() -> None:
    filler = ["    1,"] * 20
    assert _flagged("@pytest.mark.skip(", *filler[:18], '    reason="slow",', ")") == []
    assert _flagged("@pytest.mark.skip(", *filler, '    reason="slow",', ")") == [1]


def test_markers_in_strings_and_docstrings_are_ignored() -> None:
    lines = (
        's = "x  # noqa"',
        "t = '@pytest.mark.skip'",
        'u = "a\\\\" + "# noqa"',
        'DOC = """',
        "x = f()  # type: ignore",
        '"""',
    )
    assert _flagged(*lines) == []
    assert _flagged('x = """a"""  # noqa') == [1]
    assert _flagged("s = 'unterminated", "import y  # noqa") == [2]


def test_a_string_open_at_a_hunk_end_does_not_hide_the_next_hunk() -> None:
    file = FileDiff("a.py", ((1, 'DOC = """'), (5, "import y  # noqa")), 0, False)
    assert [finding.line for finding in unexplained((file,))] == [5]


def test_finding_names_the_form_and_location() -> None:
    (finding,) = unexplained((_file("a.py", "x = 1", "y = 2", "import z  # noqa"),))
    assert str(finding) == "a.py:3: noqa needs the rule code and a reason on the same line"
    (mark,) = unexplained((_file("t.py", "@pytest.mark.skip"),))
    assert str(mark) == "t.py:1: pytest.mark.skip needs a reason"


def test_devgate_package_has_no_unexplained_suppressions() -> None:
    files = tuple(
        _file(str(path), *path.read_text().splitlines()) for path in PACKAGE.rglob("*.py")
    )
    assert files
    assert unexplained(files) == []


def test_suppressions_only_checked_in_python() -> None:
    for path in ("x.js", "x.md", "x.sh"):
        assert _flagged("x = 1  # noqa", path=path) == []
