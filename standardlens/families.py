"""Parse BIS/ISO-style standard numbers into a number family and part label.

Series members such as ``IS 101 (Part 2/Sec 6):2026`` and
``IS 101 (Part 5):2015`` belong to one family (``IS 101``). Families are a
factual property of the identifier, so they can be shown as related records
without inventing any BIS relationship type.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Leading organisation prefix (IS, IS/ISO/IEC, IS/ISO/IEC/IEEE, SP, IS/QC, ...).
PREFIX = r"[A-Z]{2,12}(?:[ ]*/[ ]*[A-Z]{2,12})*"
NUMBER_RE = re.compile(
    rf"^(?P<prefix>{PREFIX})[ .\-]*(?P<number>\d{{1,9}}[A-Z]?)(?P<rest>.*)$",
    re.I | re.S,
)
PART_RE = re.compile(r"\(\s*(?P<part>[^()]*?)\s*\)")
YEAR_RE = re.compile(r":\s*(\d{4})")


@dataclass(frozen=True)
class NumberParts:
    prefix: str
    number: str
    part: str
    year: str
    suffix: str

    @property
    def family(self) -> str:
        """Stable grouping key that ignores edition year and part."""
        return f"{self.prefix} {self.number}" if self.prefix else self.number


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def parse_number(is_number: str) -> NumberParts:
    """Split an identifier into prefix, base number, part label, year, suffix."""
    text = _clean(is_number or "")
    if not text:
        return NumberParts("", "", "", "", "")
    match = NUMBER_RE.match(text.replace("IEC IEEE", "IEC/IEEE"))
    if not match:
        # Unknown shape: fall back to the year-stripped identifier so grouping never crashes.
        return NumberParts("", "", "", "", "")
    prefix = re.sub(r"\s*/\s*", "/", _clean(match.group("prefix"))).upper()
    number = match.group("number").upper()
    rest = match.group("rest") or ""
    part_match = PART_RE.search(rest)
    part = _clean(part_match.group("part")) if part_match else ""
    year_match = YEAR_RE.search(rest)
    year = year_match.group(1) if year_match else ""
    tail = _clean(re.sub(PART_RE, " ", re.sub(YEAR_RE, " ", rest)))
    return NumberParts(prefix, number, part, year, tail)


def family_key(is_number: str) -> str:
    return parse_number(is_number).family


def part_label(is_number: str) -> str:
    return parse_number(is_number).part


def edition_year(is_number: str) -> str:
    return parse_number(is_number).year


def group_families(values: list[str]) -> dict[str, list[int]]:
    """Map family key -> record indices, keeping only families with 2+ members."""
    groups: dict[str, list[int]] = {}
    for index, value in enumerate(values):
        family = family_key(value)
        if not family:
            continue
        groups.setdefault(family, []).append(index)
    return {family: members for family, members in groups.items() if len(members) > 1}
