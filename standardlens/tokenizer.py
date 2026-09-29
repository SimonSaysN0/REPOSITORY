"""Stopwords and tokenizer shared by the Python index builder and search.js.

The browser reads STOPWORDS from the generated index, so the lists cannot drift
apart. Keep this tokenizer ASCII-only and dependency-free so search.js can be a
faithful transcription of it.
"""
from __future__ import annotations

import re

# Terms that carry no discriminating signal for procurement matching.
STOPWORDS_TEXT = """
a an and are as at be been by for from has have if in into is it its of on or per that the this to with within
without used using use uses shall should may must can could will would not no nor any all other others each
such their them they we you our your which who whom whose when where while what how why also than then
these those there here both more most much many less least about above after again along ahead against
among around because before behind below beneath beside besides between beyond during either neither
except few further hence however instead itself likewise meanwhile moreover nevertheless onward
onto whatsoever whenever whether whereby wherein regarding respectively since so through throughout
thus toward towards under unless until unto upon whatever wherever whichever yet namely viz etc ie eg
vs versus given gave make making based up down off over out wise form forming takes taken
procurement purchase purchasing supply supplied supplier supplying vendors vendor tender tenders
bidding buyer buyers desired needed wanted intended provide provided provision suitable suitably
required requirement requirements spec
indian india standard standards method methods tests test code practice practices
guideline guidelines general terms term definition definitions sectional section sections
annexure annex appendix
table figure figures page pages revision revisions amended amendment latest edition issue issues
part parts sub-part subpart clause clauses sheet sheets group groups series
"""

STOPWORDS: tuple[str, ...] = tuple(dict.fromkeys(STOPWORDS_TEXT.lower().split()))
MIN_TOKEN_LEN = 2
MAX_TOKEN_LEN = 40
TOKEN_PATTERN = re.compile(r"[a-z0-9][a-z0-9.\-]*")
# Words ending in "s" that must not lose their final letter.
NO_FOLD = frozenset({"gas", "bias", "status", "canvas", "atlas", "corpus", "genus", "bus", "plus", "iris", "lens"})


def fold(term: str) -> str:
    """Collapse a crude plural so "cables" and "cable" share one posting list."""
    if len(term) > 4 and term.endswith("s") and not term.endswith("ss") and term not in NO_FOLD:
        return term[:-1]
    return term


def normalize(term: str) -> str:
    return fold(term.strip().lower().strip("-.").rstrip("."))


def tokenize(text: str, stopwords: frozenset[str] | set[str] | None = None) -> list[str]:
    """Return folded, stop-word-filtered tokens in order of appearance."""
    stop = frozenset(STOPWORDS) if stopwords is None else stopwords
    out: list[str] = []
    for raw in TOKEN_PATTERN.findall((text or "").lower()):
        token = raw.strip("-.")
        if len(token) < MIN_TOKEN_LEN or len(token) > MAX_TOKEN_LEN:
            continue
        if token.isdigit() and len(token) < 3:  # keep "110", drop bare "1"/"2"
            continue
        term = fold(token)
        if term in stop:
            continue
        out.append(term)
    return out


def unique_tokens(text: str, stopwords: frozenset[str] | set[str] | None = None) -> list[str]:
    return list(dict.fromkeys(tokenize(text, stopwords)))
