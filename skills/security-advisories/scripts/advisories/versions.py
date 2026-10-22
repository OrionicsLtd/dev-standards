"""Approximate version ordering, good enough to pick a fix target across ecosystems.

Not a full PEP 440 or semver implementation: the agent confirms the chosen target against the
advisory before upgrading.
"""

import re

RELEASE = re.compile(r"^[vV]?(\d+(?:\.\d+)*)(.*)$")
POST_MARKERS = ("+", ".post", "-post", "post")

Key = tuple[tuple[int, ...], int, str]


def key(version: str) -> Key:
    """Sort key: numeric release, then pre-releases before the release and post-releases after."""
    match = RELEASE.match(version.strip())
    if not match:
        return ((), 0, version)
    numbers = [int(part) for part in match.group(1).split(".")]
    while len(numbers) > 1 and numbers[-1] == 0:
        numbers.pop()
    rest = match.group(2)
    rank = 1 if not rest else 2 if rest.startswith(POST_MARKERS) else 0
    return (tuple(numbers), rank, rest)


def newer(candidate: str, current: str) -> bool:
    """True when `candidate` sorts after `current`."""
    return key(candidate) > key(current)


def line(version: str, depth: int) -> tuple[int, ...]:
    """The release line of a version: its first `depth` numeric parts (`24.18.0`, 1 → `(24,)`)."""
    match = RELEASE.match(version.strip())
    return tuple(int(part) for part in match.group(1).split(".")[:depth]) if match else ()
