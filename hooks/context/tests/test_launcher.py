"""Integration tests: both hooks run through the launcher as Claude Code runs them, on hook-input
fixtures built from the documented schema with tmp paths filled in."""

import json
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parents[2]
LAUNCHER = HOOKS / "run_context.py"
FIXTURES = Path(__file__).parent / "fixtures"
SETTINGS = HOOKS.parent / "settings.example.json"
NUDGE = (
    "~248k tokens in use; if this request is a new task, propose a new session and write the "
    "handoff first."
)


def _fixture(name: str, **paths: Path) -> str:
    text = (FIXTURES / name).read_text()
    for key, value in paths.items():
        text = text.replace("{" + key + "}", str(value))
    return text


def _run(stdin: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", str(LAUNCHER), *args],
        input=stdin,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _reply(stdin: str, *args: str) -> dict:
    done = _run(stdin, *args)
    assert done.returncode == 0 and done.stderr == ""
    return json.loads(done.stdout) if done.stdout else {}


def _long_file(directory: Path, lines: int) -> Path:
    path = directory / "big.py"
    path.write_text("x = 1\n" * lines)
    return path


def test_nudge_above_threshold_adds_context(tmp_path: Path) -> None:
    event = _fixture("prompt.json", transcript=FIXTURES / "transcript.jsonl", cwd=tmp_path)
    assert _reply(event, "nudge", "--tokens", "200000") == {
        "hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": NUDGE}
    }


def test_nudge_below_default_threshold_is_silent(tmp_path: Path) -> None:
    event = _fixture("prompt.json", transcript=FIXTURES / "transcript.jsonl", cwd=tmp_path)
    assert _reply(event, "nudge") == {}


def test_nudge_without_transcript_says_nothing() -> None:
    assert _reply(_fixture("prompt_no_transcript.json"), "nudge", "--tokens", "1") == {}


def test_long_text_file_whole_read_is_denied(tmp_path: Path) -> None:
    event = _fixture("read.json", cwd=tmp_path, file=_long_file(tmp_path, 401))
    assert _reply(event, "read-guard", "--lines", "400") == {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": "big.py has 401 lines; grep for what you need, then read "
            "that slice with offset and limit. To read it whole on purpose, pass an explicit "
            "limit.",
        }
    }


@pytest.mark.parametrize(("lines", "denied"), [(401, True), (400, False)])
def test_default_line_threshold(tmp_path: Path, lines: int, denied: bool) -> None:
    event = _fixture("read.json", cwd=tmp_path, file=_long_file(tmp_path, lines))
    assert bool(_reply(event, "read-guard")) is denied


def test_subagent_read_is_allowed(tmp_path: Path) -> None:
    event = _fixture("read_subagent.json", cwd=tmp_path, file=_long_file(tmp_path, 1000))
    assert _reply(event, "read-guard", "--lines", "400") == {}


@pytest.mark.parametrize(
    ("stdin", "args"),
    [
        ("not json", ["nudge"]),
        ("{}", []),
        ("{}", ["compact"]),
        ("{}", ["read-guard", "--lines", "abc"]),
        ("{}", ["nudge", "--tokens", "0"]),
        ("{}", ["nudge", "--tokens", "-5"]),
        ("{}", ["read-guard", "--lines", "4.5"]),
        ("{}", ["read-guard", "--lines", "+5"]),
        ("{}", ["read-guard", "--lines", "1_000"]),
        ("{}", ["nudge", "--tokens=5"]),
        ("{}", ["nudge", "--lines", "5"]),
        ("{}", ["read-guard", "--lines"]),
        ("{}", ["read-guard", "--lines", "5", "extra"]),
    ],
)
def test_hooks_never_fail(stdin: str, args: list[str]) -> None:
    done = _run(stdin, *args)
    assert done.returncode == 0 and done.stdout == ""
    assert done.stderr.startswith("context: ")


@pytest.mark.parametrize("command", ["nudge", "read-guard"])
def test_empty_event_is_silent(command: str) -> None:
    done = _run("{}", command)
    assert (done.returncode, done.stdout, done.stderr) == (0, "", "")


def _hook(event: str, matcher: str | None) -> dict:
    groups = json.loads(SETTINGS.read_text())["hooks"][event]
    (group,) = [g for g in groups if g.get("matcher") == matcher]
    (hook,) = group["hooks"]
    return hook


@pytest.mark.parametrize(
    ("event", "matcher", "command"),
    [("UserPromptSubmit", None, "nudge"), ("PreToolUse", "Read", "read-guard")],
)
def test_settings_example_wires_both_hooks(event: str, matcher: str | None, command: str) -> None:
    hook = _hook(event, matcher)
    assert hook["timeout"] == 10
    argv = shlex.split(hook["command"])
    assert argv[:3] == ["python3", "-I", "$HOME/.claude/hooks/run_context.py"]
    assert argv[3] == command
    assert _run("{}", *argv[3:]).stderr == ""
