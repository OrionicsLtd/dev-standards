"""Report rendering: the summary printed to the terminal against the full report on disk."""

from advisories.osv import Advisory, Vulnerable
from advisories.report import dependencies, exploited, exploited_summary


def _package(name: str, *ids: str) -> Vulnerable:
    advisory = Advisory(ids, f"{name} is broken", 7.5, "2.0")
    return Vulnerable("PyPI", name, "1.0", "uv.lock", (advisory,))


PACKAGES = [_package(f"pkg{n}", f"GHSA-{n}") for n in range(7)]
KEV_ENTRY = {
    "dateAdded": "2026-11-10",
    "vendorProject": "Microsoft",
    "product": "Office",
    "cveID": "CVE-2026-1",
    "vulnerabilityName": "Office flaw",
    "dueDate": "2026-11-24",
}


def _rows(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith(("| PyPI", "| npm"))]


def test_dependencies_counts_what_needs_attention() -> None:
    found = [
        _package("evil", "MAL-1"),
        _package("hit", "CVE-2026-9"),
        _package("plain", "GHSA-1"),
    ]
    text = dependencies(found, {"CVE-2026-9": {}}, {})
    assert "3 vulnerable packages: 1 malicious, 1 exploited in the wild." in text


def test_summary_keeps_the_five_most_urgent_rows() -> None:
    found = [*PACKAGES, _package("evil", "MAL-1")]
    text = dependencies(found, {}, {}, summary=True)
    rows = _rows(text)
    assert len(rows) == 5
    assert "`evil`" in rows[0]
    assert "3 more in the full report." in text


def test_summary_shows_the_three_most_urgent_advisories_of_a_package() -> None:
    advisories = tuple(Advisory((f"GHSA-{n}",), f"bug {n}", float(n), "2.0") for n in range(6))
    found = [Vulnerable("npm", "big", "1.0", "package-lock.json", advisories)]
    (row,) = _rows(dependencies(found, {}, {}, summary=True))
    assert "GHSA-5" in row and "GHSA-4" in row and "GHSA-3" in row
    assert "GHSA-2" not in row and "+3 more" in row
    (full,) = _rows(dependencies(found, {}, {}))
    assert "GHSA-0" in full and "more" not in full


def test_dependencies_without_limit_lists_every_package() -> None:
    text = dependencies(PACKAGES, {}, {})
    assert len(_rows(text)) == len(PACKAGES)
    assert "more in the full report" not in text


def test_summary_below_the_limit_adds_no_more_line() -> None:
    text = dependencies(PACKAGES[:2], {}, {}, summary=True)
    assert len(_rows(text)) == 2 and "more in the full report" not in text


def test_exploited_summary_groups_products_by_vendor() -> None:
    entries = [
        KEV_ENTRY,
        {**KEV_ENTRY, "product": "Windows", "cveID": "CVE-2026-2"},
        {**KEV_ENTRY, "product": "Office", "cveID": "CVE-2026-3"},
        {**KEV_ENTRY, "vendorProject": "Apple", "product": "iOS", "cveID": "CVE-2026-4"},
    ]
    text = exploited_summary(entries, 30)
    assert text == (
        "## Actively exploited (last 30 days)\n\n"
        "4 added. By vendor: Apple (iOS); Microsoft (Office, Windows)\n"
    )
    assert "CVE-2026-1" in exploited(entries, 30)


def test_exploited_summary_with_nothing_added_says_so() -> None:
    assert exploited_summary([], 7) == "## Actively exploited (last 7 days)\n\nNone added.\n"
