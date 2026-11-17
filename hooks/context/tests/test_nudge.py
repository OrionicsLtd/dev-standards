"""Unit tests for reading the live context size from a transcript and phrasing the nudge."""

import json
from pathlib import Path

import pytest

from context.nudge import BLOCK, last_tokens, live_tokens, note

BIG = {"input_tokens": 2, "cache_read_input_tokens": 244906, "cache_creation_input_tokens": 3363}
TOTAL = 2 + 244906 + 3363


def _entry(usage: object, kind: str = "assistant", sidechain: bool = False) -> dict:
    return {"type": kind, "isSidechain": sidechain, "message": {"usage": usage}}


def _user(text: str) -> dict:
    return {"type": "user", "message": {"role": "user", "content": text}}


def _dumps(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def _transcript(tmp_path: Path, *lines: object) -> Path:
    path = tmp_path / "t.jsonl"
    path.write_text(
        "".join((line if isinstance(line, str) else _dumps(line)) + "\n" for line in lines)
    )
    return path


def test_live_tokens_sums_input_and_cache() -> None:
    usage = {**BIG, "output_tokens": 1693}
    assert live_tokens(usage) == TOTAL


def test_live_tokens_counts_missing_keys_as_zero() -> None:
    assert live_tokens({"input_tokens": 5}) == 5


@pytest.mark.parametrize(
    "usage",
    [{"input_tokens": None}, {"input_tokens": "5"}, {"cache_read_input_tokens": True}],
)
def test_live_tokens_rejects_malformed_values(usage: dict) -> None:
    assert live_tokens(usage) is None


def test_last_tokens_skips_sidechain_zero_and_malformed_entries(tmp_path: Path) -> None:
    path = _transcript(
        tmp_path,
        _entry(BIG),
        _entry({"input_tokens": 7}, sidechain=True),
        _entry({"input_tokens": 0, "output_tokens": 0}),
        _entry({"input_tokens": "x"}),
        _entry({"input_tokens": -5}),
        {"type": "user", "subtype": "compact_boundary"},
        {"type": "assistant", "message": "not a dict"},
        [1, 2, 3],
        _user("hi"),
    )
    assert last_tokens(path) == TOTAL


def test_last_tokens_stops_at_a_compaction(tmp_path: Path) -> None:
    boundary = {"type": "system", "subtype": "compact_boundary"}
    path = _transcript(tmp_path, _entry(BIG), boundary, _user("summary"), _user("next"))
    assert last_tokens(path) is None


def test_last_tokens_reassembles_lines_longer_than_a_block(tmp_path: Path) -> None:
    path = _transcript(
        tmp_path,
        _user("a" * 200_000),
        _entry(BIG),
        _user("b" * 300_000),
        "{not json",
    )
    assert last_tokens(path) == TOTAL


def test_last_tokens_reads_an_entry_split_across_blocks(tmp_path: Path) -> None:
    entry = {**_entry(BIG), "note": "café ü — " * 20}
    encoded = len((_dumps(entry) + "\n").encode())
    # The trailing line ends the file, so the 64 KiB block boundary falls mid-entry.
    tail = _user("p" * (BLOCK - encoded // 2 - 60))
    path = _transcript(tmp_path, _user("start"), entry, tail)
    entry_end = path.stat().st_size - len((_dumps(tail) + "\n").encode())
    assert entry_end - encoded < path.stat().st_size - BLOCK < entry_end
    assert last_tokens(path) == TOTAL


@pytest.mark.parametrize("lines", [(), (_user("only a prompt"),)])
def test_last_tokens_without_entries_is_none(tmp_path: Path, lines: tuple) -> None:
    assert last_tokens(_transcript(tmp_path, *lines)) is None


def test_last_tokens_of_a_missing_file_is_none(tmp_path: Path) -> None:
    assert last_tokens(tmp_path / "missing.jsonl") is None


@pytest.mark.parametrize(
    ("tokens", "expected"),
    [
        (300_000, None),
        (299_999, None),
        (300_001, "~300k"),
        (312_500, "~312k"),
        (313_500, "~314k"),
    ],
)
def test_note_only_above_threshold(tokens: int, expected: str | None) -> None:
    text = note(tokens, 300_000)
    if expected is None:
        assert text is None
    else:
        assert text == (
            f"{expected} tokens in use; if this request is a new task, propose a new session "
            "and write the handoff first."
        )
