"""End-to-end tests: hook events against a scratch git repository."""

import io
import json
import subprocess
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from devgate import cli, state

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


def _fire(monkeypatch: pytest.MonkeyPatch, hook: str, repo: Path, **fields: object) -> dict:
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
    _fire(monkeypatch, "subagent-stop", repo, agent_type="diff-reviewer")
    second = _fire(monkeypatch, "stop", repo, last_assistant_message="done")
    assert "Not verified" in second["reason"]
    assert _fire(monkeypatch, "stop", repo, last_assistant_message=PASSING_REPORT) == {}
    assert _fire(monkeypatch, "stop", repo, last_assistant_message="chat") == {}


def _launch(
    monkeypatch: pytest.MonkeyPatch,
    repo: Path,
    agent_id: str = "a1",
    agent: str = "diff-reviewer",
    status: str = "async_launched",
) -> None:
    response = {"status": status, "agentId": agent_id}
    tool_input = {"subagent_type": agent}
    _fire(monkeypatch, "review-start", repo, tool_input=tool_input, tool_response=response)


def _report(monkeypatch: pytest.MonkeyPatch, repo: Path, agent_id: str = "a1") -> None:
    _fire(monkeypatch, "subagent-stop", repo, agent_type="diff-reviewer", agent_id=agent_id)


def _lines(start: int, count: int) -> str:
    return "".join(f"y{i} = {i}\n" for i in range(start, start + count))


def test_lines_added_while_a_review_runs_stay_unreviewed(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fire(monkeypatch, "session-start", repo)
    (repo / "app.py").write_text("x = 1\n" + _lines(0, 10))
    _launch(monkeypatch, repo)
    (repo / "app.py").write_text("x = 1\n" + _lines(0, 16))
    _report(monkeypatch, repo)
    reason = _fire(monkeypatch, "stop", repo, last_assistant_message="done")["reason"]
    assert reason.startswith("6 added lines have not been independently reviewed")


def test_a_running_review_lets_the_turn_end_until_it_reports(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fire(monkeypatch, "session-start", repo)
    (repo / "app.py").write_text("x = 1\n" + _lines(0, 10))
    _launch(monkeypatch, repo)
    waiting = _fire(monkeypatch, "stop", repo, last_assistant_message="review started")
    assert "decision" not in waiting and "still running" in waiting["systemMessage"]
    _report(monkeypatch, repo)
    reply = _fire(monkeypatch, "stop", repo, last_assistant_message="done")
    assert "Not verified" in reply["reason"]


def test_an_abandoned_review_stops_counting_as_running(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = "checks = []\nreview_threshold = 5\nreview_expiry = 0\n"
    (repo / ".claude/devgate.toml").write_text(config)
    _fire(monkeypatch, "session-start", repo)
    (repo / "app.py").write_text("x = 1\n" + _lines(0, 10))
    _launch(monkeypatch, repo)
    reply = _fire(monkeypatch, "stop", repo, last_assistant_message="done")
    assert "diff-reviewer" in reply["reason"]


def test_a_review_outliving_the_expiry_still_counts_for_its_launch(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = "checks = []\nreview_threshold = 5\nreview_expiry = 0\n"
    (repo / ".claude/devgate.toml").write_text(config)
    _fire(monkeypatch, "session-start", repo)
    (repo / "app.py").write_text("x = 1\n" + _lines(0, 10))
    _launch(monkeypatch, repo)
    (repo / "app.py").write_text("x = 1\n" + _lines(0, 16))
    _report(monkeypatch, repo)
    reason = _fire(monkeypatch, "stop", repo, last_assistant_message="done")["reason"]
    assert reason.startswith("6 added lines have not been independently reviewed")


def test_each_report_stamps_its_own_launch_in_any_order(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fire(monkeypatch, "session-start", repo)
    (repo / "app.py").write_text("x = 1\n" + _lines(0, 10))
    _launch(monkeypatch, repo, agent_id="early")
    (repo / "app.py").write_text("x = 1\n" + _lines(0, 16))
    _launch(monkeypatch, repo, agent_id="late")
    _launch(monkeypatch, repo, agent_id="never-reports")
    _report(monkeypatch, repo, agent_id="late")
    _report(monkeypatch, repo, agent_id="early")
    assert sum(state.reviewed(repo).values()) == 16
    waiting = _fire(monkeypatch, "stop", repo, last_assistant_message="x")
    assert "still running" in waiting["systemMessage"]


def test_foreground_and_other_launches_are_not_recorded(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fire(monkeypatch, "session-start", repo)
    (repo / "app.py").write_text("x = 1\n" + _lines(0, 10))
    _launch(monkeypatch, repo, agent="Explore")
    _launch(monkeypatch, repo, agent_id="fg", status="completed")
    reply = _fire(monkeypatch, "stop", repo, last_assistant_message="done")
    assert "diff-reviewer" in reply["reason"]
    _report(monkeypatch, repo, agent_id="fg")
    assert "Not verified" in _fire(monkeypatch, "stop", repo, last_assistant_message="x")["reason"]


def test_a_review_launched_before_any_code_does_not_cover_later_code(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fire(monkeypatch, "session-start", repo)
    _launch(monkeypatch, repo)
    (repo / "app.py").write_text("x = 1\n" + _lines(0, 10))
    _report(monkeypatch, repo)
    assert "diff-reviewer" in _fire(monkeypatch, "stop", repo, last_assistant_message="x")["reason"]


def test_concurrent_launches_and_reports_are_all_recorded(repo: Path) -> None:
    lines = Counter({f"app.py\0y{i}": 1 for i in range(8)})

    def launch(index: int) -> None:
        state.start_review(repo, f"a{index}", lines, 0.0)

    def report(index: int) -> None:
        state.stamp_reviewed(repo, Counter({f"app.py\0y{index}": 1}), lines)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(launch, range(8)))
        list(pool.map(report, range(8)))
    assert all(state.finish_review(repo, f"a{i}", 0.0, 60) for i in range(8))
    assert state.reviewed(repo) == lines


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
