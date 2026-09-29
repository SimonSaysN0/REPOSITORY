"""Temporary profiling probe for the BIS catalogue CSV (safe to delete)."""
import collections
import csv
import json
import re

csv.field_size_limit(10 ** 7)
rows = list(csv.DictReader(open(r"data/bis_standards.csv", encoding="utf-8-sig", newline="")))
print("rows", len(rows))
print("coverage", json.dumps({k: sum(1 for r in rows if (r.get(k) or "").strip()) for k in rows[0]}))
print("types", collections.Counter((r["type_of_standard"] or "").strip() for r in rows).most_common(25))
print("equiv", collections.Counter((r["degree_of_equivalence"] or "").strip() for r in rows).most_common(8))
print("years", collections.Counter((r["edition_year"] or "").strip() for r in rows).most_common(8))

FAMILY = re.compile(r"^\s*((?:IS|ISO|IEC)(?:\s*/\s*(?:ISO|IEC))?)\s*(\d+[A-Z]?)(.*)$", re.I)
fam, unparsed = collections.Counter(), 0
for r in rows:
    m = FAMILY.match(r["is_number"])
    if not m:
        unparsed += 1
        continue
    fam[m.group(1).upper().replace(" ", "") + " " + m.group(2).upper()] += 1
multi = {k: v for k, v in fam.items() if v > 1}
print("unparsed", unparsed, "distinct bases", len(fam), "bases>1", len(multi),
      "members in multi", sum(multi.values()), "max", max(fam.values()), "top", fam.most_common(12))

STOP = set("the of for and with from to in on a an is are by as at be this from methods test sampling determination "
           "specification requirements code practice india indian standard standards part section guidelines terms".split())


def tokens(text):
    return [w for w in re.findall(r"[a-z0-9][a-z0-9.\-]*", text.lower()) if len(w) > 2 and w not in STOP]


uniq, total = set(), 0
for r in rows:
    ws = set(tokens(r["title"]))
    uniq |= ws
    total += len(ws)
print("unique title terms", len(uniq), "postings", total, "avg/rec", round(total / len(rows), 2))

non_is = [r["is_number"] for r in rows if not r["is_number"].startswith("IS ")]
print("non-IS-prefixed", len(non_is), non_is[:12])
dupes = [k for k, c in collections.Counter(r["is_number"].casefold() for r in rows).items() if c > 1]
print("duplicate ids", len(dupes), dupes[:5])
print("part-style examples", [r["is_number"] for r in rows if "(Part" in r["is_number"]][:6])
print("avg title len", round(sum(len(r["title"]) for r in rows) / len(rows), 1))
