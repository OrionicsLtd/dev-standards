"""Free public feeds: CISA's exploited-vulnerability catalog, EPSS scores and release indexes.

Responses are cached on disk for a few hours so repeated scans stay fast and polite.
"""

import hashlib
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

CACHE = Path.home() / ".cache" / "security-advisories"
TTL_SECONDS = 6 * 3600
TIMEOUT_SECONDS = 30
EPSS_BATCH = 100

KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
EPSS_URL = "https://api.first.org/data/v1/epss?cve="
NODE_URL = "https://nodejs.org/dist/index.json"
EOL_URL = "https://endoflife.date/api/{product}.json"


class FeedError(Exception):
    """A feed could not be fetched or parsed."""


def fetch(url: str) -> Any:
    """Return a URL's JSON, served from the disk cache while it is fresh."""
    cached = CACHE / (hashlib.sha256(url.encode()).hexdigest()[:24] + ".json")
    if cached.exists() and time.time() - cached.stat().st_mtime < TTL_SECONDS:
        return json.loads(cached.read_text())
    request = urllib.request.Request(url, headers={"User-Agent": "security-advisories-skill"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            body = response.read().decode()
        data = json.loads(body)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise FeedError(f"{url}: {error}") from error
    CACHE.mkdir(parents=True, exist_ok=True)
    cached.write_text(body)
    return data


def kev() -> dict[str, dict[str, Any]]:
    """CISA's Known Exploited Vulnerabilities catalog, keyed by CVE."""
    return {entry["cveID"]: entry for entry in fetch(KEV_URL)["vulnerabilities"]}


def epss(cves: list[str]) -> dict[str, float]:
    """Probability of exploitation in the next 30 days, for the CVEs FIRST has scored."""
    scores: dict[str, float] = {}
    unique = sorted(set(cves))
    for start in range(0, len(unique), EPSS_BATCH):
        batch = ",".join(unique[start : start + EPSS_BATCH])
        for row in fetch(EPSS_URL + batch).get("data", []):
            scores[row["cve"]] = float(row["epss"])
    return scores


def node_releases() -> list[dict[str, Any]]:
    """Every Node.js release, newest first, with its `security` flag."""
    return fetch(NODE_URL)


def cycles(product: str) -> list[dict[str, Any]]:
    """endoflife.date release cycles for a product: latest patch and end-of-life date."""
    return fetch(EOL_URL.format(product=product))
