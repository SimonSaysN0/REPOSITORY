from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

STANDARD_FIELDS = ["is_number", "title", "edition_year", "publication_date", "department", "technical_committee", "type_of_standard", "sector", "status", "number_of_revisions", "number_of_amendments", "amendment_year", "reaffirmation_year", "certification", "superseding_standard", "source_url"]


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS standards (
          is_number TEXT PRIMARY KEY, title TEXT, edition_year TEXT, publication_date TEXT, department TEXT,
          technical_committee TEXT, type_of_standard TEXT, sector TEXT, status TEXT,
          number_of_revisions TEXT, number_of_amendments TEXT, amendment_year TEXT,
          reaffirmation_year TEXT, certification TEXT, superseding_standard TEXT,
          source_url TEXT, first_seen TEXT NOT NULL, last_checked TEXT NOT NULL,
          last_changed TEXT NOT NULL, content_hash TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS relationships (
          source_is TEXT NOT NULL, target_is TEXT NOT NULL, relationship_type TEXT NOT NULL,
          source_url TEXT NOT NULL, last_checked TEXT NOT NULL,
          PRIMARY KEY(source_is,target_is,relationship_type)
        );
        CREATE TABLE IF NOT EXISTS change_log (
          id INTEGER PRIMARY KEY, is_number TEXT NOT NULL, changed_at TEXT NOT NULL,
          old_values TEXT, new_values TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS crawl_state (
          key TEXT PRIMARY KEY, value TEXT NOT NULL
        );
        """)
        self.db.commit()

    @staticmethod
    def now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def save(self, data: dict[str, str], references: list[str]) -> bool:
        is_number = data.get("is_number", "").strip()
        if not is_number: return False
        now = self.now()
        old = self.db.execute("SELECT * FROM standards WHERE is_number=?", (is_number,)).fetchone()
        values = {field: (data.get(field) or "").strip() for field in STANDARD_FIELDS}
        values["is_number"] = is_number
        if old is not None:
            # An unrecognized or absent field on a later page parse must not erase known metadata.
            for field in STANDARD_FIELDS:
                if not values[field]: values[field] = old[field] or ""
        old_refs = [r[0] for r in self.db.execute("SELECT target_is FROM relationships WHERE source_is=? AND relationship_type='referred' ORDER BY target_is", (is_number,))]
        effective_refs = sorted(set(references)) if references else old_refs
        serialized = json.dumps({"fields": values, "referred_standards": effective_refs}, ensure_ascii=False, sort_keys=True)
        digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        if old is None:
            insert = values | {"first_seen": now, "last_checked": now, "last_changed": now, "content_hash": digest}
            cols = list(insert)
            self.db.execute(f"INSERT INTO standards ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})", [insert[c] for c in cols])
            old_values = None
            changed = True
        else:
            previous = {field: old[field] or "" for field in STANDARD_FIELDS}
            changed = old["content_hash"] != digest
            self.db.execute("UPDATE standards SET " + ",".join(f"{f}=?" for f in STANDARD_FIELDS) + ",last_checked=?,last_changed=?,content_hash=? WHERE is_number=?",
                            [values[f] for f in STANDARD_FIELDS] + [now, now if changed else old["last_changed"], digest, is_number])
            old_values = {k: v for k, v in previous.items() if v != values[k]} if changed else None
        if changed:
            self.db.execute("INSERT INTO change_log(is_number,changed_at,old_values,new_values) VALUES(?,?,?,?)",
                            (is_number, now, json.dumps(old_values, ensure_ascii=False) if old_values is not None else None, serialized))
        if references:
            self.db.execute("DELETE FROM relationships WHERE source_is=?", (is_number,))
            self.db.executemany("INSERT OR REPLACE INTO relationships VALUES(?,?,?,?,?)",
                                [(is_number, target, "referred", values["source_url"], now) for target in dict.fromkeys(references) if target.casefold() != is_number.casefold()])
        self.db.commit()
        return changed

    def export_csv(self, out_dir: Path) -> tuple[Path, Path]:
        out_dir.mkdir(parents=True, exist_ok=True)
        standards_path, relations_path = out_dir / "standards.csv", out_dir / "relationships.csv"
        with standards_path.open("w", encoding="utf-8-sig", newline="") as f:
            cols = STANDARD_FIELDS + ["first_seen", "last_checked", "last_changed"]
            writer = csv.writer(f); writer.writerow(cols)
            for row in self.db.execute(f"SELECT {','.join(cols)} FROM standards ORDER BY is_number"):
                writer.writerow([row[c] for c in cols])
        with relations_path.open("w", encoding="utf-8-sig", newline="") as f:
            cols = ["source_is", "target_is", "relationship_type", "source_url", "last_checked"]
            writer = csv.writer(f); writer.writerow(cols)
            for row in self.db.execute(f"SELECT {','.join(cols)} FROM relationships ORDER BY source_is,target_is"):
                writer.writerow([row[c] for c in cols])
        records = [dict(row) for row in self.db.execute("SELECT * FROM standards ORDER BY is_number")]
        relations = [dict(row) for row in self.db.execute("SELECT source_is,target_is,relationship_type AS relationship,source_url,last_checked FROM relationships ORDER BY source_is,target_is")]
        (out_dir / "standards.json").write_text(json.dumps({"source": "bis_incremental_crawl", "records": records, "relationships": relations}, ensure_ascii=False), encoding="utf-8")
        return standards_path, relations_path

    def count(self) -> int:
        return int(self.db.execute("SELECT COUNT(*) FROM standards").fetchone()[0])

    def close(self) -> None:
        self.db.close()
