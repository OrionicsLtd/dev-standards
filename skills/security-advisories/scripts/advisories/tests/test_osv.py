"""Version ordering and osv-scanner report parsing, against a trimmed real report."""

import json
from pathlib import Path

from advisories.osv import fixed_version, parse
from advisories.versions import key, newer

FIXTURE = Path(__file__).parent / "fixtures" / "osv.json"


def test_versions_order_numerically_with_pre_and_post_releases() -> None:
    assert newer("4.14.10", "4.14.2")
    assert newer("2026.10.19", "2026.6.17")
    assert key("1.0.0") == key("1.0")
    assert key("1.0.0rc1") < key("1.0.0") < key("1.0.0.post1")
    assert key("v24.22.1") == key("24.22.1")


def test_fixed_version_picks_the_interval_containing_the_installed_version() -> None:
    record = {
        "affected": [
            {
                "package": {"name": "lib"},
                "ranges": [
                    {"type": "ECOSYSTEM", "events": [{"introduced": "0"}, {"fixed": "1.2.5"}]},
                    {"type": "ECOSYSTEM", "events": [{"introduced": "2.0"}, {"fixed": "2.0.3"}]},
                ],
            }
        ]
    }
    assert fixed_version(record, "lib", "1.2.0") == "1.2.5"
    assert fixed_version(record, "lib", "2.0.1") == "2.0.3"
    assert fixed_version(record, "Other", "1.0") is None


def test_unfixed_interval_has_no_target() -> None:
    record = {
        "affected": [
            {
                "package": {"name": "lib"},
                "ranges": [{"type": "SEMVER", "events": [{"introduced": "1.0"}]}],
            }
        ]
    }
    assert fixed_version(record, "lib", "1.5") is None


def test_parse_folds_duplicate_records_into_one_advisory() -> None:
    found = {p.name: p for p in parse(json.loads(FIXTURE.read_text()), Path("/repo"))}
    anyio, certifi = found["anyio"], found["certifi"]
    assert anyio.source == "uv.lock"
    assert len(anyio.advisories) == 3
    assert anyio.target == "4.14.2"
    assert certifi.target == "2026.10.19"
    assert certifi.advisories[0].severity == 9.1
    assert "GHSA-6q48-6c7w-9gw2" in certifi.advisories[0].ids


def test_malicious_records_are_flagged() -> None:
    report = {
        "results": [
            {
                "source": {"path": "package-lock.json"},
                "packages": [
                    {
                        "package": {"name": "evil", "version": "1.0.1", "ecosystem": "npm"},
                        "vulnerabilities": [{"id": "MAL-2026-1", "summary": "Malicious code"}],
                        "groups": [{"ids": ["MAL-2026-1"]}],
                    }
                ],
            }
        ]
    }
    (package,) = parse(report)
    assert package.advisories[0].malicious
    assert package.target is None
