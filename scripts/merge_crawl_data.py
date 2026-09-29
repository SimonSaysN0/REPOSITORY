#!/usr/bin/env python3
"""Merge verified crawler fields into the full catalogue before rebuilding the UI index."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
csv.field_size_limit(10 ** 7)


def read_rows(path: Path, required: set[str]) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        raise SystemExit(f"Missing input: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise SystemExit(f"{path} must contain columns: {', '.join(sorted(required))}")
        return list(reader.fieldnames), [dict(row) for row in reader]


def write_rows(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=ROOT / "data" / "bis_standards.csv")
    parser.add_argument("--crawl", type=Path, default=ROOT / "data" / "bis_crawl" / "standards.csv")
    parser.add_argument("--base-relationships", type=Path, default=ROOT / "data" / "standard_relationships.csv")
    parser.add_argument("--crawl-relationships", type=Path, default=ROOT / "data" / "bis_crawl" / "relationships.csv")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "data")
    args = parser.parse_args()

    fields, base_rows = read_rows(args.base, {"is_number", "title"})
    crawl_fields, crawl_rows = read_rows(args.crawl, {"is_number"})
    fields = list(dict.fromkeys(fields + [f for f in crawl_fields if f not in {"first_seen", "last_checked", "last_changed"}]))
    by_id = {row["is_number"].strip().casefold(): row for row in base_rows if row.get("is_number", "").strip()}
    enriched = 0
    added = 0
    for incoming in crawl_rows:
        key = incoming.get("is_number", "").strip().casefold()
        if not key: continue
        if key in by_id:
            row = by_id[key]
            before = tuple(row.get(field, "") for field in fields)
            for field in fields:
                value = (incoming.get(field) or "").strip()
                if value: row[field] = value
            if incoming.get("last_checked"):
                row["date_checked"] = incoming["last_checked"]
            if tuple(row.get(field, "") for field in fields) != before: enriched += 1
        else:
            row = {field: (incoming.get(field) or "").strip() for field in fields}
            if incoming.get("last_checked"): row["date_checked"] = incoming["last_checked"]
            if row.get("is_number") and row.get("title"):
                by_id[key] = row; added += 1

    base_rel = []
    if args.base_relationships.exists():
        _, base_rel = read_rows(args.base_relationships, {"source_is", "target_is"})
    crawl_rel = []
    if args.crawl_relationships.exists():
        _, crawl_rel = read_rows(args.crawl_relationships, {"source_is", "target_is"})
    rel_by_key = {}
    for edge in base_rel + crawl_rel:
        source, target = (edge.get("source_is", "").strip(), edge.get("target_is", "").strip())
        kind = (edge.get("relationship") or edge.get("relationship_type") or "referred").strip()
        if not source or not target: continue
        normalized = {"source_is": source, "target_is": target, "relationship": kind,
                      "source_url": edge.get("source_url", ""),
                      "date_checked": edge.get("date_checked") or edge.get("last_checked", "")}
        rel_by_key.setdefault((source.casefold(), target.casefold(), kind.casefold()), normalized)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    standards_out = args.out_dir / "bis_standards_enriched.csv"
    relations_out = args.out_dir / "standard_relationships_enriched.csv"
    write_rows(standards_out, fields, list(by_id.values()))
    write_rows(relations_out, ["source_is", "target_is", "relationship", "source_url", "date_checked"], list(rel_by_key.values()))
    print(f"Base records: {len(base_rows)}; enriched: {enriched}; added: {added}; merged relationships: {len(rel_by_key)}")
    print(f"Search-index inputs: {standards_out} and {relations_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
