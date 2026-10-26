"""End-to-end tests: hook events against a scratch git repository."""

import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

from devgate import cli

PASSING_REPORT = "Ran pytest.\nNot verified: nothing"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "t")
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude/devgate.toml").write_text("checks = []\nreview_threshold = 5\n")
    (tmp_path / "app.py").write_text("x = 1\n")
    git("add", ".")
    git("commit", "-qm", "init")
    return tmp_path


def _fire(monkeypatch: pytest.MonkeyPatch, hook: str, repo: Path, **fields: str) -> dict:
    event = {"session_id": "s1", "cwd": str(repo), **fields}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(event)))
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    assert cli.main(["devgate", hook]) == 0
    return json.loads(out.getvalue() or "{}")


def test_preexisting_changes_are_baseline(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (repo / "app.py").write_text("x = 1\n" + "".join(f"y{i} = {i}\n" for i in range(10)))
    _fire(monkeypatch, "session-start", repo)
    assert _fire(monkeypatch, "stop", repo, last_assistant_message="done") == {}


def test_review_then_evidence_then_pass(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fire(monkeypatch, "session-start", repo)
    (repo / "app.py").write_text("x = 1\n" + "".join(f"y{i} = {i}\n" for i in range(10)))
    first = _fire(monkeypatch, "stop", repo, last_assistant_message="done")
    assert first["decision"] == "block" and "diff-reviewer" in first["reason"]
    _fire(
        monkeypatch, "subagent-stop", repo, agent_type="diff-reviewer", last_assistant_message="ok"
    )
    second = _fire(monkeypatch, "stop", repo, last_assistant_message="done")
    assert "Not verified" in second["reason"]
    assert _fire(monkeypatch, "stop", repo, last_assistant_message=PASSING_REPORT) == {}
    assert _fire(monkeypatch, "stop", repo, last_assistant_message="chat") == {}


def test_other_subagents_do_not_stamp(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fire(monkeypatch, "session-start", repo)
    (repo / "app.py").write_text("x = 1\n" + "".join(f"y{i} = {i}\n" for i in range(10)))
    _fire(monkeypatch, "subagent-stop", repo, agent_type="Explore", last_assistant_message="ok")
    assert "diff-reviewer" in _fire(monkeypatch, "stop", repo, last_assistant_message="x")["reason"]


def test_style_blocks_and_gives_up_after_limit(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fire(monkeypatch, "session-start", repo)
    (repo / "app.py").write_text("x = 1  # as requested by the user\n")
    for _ in range(3):
        reply = _fire(monkeypatch, "stop", repo, last_assistant_message=PASSING_REPORT)
        assert "app.py:1" in reply["reason"]
    final = _fire(monkeypatch, "stop", repo, last_assistant_message=PASSING_REPORT)
    assert "gave up" in final["systemMessage"]


def test_failing_check_blocks_with_its_output(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = (
        'review_threshold = 999\n[[checks]]\nname = "lint"\ncmd = "sh -c \'echo bad; exit 1\'"\n'
    )
    (repo / ".claude/devgate.toml").write_text(config)
    _fire(monkeypatch, "session-start", repo)
    (repo / "app.py").write_text("x = 2\n")
    reply = _fire(monkeypatch, "stop", repo, last_assistant_message=PASSING_REPORT)
    assert "`lint` failed" in reply["reason"]


def test_outside_a_repository_is_silent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert _fire(monkeypatch, "stop", tmp_path, last_assistant_message="x") == {}


def test_growing_oversized_files_go_on_a_backlog_not_into_the_block(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    big = "".join(f"v{i} = {i}\n" for i in range(450))
    (repo / "big.py").write_text(big)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "big"], cwd=repo, check=True)
    _fire(monkeypatch, "session-start", repo)
    (repo / "big.py").write_text(big + "".join(f"w{i} = {i}\n" for i in range(30)))
    reply = _fire(monkeypatch, "stop", repo, last_assistant_message="done")
    assert "diff-reviewer" in reply["reason"] and "big.py (480" not in reply["reason"]
    # The next session is told, until the file is split.
    shown = _fire(monkeypatch, "session-start", repo, session_id="s2")
    assert "big.py (480 lines, since" in shown["hookSpecificOutput"]["additionalContext"]
    (repo / "big.py").write_text("v = 1\n")
    assert _fire(monkeypatch, "session-start", repo, session_id="s3") == {}


def test_markdown_does_not_count_toward_review(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fire(monkeypatch, "session-start", repo)
    (repo / "notes.md").write_text("".join(f"line {i}\n" for i in range(50)))
    assert _fire(monkeypatch, "stop", repo, last_assistant_message="done") == {}
    (repo / "app.py").write_text("x = 1\ny = 2\n")
    reply = _fire(monkeypatch, "stop", repo, last_assistant_message="done")
    assert "Not verified" in reply["reason"]
