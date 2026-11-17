"""Secrets on the lines a change adds. Findings name the kind of secret, never its text."""

import hashlib
import re
from collections.abc import Callable

from .diff import FileDiff
from .findings import Finding

# A token starts and, at a fixed length, ends where no token character touches it.
START = r"(?<![A-Za-z0-9_-])"
END = r"(?![A-Za-z0-9_-])"
TOKENS = (
    ("AWS access key", rf"{START}(?:AKIA|ASIA)[0-9A-Z]{{16}}{END}"),
    ("GitHub token", rf"{START}gh[pousr]_[A-Za-z0-9]{{36}}{END}"),
    ("GitHub token", rf"{START}github_pat_[A-Za-z0-9_]{{22,}}"),
    ("Anthropic API key", rf"{START}sk-ant-[A-Za-z0-9_-]{{20,}}"),
    ("OpenAI API key", rf"{START}sk-(?!ant-)[A-Za-z0-9_-]{{20,}}"),
    ("Stripe live key", rf"{START}[sr]k_live_[A-Za-z0-9]{{16,}}"),
    ("Slack token", rf"{START}xox[abprs]-[A-Za-z0-9-]{{10,}}"),
    ("Google API key", rf"{START}AIza[0-9A-Za-z_-]{{35}}{END}"),
    ("GitLab token", rf"{START}glpat-[A-Za-z0-9_-]{{20,}}"),
    ("npm token", rf"{START}npm_[A-Za-z0-9]{{36}}{END}"),
    ("PyPI token", rf"{START}pypi-AgEIcHlwaS5vcmc[A-Za-z0-9_-]{{50,}}"),
    ("Hugging Face token", rf"{START}hf_[A-Za-z0-9]{{34}}{END}"),
    ("PEM private key", r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY(?: BLOCK)?-----"),
)
HEX_KEY = re.compile(rf"{START}(?:0x)?([0-9a-fA-F]{{64}}){END}")
# 64 hex characters are also hashes and transaction ids; only a line that names a key makes
# them a key.
KEY_WORD = re.compile(
    r"priv(?:ate)?[ _-]?key|secret|signing[ _-]?key|mnemonic|(?<![a-z])pk(?![a-z])", re.IGNORECASE
)
MNEMONIC = re.compile(r"[a-z]{3,8}(?: [a-z]{3,8})*")
MNEMONIC_LENGTHS = (12, 15, 18, 21, 24)
QUOTED = re.compile(r"\"([^\"]*)\"|'([^']*)'")
# sha256 of the public Hardhat/Anvil dev secrets (lowercase hex, no 0x): the 20 default account
# keys of `test test test test test test test test test test test junk`, then that mnemonic.
DEV_ACCOUNT_DIGESTS = frozenset(
    {
        "bc1a50966c9e6486bc4ebf880b51611a2a97fcb8e7a6976e9b81a9e3e8ca0e3c",
        "8335c55334821eefd4334369ff9c04a8594f161013cf9d87f58802d87297837e",
        "b26ab6529d20ebebb4192256f202984754f785481c64b1a1aed58cac93b3617e",
        "64034b44c579b335ab5e85debbfe72789e970138cc8d296799c3833a2a8525fb",
        "4d3e46eec8244d1d106f866ee48994f6176705298aee1b8426b2ad2529eb454b",
        "0aedba9d586f34f95cf1f0d54926f62e8a078ce2ca593be73ab27a87d3ff9c5d",
        "28e543d3753fc9d14c658ebef20b76a3b5f8e7d78667baf27832ceb3bea01bdf",
        "f070994a8599478580678f2b9482c5f02bb3de0647281e8efae183669425808a",
        "38e69fdd19aefeb4adf56312f10e62c30274997835173c7006308323ad7db506",
        "967f21586cdf1248a862f2cfb330099701c942c2c7a7537c54f7ec48f8556505",
        "0b33e0132123e78d42dd12a0fbbbacd19827d35ca88e0ad4ba83a47a65ba0487",
        "84bc109b3d59b0173a76fc3d831360a6e5063b3d4c82793a97de992947a0e3a8",
        "85bde548053aab4b5a6c78473d5eb2addaa5824299ad009bf06775e3ce923010",
        "f1513114f60e5e95732b840669fe83956d8a944d23e6c76f953e7edcf2491901",
        "5330d388af894c9e1a181a06a3ce44d61fd8602165d979942be4641f4002762f",
        "a2e06155cb1a424f972c3abfaddc9cea4820c4aec722d2378903fe28dd8fc40c",
        "4a67d7a0d8a16d6d954cef19eb5afdbdd82cc0e907a571f376ef0a0981a2a9d4",
        "b08bdfde9930d9202809530dcbe193c53fd0dc6928f2010d2ffca74df95ead36",
        "cf1fc66f853151a4c6666909c8f1f80e1d855ecffefbcb65a709aae544de5588",
        "100546a8b020a55aa09b2d34b50de9a3fc45a70b261aec6a989bb2d9321af583",
        "f79cd64f9cea237897b8133e4b905b361c6f166faa5a1c64c32280938f5b707e",
    }
)
MESSAGE = "possible {kind}; remove it, and revoke it if it was ever real"
HIDDEN_LINE = "(line not shown: it holds a possible secret)"


def _tokens(pattern: str) -> Callable[[str], list[str]]:
    return re.compile(pattern).findall


def _hex_keys(text: str) -> list[str]:
    return [key.lower() for key in HEX_KEY.findall(text)] if KEY_WORD.search(text) else []


def _mnemonics(text: str) -> list[str]:
    """Whole word runs: each quoted string, the value after `=` or `:`, and the line itself."""
    candidates = [double or single for double, single in QUOTED.findall(text)]
    assignment = re.split("[=:]", text, maxsplit=1)
    if len(assignment) == 2:
        candidates.append(assignment[1].strip().strip("\"'").strip())
    candidates.append(text.strip())
    return [
        words
        for words in candidates
        if MNEMONIC.fullmatch(words) and len(words.split(" ")) in MNEMONIC_LENGTHS
    ]


DETECTORS: tuple[tuple[str, Callable[[str], list[str]]], ...] = (
    *((kind, _tokens(pattern)) for kind, pattern in TOKENS),
    ("hex private key", _hex_keys),
    ("mnemonic", _mnemonics),
)


def _public(value: str) -> bool:
    return hashlib.sha256(value.encode()).hexdigest() in DEV_ACCOUNT_DIGESTS


def kinds(text: str) -> list[str]:
    """Name each kind of secret the text holds, once, leaving out the public dev secrets."""
    found = [kind for kind, find in DETECTORS if any(not _public(v) for v in find(text))]
    return list(dict.fromkeys(found))


def redact(text: str) -> str:
    """Replace each line holding a possible secret, so tool output never repeats one."""
    return "\n".join(HIDDEN_LINE if kinds(line) else line for line in text.splitlines())


def leaks(files: tuple[FileDiff, ...]) -> list[Finding]:
    """Flag added lines holding a secret, by kind only, so the report never repeats it."""
    return [
        Finding(file.path, line_no, MESSAGE.format(kind=kind))
        for file in files
        for line_no, text in file.added
        for kind in kinds(text)
    ]
