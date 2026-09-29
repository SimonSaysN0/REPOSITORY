"""Build the compact browser search index consumed by search.js.

The MVP used to download a 21 MB pretty-printed catalogue dump and re-tokenize
all 23,866 records in the browser on every search. This module does that work
once, at build time:

* one slim record row per standard (optional columns that are entirely empty in
  the source are dropped, so shallow exports stay small),
* an inverted index of folded title/scope terms -> [record index, term freq, ...],
* identifier families (multi-part series members) so related records can be
  surfaced without inventing BIS relationship types,
* the recorded relationship edges, plus the field coverage the UI displays.

Output is compact JSON and, by default, a gzip sibling the browser inflates with
DecompressionStream.
"""
from __future__ import annotations

import gzip
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .families import group_families, part_label
from .provenance import field_coverage
from .tokenizer import STOPWORDS, tokenize

INDEX_SCHEMA = 2
MAX_TERM_FREQ = 255
CORE_COLUMNS: list[tuple[str, tuple[str, ...]]] = [
    ("id", ("is_number",)),
    ("title", ("title",)),
    ("type", ("type_of_standard",)),
    ("year", ("edition_year",)),
    ("pub", ("publication_date",)),
    ("equiv", ("degree_of_equivalence",)),
    ("fam", ()),   # filled from the computed identifier family
    ("part", ()),  # filled from the parsed identifier
]
OPTIONAL_COLUMNS: list[tuple[str, tuple[str, ...]]] = [
    ("scope", ("scope",)),
    ("dept", ("department",)),
    ("committee", ("technical_committee",)),
    ("sector", ("sector",)),
    ("category", ("product_category",)),
    ("status", ("status",)),
    ("certification", ("certification",)),
    ("revisions", ("number_of_revisions",)),
    ("amendments", ("number_of_amendments",)),
    ("amendment_year", ("amendment_year",)),
    ("reaffirmation", ("reaffirmation_year",)),
    ("supersedes", ("superseding_standard",)),
    ("url", ("source_url",)),
    ("checked", ("date_checked", "last_checked")),
    ("seen", ("first_seen",)),
]
# Fields that contribute terms to the inverted index.
INDEXED_TEXT_FIELDS = ("title", "product_category", "sector", "scope", "technical_committee", "department")
PLACEHOLDERS = {"", "-", "--", "n/a", "na", "not available", "none"}


def _pick(row: dict[str, Any], candidates: Iterable[str]) -> str:
    for field in candidates:
        value = str(row.get(field, "") or "").strip()
        if value and value.lower() not in PLACEHOLDERS:
            return re.sub(r"\s+", " ", value)
    return ""


def indexed_text(row: dict[str, Any]) -> str:
    return " ".join(str(row.get(field, "") or "") for field in INDEXED_TEXT_FIELDS if row.get(field))


def _used_optional_columns(records: list[dict[str, Any]]) -> list[tuple[str, tuple[str, ...]]]:
    used = []
    for name, candidates in OPTIONAL_COLUMNS:
        if any(_pick(row, candidates) for row in records):
            used.append((name, candidates))
    return used



def build_index(
    records: list[dict[str, Any]],
    relationships: list[dict[str, Any]] | None = None,
    *,
    source: dict[str, Any] | None = None,
    pipeline: str = "unknown",
    coverage: dict[str, dict[str, float]] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Turn catalogue rows into the slim, pre-tokenized structure search.js expects."""
    if not records:
        raise ValueError("build_index requires at least one record")
    ids = [str(row.get("is_number", "") or "").strip() for row in records]
    families = group_families(ids)
    member_of = {index: family for family, members in families.items() for index in members}
    optional_used = _used_optional_columns(records)
    columns = [name for name, _ in CORE_COLUMNS] + [name for name, _ in optional_used]

    rows: list[list[str]] = []
    postings: dict[str, list[int]] = {}
    doc_lengths: list[int] = []
    for index, row in enumerate(records):
        family = member_of.get(index, "")
        values = {
            "id": ids[index],
            "title": _pick(row, ("title",)),
            "type": _pick(row, ("type_of_standard",)),
            "year": _pick(row, ("edition_year",)),
            "pub": _pick(row, ("publication_date",)),
            "equiv": _pick(row, ("degree_of_equivalence",)),
            "fam": family,
            "part": part_label(ids[index]) if family else "",
        }
        for name, candidates in optional_used:
            values[name] = _pick(row, candidates)
        rows.append([values[column] for column in columns])

        counts = Counter(tokenize(indexed_text(row)))
        doc_lengths.append(max(len(counts), 1))
        for term, freq in counts.items():
            postings.setdefault(term, []).extend((index, min(freq, MAX_TERM_FREQ)))

    id_to_index = {value.casefold(): index for index, value in enumerate(ids) if value}
    edges: list[dict[str, Any]] = []
    unresolved = 0
    for edge in relationships or []:
        source_is = str(edge.get("source_is", "") or edge.get("s", "") or "").strip()
        target_is = str(edge.get("target_is", "") or edge.get("t", "") or "").strip()
        kind = str(edge.get("relationship", "") or edge.get("relationship_type", "") or edge.get("r", "") or "").strip()
        if not source_is or not target_is or not kind:
            continue
        source_index = id_to_index.get(source_is.casefold())
        if source_index is None:
            continue
        item: dict[str, Any] = {"s": source_index, "r": kind}
        target_index = id_to_index.get(target_is.casefold())
        if target_index is None:
            item["tid"] = target_is
            unresolved += 1
        else:
            item["t"] = target_index
        edges.append(item)

    return {
        "schema": INDEX_SCHEMA,
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pipeline": pipeline,
        "source": source or {},
        "coverage": coverage if coverage is not None else field_coverage(records),
        "stopwords": list(STOPWORDS),
        "columns": columns,
        "records": rows,
        "postings": postings,
        "lens": doc_lengths,
        "families": families,
        "relationships": edges,
        "stats": {
            "records": len(rows),
            "terms": len(postings),
            "postings": sum(len(value) // 2 for value in postings.values()),
            "families": len(families),
            "family_members": sum(len(members) for members in families.values()),
            "relationships": len(edges),
            "unresolved_relationships": unresolved,
        },
    }


def write_index(index: dict[str, Any], json_path: Path, gz_path: Path | None = None) -> list[Path]:
    """Write compact JSON and optionally a gzip sibling for the browser."""
    json_path = Path(json_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(index, ensure_ascii=False, separators=(",", ":"))
    json_path.write_text(payload, encoding="utf-8")
    written = [json_path]
    if gz_path is not None:
        gz_path = Path(gz_path)
        gz_path.parent.mkdir(parents=True, exist_ok=True)
        with gz_path.open("wb") as handle:
            with gzip.GzipFile(filename="", mode="wb", fileobj=handle, compresslevel=9, mtime=0) as compressor:
                compressor.write(payload.encode("utf-8"))
        written.append(gz_path)
    return written
