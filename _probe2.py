"""Temporary probe #2: inspect non-standard IS numbers and prefixes (safe to delete)."""
import collections
import csv
import re

csv.field_size_limit(10 ** 7)
rows = list(csv.DictReader(open(r"data/bis_standards.csv", encoding="utf-8-sig", newline="")))
FAMILY = re.compile(r"^\s*((?:IS|ISO|IEC)(?:\s*/\s*(?:ISO|IEC))?)\s*(\d+[A-Z]?)(.*)$", re.I)
unparsed = [r["is_number"] for r in rows if not FAMILY.match(r["is_number"])]
print("unparsed count", len(unparsed))
for sample in unparsed[:30]:
    print("  ", repr(sample))
prefix = collections.Counter()
for r in rows:
    head = re.split(r"[\s\d]", r["is_number"], 1)[0]
    prefix[head] += 1
print("prefixes", prefix.most_common(25))
weird_titles = [r["title"] for r in rows if "\ufffd" in r["title"]]
print("replacement-char titles", len(weird_titles), weird_titles[:3])
print("titles with trailing dash", sum(1 for r in rows if r["title"].rstrip().endswith("-")))
for r in rows:
    if r["type_of_standard"] == "-":
        print("type '-' example:", r["is_number"], "|", r["title"][:80])
        break
