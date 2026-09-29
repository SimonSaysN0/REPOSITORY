#!/usr/bin/env python3
"""Normalize a BIS catalogue CSV export without downloading standard documents.

This is intentionally an export importer, not a portal scraper. It does not
guess undocumented endpoints or synthesize missing BIS metadata.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STANDARDS_OUT = ROOT / "data" / "bis_standards.csv"
RELATIONS_OUT = ROOT / "data" / "standard_relationships.csv"
JSON_OUT = ROOT / "data" / "standards.json"

FIELDS = [
    "is_number", "title", "edition_year", "publication_date", "degree_of_equivalence", "scope", "department",
    "technical_committee", "type_of_standard", "sector", "product_category",
    "status", "number_of_revisions", "number_of_amendments", "amendment_year",
    "reaffirmation_year", "certification", "referred_standards",
    "superseding_standard", "source_url", "date_checked", "scope_source",
]
REL_FIELDS = ["source_is", "target_is", "relationship", "source_url", "date_checked"]

ALIASES = {
    "is_number": ["is number", "standard number", "standard no", "standardno", "is no", "is_number"],
    "title": ["title", "standard title", "name", "standard name"],
    "edition_year": ["edition year", "year", "edition", "publication year", "edition_year"],
    "publication_date": ["date of publish", "date published", "publication date", "published on"],
    "degree_of_equivalence": ["degree of equivalence", "equivalence", "equivalence degree"],
    "scope": ["scope", "scope of standard", "abstract", "description"],
    "department": ["department", "department name"],
    "technical_committee": ["technical committee", "committee", "committee number", "technical_committee"],
    "type_of_standard": ["type", "type of standard", "standard type", "type_of_standard"],
    "sector": ["classification", "sector", "classification details"],
    "product_category": ["product category", "category", "product_category"],
    "status": ["status", "standard status"],
    "number_of_revisions": ["revisions", "number of revisions", "revision count"],
    "number_of_amendments": ["amendments", "number of amendments", "amendment count"],
    "amendment_year": ["amendment year", "latest amendment year"],
    "reaffirmation_year": ["reaffirmation year", "reaffirmed year"],
    "certification": ["certification", "certification status", "mandatory certification"],
    "referred_standards": ["referred standards", "referred indian standards", "references", "referenced standards"],
    "superseding_standard": ["superseding standard", "superseded by", "replaced by"],
    "source_url": ["source url", "url", "link"],
}
IS_PATTERN = re.compile(r"\b(?:IS|ISO|IEC|IS/ISO|IS/IEC)\s*[/A-Z]*\s*\d+[A-Z]?(?:\s*:\s*\d{4})?\b", re.I)


def norm_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").strip().lower()).strip()


def read_xlsx(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Read the first worksheet that has recognizable IS-number and title headers."""
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    def col_index(cell_ref: str) -> int:
        letters = re.match(r"[A-Z]+", cell_ref.upper())
        value = 0
        for char in letters.group(0) if letters else "A":
            value = value * 26 + ord(char) - 64
        return value - 1
    with zipfile.ZipFile(path) as book:
        strings: list[str] = []
        if "xl/sharedStrings.xml" in book.namelist():
            root = ET.fromstring(book.read("xl/sharedStrings.xml"))
            strings = ["".join(t.text or "" for t in item.findall(".//m:t", ns)) for item in root.findall("m:si", ns)]
        for sheet_path in sorted((n for n in book.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n))):
            root = ET.fromstring(book.read(sheet_path))
            rows: list[list[str]] = []
            for row in root.findall(".//m:sheetData/m:row", ns):
                values: list[str] = []
                for cell in row.findall("m:c", ns):
                    idx = col_index(cell.attrib.get("r", "A1"))
                    while len(values) <= idx: values.append("")
                    value = cell.find("m:v", ns)
                    if cell.attrib.get("t") == "s" and value is not None:
                        text = strings[int(value.text or "0")]
                    elif cell.attrib.get("t") == "inlineStr":
                        text = "".join(t.text or "" for t in cell.findall(".//m:t", ns))
                    else:
                        text = value.text if value is not None and value.text else ""
                    values[idx] = text.strip()
                rows.append(values)
            for header_i, headers in enumerate(rows):
                normalized = {norm_header(h) for h in headers if h}
                has_number = any(norm_header(alias) in normalized for alias in ALIASES["is_number"])
                has_title = any(norm_header(alias) in normalized for alias in ALIASES["title"])
                if has_number and has_title:
                    headers = [h or f"column_{i+1}" for i, h in enumerate(headers)]
                    records = []
                    for row in rows[header_i+1:]:
                        padded = row + [""] * max(0, len(headers)-len(row))
                        if any(str(v).strip() for v in padded):
                            records.append(dict(zip(headers, padded)))
                    return headers, records
    raise ValueError("No worksheet contained recognizable IS number and title columns")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_file", type=Path, help="BIS catalogue export as CSV or XLSX")
    parser.add_argument("--relationships", type=Path, help="Optional reviewed CSV with source_is,target_is,relationship,source_url")
    parser.add_argument("--source-url", default="", help="BIS page URL from which the export was obtained")
    parser.add_argument("--date-checked", default=date.today().isoformat(), help="ISO date, defaults to today")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "data")
    args = parser.parse_args()
    if not args.input_file.exists():
        parser.error(f"Input file not found: {args.input_file}")
    try:
        args.date_checked = date.fromisoformat(args.date_checked).isoformat()
    except ValueError:
        parser.error("--date-checked must use YYYY-MM-DD")

    try:
        if args.input_file.suffix.lower() == ".xlsx":
            fieldnames, source_rows = read_xlsx(args.input_file)
        elif args.input_file.suffix.lower() == ".csv":
            with args.input_file.open("r", encoding="utf-8-sig", newline="") as stream:
                reader = csv.DictReader(stream)
                if not reader.fieldnames: parser.error("CSV has no header row")
                fieldnames, source_rows = reader.fieldnames, list(reader)
        else:
            parser.error("Input must be a .csv or .xlsx file")
    except (zipfile.BadZipFile, KeyError, ValueError) as exc:
        parser.error(f"Could not read the BIS export: {exc}")
    headers = {norm_header(h): h for h in fieldnames}
    mapping: dict[str, str | None] = {}
    for field, aliases in ALIASES.items():
        mapping[field] = next((headers[norm_header(a)] for a in aliases if norm_header(a) in headers), None)
    if not mapping["is_number"] or not mapping["title"]:
        parser.error("Could not identify the required IS number and title columns. Rename columns or extend ALIASES in this script.")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    standards_path = args.out_dir / "bis_standards.csv"
    relations_path = args.out_dir / "standard_relationships.csv"
    json_path = args.out_dir / "standards.json"
    cleaned: list[dict[str, str]] = []
    relations: list[dict[str, str]] = []
    seen: set[str] = set()
    issues: list[str] = []
    for line, raw in enumerate(source_rows, start=2):
        row = {field: (str(raw.get(source, "") or "").strip() if source else "") for field, source in mapping.items()}
        row["is_number"] = re.sub(r"\s+", " ", row["is_number"])
        row["title"] = re.sub(r"\s+", " ", row["title"])
        if not row["edition_year"]:
            year_match = re.search(r":(\d{4})\s*$", row["is_number"])
            if year_match: row["edition_year"] = year_match.group(1)
        if "\ufffd" in row["title"]:
            issues.append(f"line {line}: title contains a replacement character; review source export text")
        if not row["is_number"] or not row["title"]:
            issues.append(f"line {line}: skipped; missing IS number or title")
            continue
        key = row["is_number"].casefold()
        if key in seen:
            issues.append(f"line {line}: duplicate IS number {row['is_number']}; retained first row")
            continue
        seen.add(key)
        row["scope_source"] = "BIS export" if row["scope"] else ""
        row["source_url"] = row["source_url"] or args.source_url
        row["date_checked"] = args.date_checked
        refs = row["referred_standards"]
        for target in dict.fromkeys(x.strip() for x in IS_PATTERN.findall(refs)):
            if target.casefold() != row["is_number"].casefold():
                relations.append({"source_is": row["is_number"], "target_is": re.sub(r"\s+", " ", target),
                                  "relationship": "referred_standard", "source_url": row["source_url"],
                                  "date_checked": args.date_checked})
        cleaned.append({field: row.get(field, "") for field in FIELDS})

    if args.relationships:
        with args.relationships.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            required = {"source_is", "target_is", "relationship"}
            if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
                parser.error("--relationships needs source_is,target_is,relationship columns")
            for edge in reader:
                source, target, kind = (edge.get("source_is", "").strip(), edge.get("target_is", "").strip(), edge.get("relationship", "").strip())
                if source and target and kind:
                    relations.append({"source_is": source, "target_is": target, "relationship": kind,
                                      "source_url": edge.get("source_url", "").strip() or args.source_url,
                                      "date_checked": args.date_checked})
    unique_relations = {}
    for edge in relations:
        key = (edge["source_is"].casefold(), edge["target_is"].casefold(), edge["relationship"].casefold())
        unique_relations.setdefault(key, edge)
    relations = list(unique_relations.values())

    with standards_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS); writer.writeheader(); writer.writerows(cleaned)
    with relations_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=REL_FIELDS); writer.writeheader(); writer.writerows(relations)
    json_path.write_text(json.dumps({"records": cleaned, "relationships": relations}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Imported {len(cleaned)} standards and {len(relations)} referred-standard links.")
    print(f"Standards: {standards_path}\nRelationships: {relations_path}\nJSON: {json_path}")
    if issues:
        print(f"Review {len(issues)} import issue(s):", file=sys.stderr)
        for item in issues[:30]: print(f"  - {item}", file=sys.stderr)
        if len(issues) > 30: print(f"  ... and {len(issues)-30} more", file=sys.stderr)
    missing_url = sum(not x["source_url"] for x in cleaned)
    if missing_url: print(f"Note: {missing_url} rows have no source URL; provide --source-url or an export URL column.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
