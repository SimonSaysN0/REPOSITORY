"""Temporary smoke test for standardlens helpers (safe to delete)."""
from standardlens.families import family_key, parse_number, part_label
from standardlens.tokenizer import STOPWORDS, tokenize
from standardlens.indexing import build_index, write_index

SAMPLES = [
    "IS 12437:2026", "IS 6092 (Part 6):2026", "IS 101 (Part 2/Sec 6):2026", "IS/ISO/IEC 30161 (Part 1):2020",
    "IS/ISO/IEC/IEEE 88021509 (Part 15/Sec 9):2024", "SP 7:2026", "IS/ISO/IECTR 20226:2025",
    "IS/ISO/IEC 20540:2025 P", "Is 402:2024", "IS/QC 122:2020", "ISO/SAE 2161:2022", "", "nonsense",
]
for sample in SAMPLES:
    p = parse_number(sample)
    print(f"{sample!r:48} fam={p.family!r:24} part={p.part!r:18} year={p.year!r:6} suffix={p.suffix!r}")
print("families in sample:", {s: family_key(s) for s in SAMPLES[:6]})
print("stopwords", len(STOPWORDS))
print("tokens", tokenize("PVC insulated copper electrical cables, 1.1 kV, suitable for industrial applications."))
print("tokens2", tokenize("Methods of sampling and test for Fertilizers: Part 6 Determination of moisture"))
rows = [
    {"is_number": "IS 101 (Part 2):2015", "title": "Electrical cables Part 2", "type_of_standard": "Product Specification"},
    {"is_number": "IS 101 (Part 5):2018", "title": "Electrical cables Part 5 test method", "type_of_standard": "Methods of Tests"},
    {"is_number": "IS 9999:2020", "title": "Zirconium powder test methods", "type_of_standard": "Methods of Tests", "scope": ""},
]
idx = build_index(rows, [{"source_is": "IS 101 (Part 2):2015", "target_is": "IS MISSING:1999", "relationship": "referred_standard"}])
print("columns", idx["columns"])
for row in idx["records"]:
    print("row", row)
print("families", idx["families"])
print("postings sample", {k: v for k, v in list(idx["postings"].items())[:6]})
print("rel", idx["relationships"], "stats", idx["stats"])
paths = write_index(idx, __import__("pathlib").Path("_tmp_index.json"), __import__("pathlib").Path("_tmp_index.json.gz"))
print("written", [(p.name, p.stat().st_size) for p in paths])
