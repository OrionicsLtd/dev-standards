"""The command line through `main`: a short summary on stdout, the full report in a file.

The network and the tools the suite can't assume (osv-scanner, runtimes) are faked; the feed
cache points at a temp dir so a real cache on this machine is never read.
"""

import copy
import datetime
import io
import json
import os
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from advisories import feeds
from advisories.cli import main

FIXTURE = Path(__file__).parent / "fixtures" / "osv.json"
TODAY = datetime.date.today()


def _kev_entry(days_ago: int, cve: str, vendor: str) -> dict[str, str]:
    added = (TODAY - datetime.timedelta(days=days_ago)).isoformat()
    return {
        "dateAdded": added,
        "vendorProject": vendor,
        "product": "Server",
        "cveID": cve,
        "vulnerabilityName": f"{vendor} Server flaw",
        "dueDate": added,
    }


KEV = {
    "vulnerabilities": [
        _kev_entry(1, "CVE-2026-11", "Acme"),
        _kev_entry(2, "CVE-2026-12", "Globex"),
        _kev_entry(60, "CVE-2026-13", "Initech"),
    ]
}


@pytest.fixture(autouse=True)
def offline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Serve only the URLs a test registers; every other request fails as if offline."""
    responses: dict[str, Any] = {}

    def urlopen(request: urllib.request.Request, timeout: float) -> io.BytesIO:
        if request.full_url not in responses:
            raise urllib.error.URLError("offline")
        return io.BytesIO(json.dumps(responses[request.full_url]).encode())

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(feeds, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    return responses


def _fake_tools(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, report: Path = FIXTURE) -> None:
    """An osv-scanner that prints a recorded report, and runtimes that report no version."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    scripts = {"osv-scanner": f"cat '{report}'\nexit 1\n", "node": "exit 1\n"}
    scripts |= {"python3": "exit 1\n", "go": "exit 1\n"}
    for name, body in scripts.items():
        tool = bin_dir / name
        tool.write_text("#!/bin/sh\n" + body)
        tool.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")


def _report_path(stdout: str) -> Path:
    (line,) = [line for line in stdout.splitlines() if line.startswith("Full report: ")]
    return Path(line.removeprefix("Full report: "))


def test_hot_prints_a_summary_and_writes_the_table(
    offline: dict[str, Any], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    offline[feeds.KEV_URL] = KEV
    output = tmp_path / "hot.md"
    assert main(["hot", "--days", "30", "--output", str(output)]) == 0
    stdout = capsys.readouterr().out
    assert "2 added. By vendor: Acme (Server); Globex (Server)" in stdout
    assert "CVE-2026-11" not in stdout
    assert _report_path(stdout) == output
    details = output.read_text()
    assert "CVE-2026-11" in details and "CVE-2026-12" in details
    assert "CVE-2026-13" not in details


def test_report_goes_to_a_new_temp_file_by_default(
    offline: dict[str, Any], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    offline[feeds.KEV_URL] = KEV
    assert main(["hot"]) == 0
    path = _report_path(capsys.readouterr().out)
    assert path.parent == tmp_path and path.name.startswith("advisories-hot-")
    assert "CVE-2026-12" in path.read_text()


def test_scan_prints_counts_and_writes_every_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _fake_tools(tmp_path, monkeypatch)
    output = tmp_path / "scan.md"
    assert main(["scan", str(tmp_path), "--output", str(output)]) == 0
    stdout = capsys.readouterr().out
    assert "2 vulnerable packages: 0 malicious, 0 exploited in the wild." in stdout
    assert "Feed unavailable" in stdout
    details = output.read_text()
    assert "`anyio`" in details and "`certifi`" in details
    assert _report_path(stdout) == output


def test_scan_summary_lists_five_packages_and_the_file_lists_all(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    recorded = json.loads(FIXTURE.read_text())
    result = recorded["results"][0]
    packages = []
    for n in range(7):
        package = copy.deepcopy(result["packages"][0])
        package["package"]["name"] = f"pkg{n}"
        packages.append(package)
    report = tmp_path / "osv.json"
    report.write_text(json.dumps({"results": [{**result, "packages": packages}]}))
    _fake_tools(tmp_path, monkeypatch, report)
    output = tmp_path / "scan.md"
    assert main(["scan", str(tmp_path), "--output", str(output)]) == 0
    stdout = capsys.readouterr().out
    assert stdout.count("| PyPI `pkg") == 5
    assert "2 more in the full report." in stdout
    assert output.read_text().count("| PyPI `pkg") == 7


def test_unwritable_output_is_an_error(
    offline: dict[str, Any], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    offline[feeds.KEV_URL] = KEV
    assert main(["hot", "--output", str(tmp_path / "missing" / "hot.md")]) == 1
    assert "error:" in capsys.readouterr().err
