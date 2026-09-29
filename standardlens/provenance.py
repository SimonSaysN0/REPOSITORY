"""Field-coverage and source provenance for the local dataset.

The MVP must never imply that a blank BIS field was checked and found empty.
This module records which fields the loaded export actually carried, plus a hash
of the source export so a later import can be compared against it.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

TRACKED_FIELDS = [
    "is_number", "title", "edition_year", "publication_date", "degree_of_equivalence", "scope", "department",
    "technical_committee", "type_of_standard", "sector", "product_category", "status", "number_of_revisions",
    "number_of_amendments", "amendment_year", "reaffirmation_year", "certification", "referred_standards",
    "superseding_standard", "source_url", "date_checked",
]
CRAWL_FIELDS = ["first_seen", "last_checked", "last_changed"]


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(chunk), b""):
            digest.update(block)
    return digest.hexdigest()


def field_coverage(records: Iterable[dict[str, Any]], fields: Iterable[str] | None = None) -> dict[str, dict[str, float]]:
    """Report how many records carry a non-placeholder value for each field."""
    rows = list(records)
    total = len(rows)
    coverage: dict[str, dict[str, float]] = {}
    for field in (fields or TRACKED_FIELDS):
        filled = 0
        for row in rows:
            value = str(row.get(field, "") or "").strip()
            if value and value not in {"-", "--", "n/a", "na", "not available", "not available."}:
                filled += 1
        coverage[field] = {"filled": filled, "total": total, "pct": round(100.0 * filled / total, 1) if total else 0.0}
    return coverage


def distribution(rows: Iterable[dict[str, Any]], field: str, limit: int = 15) -> list[dict[str, Any]]:
    counter = Counter(str(row.get(field, "") or "").strip() or "(blank)" for row in rows)
    return [{"value": value, "count": count} for value, count in counter.most_common(limit)]


def year_span(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    years = sorted(int(row["edition_year"]) for row in rows if str(row.get("edition_year", "")).strip().isdigit())
    return {"min": years[0], "max": years[-1], "count": len(years)} if years else {"min": None, "max": None, "count": 0}


def build_provenance(
    *,
    input_path: Path | None,
    source_url: str,
    date_checked: str,
    records: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
    pipeline: str,
    relationship_kinds: dict[str, int] | None = None,
    family_stats: dict[str, Any] | None = None,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    input_file = Path(input_path) if input_path else None
    doc: dict[str, Any] = {
        "schema": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pipeline": pipeline,
        "input": {
            "name": input_file.name if input_file else None,
            "sha256": sha256_file(input_file) if input_file and input_file.exists() else None,
            "bytes": input_file.stat().st_size if input_file and input_file.exists() else None,
        },
        "source_url": source_url,
        "date_checked": date_checked,
        "counts": {
            "records": len(records),
            "relationships": len(relationships),
            "relationship_kinds": relationship_kinds or {},
        },
        "coverage": field_coverage(records),
        "type_of_standard": distribution(records, "type_of_standard"),
        "degree_of_equivalence": distribution(records, "degree_of_equivalence"),
        "edition_year_span": year_span(records),
        "families": family_stats or {},
        "notes": notes or [],
    }
    return doc


def write_provenance(doc: dict[str, Any], path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def default_date_checked() -> str:
    return date.today().isoformat()
