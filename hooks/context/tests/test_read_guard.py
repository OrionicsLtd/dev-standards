"""Unit tests for the whole-file read guard, on files in a temp dir."""

from pathlib import Path

import pytest

from context.guard import count_lines, refusal

THRESHOLD = 400


def _file(directory: Path, name: str, lines: int) -> Path:
    path = directory / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"line {n}\n" for n in range(lines)))
    return path


def _read(path: Path | str, cwd: Path, **tool_input: object) -> dict:
    return {
        "cwd": str(cwd),
        "tool_name": "Read",
        "tool_input": {"file_path": str(path), **tool_input},
    }


def test_long_file_whole_read_is_refused(tmp_path: Path) -> None:
    path = _file(tmp_path, "big.py", 401)
    assert refusal(_read(path, tmp_path), THRESHOLD) == (
        "big.py has 401 lines; grep for what you need, then read that slice with offset and "
        "limit. To read it whole on purpose, pass an explicit limit."
    )


def test_read_at_threshold_is_allowed(tmp_path: Path) -> None:
    assert refusal(_read(_file(tmp_path, "a.py", 400), tmp_path), THRESHOLD) is None


@pytest.mark.parametrize("size", [0, 400, 401, 10_000])
@pytest.mark.parametrize("sliced", [{"offset": 1}, {"limit": 50}, {"limit": 5000}])
def test_sliced_reads_are_allowed(tmp_path: Path, size: int, sliced: dict) -> None:
    path = _file(tmp_path, "a.py", size)
    assert refusal(_read(path, tmp_path, **sliced), THRESHOLD) is None


def test_null_offset_is_not_a_slice(tmp_path: Path) -> None:
    path = _file(tmp_path, "a.py", 401)
    assert refusal(_read(path, tmp_path, offset=None, limit=None), THRESHOLD) is not None


def test_other_tools_are_allowed(tmp_path: Path) -> None:
    event = {**_read(_file(tmp_path, "a.py", 1000), tmp_path), "tool_name": "Edit"}
    assert refusal(event, THRESHOLD) is None


def test_subagent_read_is_allowed(tmp_path: Path) -> None:
    event = {**_read(_file(tmp_path, "a.py", 1000), tmp_path), "agent_id": "a1"}
    assert refusal(event, THRESHOLD) is None


@pytest.mark.parametrize(
    "name", ["x.PNG", "x.jpg", "x.jpeg", "x.gif", "x.webp", "x.pdf", "x.ipynb"]
)
def test_special_files_are_allowed(tmp_path: Path, name: str) -> None:
    assert refusal(_read(_file(tmp_path, name, 1000), tmp_path), THRESHOLD) is None


def test_relative_path_resolves_against_cwd(tmp_path: Path) -> None:
    _file(tmp_path, "sub/big.py", 500)
    reason = refusal(_read("sub/big.py", tmp_path), THRESHOLD)
    assert reason is not None and reason.startswith("sub/big.py has 500 lines;")


def test_path_outside_cwd_is_shown_as_given(tmp_path: Path) -> None:
    path = _file(tmp_path / "elsewhere", "big.py", 500)
    (tmp_path / "work").mkdir()
    reason = refusal(_read(path, tmp_path / "work"), THRESHOLD)
    assert reason is not None and reason.startswith(f"{path} has 500 lines;")


def test_symlinked_cwd_still_shows_a_relative_path(tmp_path: Path) -> None:
    _file(tmp_path / "real", "big.py", 500)
    (tmp_path / "link").symlink_to(tmp_path / "real")
    reason = refusal(_read(tmp_path / "real" / "big.py", tmp_path / "link"), THRESHOLD)
    assert reason is not None and reason.startswith("big.py has 500 lines;")


@pytest.mark.parametrize(
    ("content", "expected"),
    [(b"", 0), (b"a", 1), (b"a\n", 1), (b"a\nb", 2), (b"a\n\n", 2), (b"x\x00y\n", None)],
)
def test_count_lines(tmp_path: Path, content: bytes, expected: int | None) -> None:
    path = tmp_path / "f"
    path.write_bytes(content)
    assert count_lines(path) == expected


def test_count_lines_spans_chunks(tmp_path: Path) -> None:
    path = tmp_path / "f"
    path.write_bytes(b"0123456789\n" * 300_000)
    assert count_lines(path) == 300_000


MIB = 1 << 20
NUL_WINDOW = 8192


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (b"x" * (MIB - 1) + b"\n", 1),
        (b"x" * (MIB - 1) + b"\nx", 2),
        (b"a" * (NUL_WINDOW - 1) + b"\x00\n", None),
        (b"a" * NUL_WINDOW + b"\x00\n", 1),
    ],
)
def test_count_lines_chunk_and_nul_boundaries(
    tmp_path: Path, content: bytes, expected: int | None
) -> None:
    path = tmp_path / "f"
    path.write_bytes(content)
    assert count_lines(path) == expected


def test_falsy_agent_id_is_not_a_subagent(tmp_path: Path) -> None:
    event = {**_read(_file(tmp_path, "a.py", 1000), tmp_path), "agent_id": ""}
    assert refusal(event, THRESHOLD) is not None


def test_event_without_keys_is_allowed() -> None:
    assert refusal({}, THRESHOLD) is None


def test_count_lines_of_a_directory_or_missing_file_is_none(tmp_path: Path) -> None:
    assert count_lines(tmp_path) is None
    assert count_lines(tmp_path / "missing") is None


def test_missing_file_is_allowed(tmp_path: Path) -> None:
    assert refusal(_read(tmp_path / "missing.py", tmp_path), THRESHOLD) is None
