"""Rank skills against a prompt by TF-IDF cosine similarity over their descriptions.

A lexical stand-in for how Claude picks a skill: two descriptions that share most of
their vocabulary score close together here, and are likely to be confused there too.
"""

import math
import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from itertools import combinations

STOPWORDS = frozenset(
    {
        "a",
        "about",
        "after",
        "all",
        "an",
        "and",
        "any",
        "are",
        "as",
        "at",
        "be",
        "before",
        "but",
        "by",
        "can",
        "could",
        "do",
        "does",
        "for",
        "from",
        "has",
        "have",
        "how",
        "i",
        "if",
        "in",
        "into",
        "is",
        "it",
        "its",
        "just",
        "me",
        "my",
        "need",
        "of",
        "on",
        "or",
        "our",
        "please",
        "should",
        "so",
        "than",
        "that",
        "the",
        "their",
        "them",
        "then",
        "there",
        "these",
        "they",
        "this",
        "to",
        "us",
        "use",
        "using",
        "was",
        "we",
        "what",
        "when",
        "whenever",
        "where",
        "which",
        "while",
        "who",
        "will",
        "with",
        "would",
        "you",
        "your",
    }
)
WORD = re.compile(r"[a-z0-9]+")

Vector = Mapping[str, float]


@dataclass(frozen=True)
class Index:
    """IDF weights fitted on the descriptions, and each description's unit vector."""

    idf: Mapping[str, float]
    vectors: Mapping[str, Vector]


def _fold(word: str) -> str:
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def tokenize(text: str) -> tuple[str, ...]:
    """Lowercase words of `text`, plurals folded to the singular, stopwords dropped.

    A word is a stopword when either form is: folding first would turn "this" into "thi",
    folding after would keep "needs" as "need".
    """
    pairs = ((word, _fold(word)) for word in WORD.findall(text.lower()))
    return tuple(
        folded for word, folded in pairs if word not in STOPWORDS and folded not in STOPWORDS
    )


def _unit(counts: Counter[str], idf: Mapping[str, float]) -> Vector:
    weights = {word: count * idf[word] for word, count in counts.items() if word in idf}
    norm = math.sqrt(sum(weight * weight for weight in weights.values()))
    return {word: weight / norm for word, weight in weights.items()} if norm else {}


def _cosine(a: Vector, b: Vector) -> float:
    return sum(weight * b.get(word, 0.0) for word, weight in a.items())


def fit(descriptions: Mapping[str, str]) -> Index:
    """Fit smoothed IDF, ln((1 + n) / (1 + df)) + 1, on the descriptions and embed each."""
    counts = {name: Counter(tokenize(text)) for name, text in descriptions.items()}
    total = len(counts)
    document_frequency = Counter(word for words in counts.values() for word in words)
    idf = {word: math.log((1 + total) / (1 + df)) + 1 for word, df in document_frequency.items()}
    return Index(idf, {name: _unit(words, idf) for name, words in counts.items()})


def rank(index: Index, prompt: str) -> tuple[tuple[str, float], ...]:
    """Every skill with its score for `prompt`, best first, ties broken by name."""
    query = _unit(Counter(tokenize(prompt)), index.idf)
    scores = ((name, _cosine(query, vector)) for name, vector in index.vectors.items())
    return tuple(sorted(scores, key=lambda item: (-item[1], item[0])))


def routes_to(ranking: tuple[tuple[str, float], ...], skill: str) -> bool:
    """Whether `skill` wins outright: first, above zero and strictly above the runner-up."""
    (first, top), *rest = ranking
    runner_up = rest[0][1] if rest else 0.0
    return first == skill and top > 0 and top > runner_up


def pair_scores(index: Index) -> tuple[tuple[str, str, float], ...]:
    """The similarity of every pair of descriptions, names in alphabetical order."""
    return tuple(
        (a, b, _cosine(index.vectors[a], index.vectors[b]))
        for a, b in combinations(sorted(index.vectors), 2)
    )


def collides(score: float, ceiling: float) -> bool:
    """Whether two descriptions scoring `score` read too alike under `ceiling`."""
    return score >= ceiling
