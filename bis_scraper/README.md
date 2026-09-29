# Incremental BIS metadata crawler

This package is the acquisition/update layer in the architecture:

```text
BIS catalogue → configured detail-link adapter → detail parser → SQLite change log
                                                  └→ referred-standard edges
SQLite → standards.csv / relationships.csv / standards.json → MVP UI
```

It collects page metadata only; it does not download standard PDFs. The crawler uses a **10-record cap**, 2-second request spacing, a host allowlist, and a `robots.txt` check by default. It stops on 429/503. It keeps SQLite `first_seen`, `last_checked`, `last_changed`, a content hash, and a change log. Re-running it updates existing IDs; it does not overwrite the BIS catalogue export.

## Install and inspect

From the project root:

```powershell
python -m pip install -r bis_scraper/requirements.txt
python -m bis_scraper.scraper --inspect-listing
```

The inspection command fetches only the listing page, checks `robots.txt`, and prints at most 20 candidate anchors. It does not follow detail links or write database rows.

If it reports zero candidates, first inspect the diagnostic page title/text and sample links. If the static response is only an application shell, install the optional browser dependency and repeat in rendered mode:

```powershell
python -m pip install -r bis_scraper/requirements-browser.txt
python -m bis_scraper.scraper --inspect-listing --render-browser
```

This renders only the listing page in headless Chrome, then reports visible DOM links. It still does not crawl standards detail pages.

The rendered catalogue inspection confirmed detail links use `/website/standard-details?encryptedId=…`; the default selector is `a[href*="/standard-details?encryptedId="]`. It also confirmed the catalogue list is JavaScript-rendered, so use `--render-browser` for inspection and crawl. The encrypted query value is passed through as an opaque URL; the scraper does not decode or alter it.

After confirming the selector, set it in PowerShell and run a small batch:

```powershell
python -m bis_scraper.scraper --max-standards 10 --render-browser --confirm-terms-reviewed
```

The explicit confirmation flag is an operator attestation that applicable BIS terms/licensing have been reviewed and this metadata collection is authorized. The crawler refuses a non-BIS host and robots-disallowed pages. The per-run cap defaults to 10; increase it only after validating detail parsing and request policy.

Outputs:

- `data/bis_metadata.sqlite3` — current metadata, referred edges, crawl timestamps, and change log
- `data/bis_crawl/standards.csv` and `relationships.csv` — reviewable exports
- `data/bis_crawl/standards.json` — crawler staging data; merge the CSV exports with `npm run index:crawl` before the deployed search index changes
- `logs/bis_scraper.log` — run log

## Boundaries and next adapter work

This is an incremental crawler, not a full-catalogue crawler yet. It currently handles one listing page and needs browser mode for the JavaScript-rendered catalogue. Pagination and exact detail-field extraction still need validation on a small sample before expanding. If any field is absent or the page layout changes, missing values are preserved during updates. An empty/absent reference section does not erase stored edges. Referred links are labeled `referred`; the crawler does not guess normative/test/safety relationship types. A partial crawl is not the active search catalog until it is merged with the full catalogue and the browser index is rebuilt.

Start with 10 records, inspect parser output, then expand deliberately. Add a scheduled weekly/monthly invocation only after the list pagination and rate policy are verified. The current app uses keyword-overlap candidate ranking; vector embeddings, reranking, PostgreSQL, and automatic scheduler integration are later architecture stages.
