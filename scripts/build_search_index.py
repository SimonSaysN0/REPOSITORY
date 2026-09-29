#!/usr/bin/env python3
"""Rebuild every UI artifact from the tracked reviewed CSV export.

The original BIS XLSX download is not stored in this repository, so this script
makes the pipeline reproducible from what *is* tracked: data/bis_standards.csv
plus data/standard_relationships.csv. It regenerates the canonical
data/standards.json, the compact browser index (data/search_index.json and its
gzip sibling) and data/provenance.json, carrying forward the hash of the
original export when it was recorded by an earlier import.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from standardlens import __version__
from standardlens.families import group_families
from standardlens.indexing import build_index, write_index
from standardlens.provenance import build_provenance, field_coverage, write_provenance

ROOT = Path(__file__).resolve().parents[1]
csv.field_size_limit(10 ** 7)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise SystemExit(f"Missing required file: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            raise SystemExit(f"{path} has no header row")
        return [dict(row) for row in reader]


def previous_upstream(provenance_path: Path) -> dict:
    """Keep the hash of the original BIS export across regenerations."""
    if not provenance_path.exists():
        return {}
    try:
        previous = json.loads(provenance_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    stored = previous.get("upstream") or (previous.get("input") if str(previous.get("input", {}).get("name", "")).lower().endswith(".xlsx") else None)
    if not stored:
        return {}
    return {**stored, "recorded_at": previous.get("generated_at"), "source_url": previous.get("source_url")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--standards-csv", type=Path, default=ROOT / "data" / "bis_standards.csv")
    parser.add_argument("--relationships-csv", type=Path, default=ROOT / "data" / "standard_relationships.csv")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--source-url", default="", help="Override the BIS page URL recorded in provenance")
    parser.add_argument("--date-checked", default="", help="Override the ISO date recorded in provenance")
    parser.add_argument("--no-gzip", action="store_true", help="Skip the .gz index sibling")
    args = parser.parse_args()

    records = read_csv(args.standards_csv)
    if not records:
        raise SystemExit(f"{args.standards_csv} contains no rows")
    relationships = read_csv(args.relationships_csv) if args.relationships_csv.exists() else []

    provenance_path = args.out_dir / "provenance.json"
    previous = {}
    if provenance_path.exists():
        try:
            previous = json.loads(provenance_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            previous = {}
    source_url = args.source_url or previous.get("source_url", "")
    date_checked = args.date_checked or previous.get("date_checked") or date.today().isoformat()

    ids = [row.get("is_number", "") for row in records]
    families = group_families(ids)
    kinds: dict[str, int] = {}
    for edge in relationships:
        kind = (edge.get("relationship") or "referred_standard").strip()
        kinds[kind] = kinds.get(kind, 0) + 1

    coverage = field_coverage(records)
    index = build_index(
        records,
        relationships,
        pipeline=f"csv_rebuild {__version__}",
        coverage=coverage,
        source={
            "kind": "reviewed_catalogue_export",
            "file": args.standards_csv.name,
            "source_url": source_url,
            "date_checked": date_checked,
            "pipeline": f"csv_rebuild {__version__}",
        },
    )
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "standards.json").write_text(
        json.dumps({"records": records, "relationships": relationships}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    written = write_index(index, args.out_dir / "search_index.json", None if args.no_gzip else args.out_dir / "search_index.json.gz")

    doc = build_provenance(
        input_path=args.standards_csv,
        source_url=source_url,
        date_checked=date_checked,
        records=records,
        relationships=relationships,
        pipeline=f"csv_rebuild {__version__}",
        relationship_kinds=kinds,
        family_stats={"groups": len(families), "members": sum(len(m) for m in families.values())},
        notes=[
            "Rebuilt from the tracked reviewed CSV; the original BIS export is not stored in this repository.",
            "Fields with 0% coverage were absent from the source export, not verified as empty by BIS.",
        ],
    )
    upstream = previous_upstream(provenance_path) or (previous.get("input") if previous else {})
    if upstream:
        doc["upstream"] = upstream
    write_provenance(doc, provenance_path)

    print(f"Records: {len(records)}  relationships: {len(relationships)}  families: {len(families)}")
    print(f"Index: {written[0]} ({written[0].stat().st_size/1_048_576:.2f} MB), terms {index['stats']['terms']}, postings {index['stats']['postings']}")
    if len(written) > 1:
        print(f"       {written[1]} ({written[1].stat().st_size/1_048_576:.2f} MB gzipped)")
    print(f"Provenance: {provenance_path}")
    empty = [field for field, info in coverage.items() if info["filled"] == 0]
    if empty:
        print(f"Fields with no data in the source export: {', '.join(empty)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
