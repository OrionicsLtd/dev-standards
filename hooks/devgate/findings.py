"""A rule broken at one place in a file."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Finding:
    """One rule a file breaks, located well enough to fix without searching."""

    path: str
    line: int
    message: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.message}"
