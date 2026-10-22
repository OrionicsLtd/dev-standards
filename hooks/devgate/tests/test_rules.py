"""Unit tests for diff parsing and the style rules."""

from devgate.config import Config
from devgate.diff import FileDiff, parse
from devgate.style import banned, dense, growing, oversized, prose

DIFF = """\
diff --git a/pkg/a.py b/pkg/a.py
index 1..2 100644
--- a/pkg/a.py
+++ b/pkg/a.py
@@ -3,0 +4,2 @@ def f():
+    x = 1  # WP3 wiring
+--- not a header
@@ -10 +11,0 @@
--- removed line that looks like a header
diff --git a/new.md b/new.md
new file mode 100644
--- /dev/null
+++ b/new.md
@@ -0,0 +1 @@
+hello
diff --git a/gone.py b/gone.py
--- a/gone.py
+++ /dev/null
@@ -1 +0,0 @@
-x = 1
"""


def _file(path: str, *lines: str, removed: int = 0, new: bool = False) -> FileDiff:
    return FileDiff(path, tuple(enumerate(lines, start=1)), removed, new)


def test_parse_tracks_line_numbers_and_header_lookalikes() -> None:
    files = parse(DIFF)
    assert [f.path for f in files] == ["pkg/a.py", "new.md"]
    assert files[0].added == ((4, "    x = 1  # WP3 wiring"), (5, "--- not a header"))
    assert files[0].removed == 1
    assert files[1].is_new and not files[0].is_new


def test_prose_finds_comments_and_docstrings_but_not_strings() -> None:
    file = _file("m.py", 'url = "http://x#y"', "x = 1  # why", '"""Doc', "body", '"""', "y = 2")
    assert [(n, c) for n, _, c in prose(file)] == [(2, True), (3, False), (4, False), (5, False)]


def test_banned_flags_planning_words_and_banners_only_in_code() -> None:
    files = (
        _file("a.py", "x = 1  # added in Phase 2", "# ---------", "y = 2  # cache keyed by commit"),
        _file("notes.md", "Phase 2 lands next week"),
    )
    found = [(f.path, f.line) for f in banned(files, Config())]
    assert found == [("a.py", 1), ("a.py", 2)]


def test_banner_rule_spares_numpy_docstring_underlines() -> None:
    file = _file("a.py", '"""Summary.', "", "Parameters", "----------", '"""')
    assert banned((file,), Config()) == []


def test_size_blocks_crossing_and_reports_legacy_growth() -> None:
    config = Config(max_lines=100, size_growth=5)
    crossed = _file("crossed.py", *["x"] * 30)
    legacy_edit = _file("big.py", *["x"] * 3)
    legacy_growth = _file("grow.py", *["x"] * 30)
    test_file = _file("tests/test_big.py", *["x"] * 300, new=True)
    files = (crossed, legacy_edit, legacy_growth, test_file)
    lengths = {"crossed.py": 110, "big.py": 500, "grow.py": 500, "tests/test_big.py": 300}
    assert [f.path for f in oversized(files, lengths, config)] == ["crossed.py"]
    assert growing(files, lengths, config) == ["grow.py (500 lines, +30)"]


def test_dense_names_comment_heavy_files() -> None:
    heavy = _file("h.py", *(["# note", "x = 1"] * 12))
    light = _file("l.py", *(["x = 1"] * 24))
    assert [note.split(":")[0] for note in dense((heavy, light), Config())] == ["h.py"]
