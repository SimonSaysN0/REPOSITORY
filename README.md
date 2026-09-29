# StandardLens MVP

A small browser prototype for the Indian Standards procurement recommendation workflow. It demonstrates requirement extraction, candidate ranking, match explanations, recorded relationships, and CSV export.

## Run locally

Open `index.html` in a modern browser for demo fixtures. To load an imported catalogue, serve this directory so the browser can fetch its JSON:

```powershell
python -m http.server 8000
```

Open `http://localhost:8000`.

## BIS catalogue export workflow

The importer is export-first. Check whether the BIS portal's Export to Excel/CSV provides suitable metadata before considering browser automation. No undocumented endpoint is assumed. This project does not download full standard documents.

1. Export permitted catalogue metadata from BIS to CSV or XLSX.
2. Run this from the project directory and pass the actual catalogue URL you used:

   ```powershell
   python scripts/prepare_bis_data.py .\your-bis-export.xlsx --source-url "https://standards.bis.gov.in/website/published-standards/published-standards-list" --date-checked 2026-09-29
   ```

3. The importer writes `data/bis_standards.csv`, `data/standard_relationships.csv`, and `data/standards.json`. It recognizes common column names in CSV or XLSX, preserves missing values as blank, derives a year only when it appears in the standard number, extracts recognizable standard identifiers from a referred-standards field, flags duplicate/incomplete rows, and stamps the check date. To include a separate manually reviewed relationships CSV, add `--relationships .\my-relationships.csv`.
4. Run the local server and reload. The UI loads non-empty `data/standards.json` in place of the fixtures and displays source links. Results remain keyword-overlap candidates for human review.

The starter schemas are in `data/*.template.csv`. The importer cannot infer official product categories, scopes, relationship types (for example, whether a referred standard is normative or a test method), or whether certification is legally mandatory. Populate those only from authorized, authoritative evidence. It does not crawl detail pages. Inspect the export and a sample detail record before deciding whether automation is appropriate.

The attached `File_Published_Standards_List_2026-09-29_011114.xlsx` export has been imported. It yielded 23,866 records with standard number, title, type, degree of equivalence, and publication date where present. This export did not include scopes, department, committee, classifications, status, amendments, certification, or referred-standard links; those fields remain blank. Its `IS 12345:2026`-style year is carried into `edition_year`. The frontend loads `data/standards.json` when served over HTTP.

## Automated detail-crawl architecture

An incremental metadata-only crawler scaffold now lives in [bis_scraper](bis_scraper/README.md). It writes to SQLite with first-seen/last-checked/last-changed dates, a change log, and referred-standard edges; it exports CSV and JSON for the MVP UI. Each run is capped at 10 detail records by default, applies request spacing, checks `robots.txt`, and does not fetch standard PDFs. It does not overwrite the exported catalogue seed.

The BIS portal's actual detail-link selector, pagination, and rendered response have not yet been verified, so the crawler intentionally requires a configured selector. First run its listing inspection command and inspect the current DOM. Do not increase the record cap or schedule recurring runs until the parser, access rules, and licensing have been reviewed. The UI prefers crawl JSON when it exists and otherwise uses the imported XLSX catalogue JSON.

## Current limitations

`DEMO-*` rows in `app.js` are fictional placeholders, not BIS standards. Matching uses keyword overlap and recorded links, not semantic AI retrieval. BIS certification/QCO validation, expert-reviewed applicability, persistent history, backend embeddings, and PDF/DOCX extraction are not implemented. TXT upload works; paste extracted PDF/DOCX text into the input.

## Dataset to provide

For the first real pilot, provide the BIS catalogue CSV export (for one domain or the full permitted catalogue) and the exact page URL used to export it. Also provide any authorized detail metadata and relationships as `source_is,target_is,relationship,source_url`, plus 5–10 tender descriptions with expert-reviewed expected standards. Certification/QCO data should include product, order/scheme, effective date, official source, and verification date.

Do not add restricted full-text standards to this prototype. Follow BIS access and licensing terms for metadata and derived content.
