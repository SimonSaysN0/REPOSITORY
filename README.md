# StandardLens

Static browser MVP for discovering candidate Indian Standards from procurement descriptions. It searches a compact prebuilt catalogue index, shows source metadata and identifier-family relationships, and exports results to CSV. Search is lexical BM25-style retrieval, not semantic AI or official standards advice.

The current index covers 23,866 BIS catalogue records. The source export has titles, identifiers, standard types, publication dates, equivalence, and year information; it has no scope, status, amendment, certification, or referred-standard data. The UI shows these gaps instead of inventing values.

## Run locally

```powershell
npm run dev
```

Open `http://localhost:8000`. Python is used only to serve the static files locally. You can also use `python -m http.server 8000`.

## Search index workflow

The source CSV and Python index builder stay out of the deployed site. If you update the source data, rebuild the canonical data, provenance report, and browser index, then commit the changed deployable index artifacts:

```powershell
python scripts/prepare_bis_data.py .\new-bis-export.xlsx --source-url "https://standards.bis.gov.in/website/published-standards/published-standards-list?selectedType=7&totalRow=1" --date-checked YYYY-MM-DD
npm run index
npm test
```

After a reviewed crawler batch, merge its non-empty metadata fields and edges into the full catalogue, then rebuild the index:

```powershell
npm run index:crawl
npm test
```

`npm run index` reads `data/bis_standards.csv` and `data/standard_relationships.csv`, writes `data/search_index.json`, its gzip sibling, and `data/provenance.json`. The browser prefers the gzip index and falls back to the plain JSON index or catalogue JSON. Search index assets are public static files; do not include restricted full standard text.

## Vercel deployment

This is a static site; the Python importer, crawler, and index builder do not run on Vercel. The repository `vercel.json` selects the `Other` preset, skips a build, serves the project root, sets security headers, and caches `/data` assets. `.vercelignore` excludes source CSVs, large raw JSON, crawler databases/logs, tests, and scratch files while retaining the browser index.

1. Import this repository into Vercel.
2. Set **Root Directory** to `.` and **Framework Preset** to **Other**. Leave **Build Command** empty and use the repository root as the output directory. Those are the documented settings for a static project with no build step.
3. Deploy. `index.html`, `app.js`, `search.js`, `styles.css`, and `data/search_index.json.gz` must be present in the deployment.

For local checks, run:

```powershell
npm test
node --check app.js
node --check search.js
python -m compileall -q scripts standardlens bis_scraper
```

The smoke tests verify that the browser index is reachable and decodes, that search returns plausible candidates, and that deployment-ignored files stay out of the static artifact.

## BIS metadata acquisition

The attached XLSX export is imported to CSV locally. An incremental metadata-only crawler is in `bis_scraper/`; it has a verified detail-link selector from the rendered catalogue output, but the detail-field parser and list pagination still need validation. Start with a small capped run only after reviewing BIS access/licensing terms. It checks `robots.txt`, rate-limits requests, tracks changes in SQLite, and never downloads standard PDFs. `npm run index:crawl` merges reviewed crawl exports with the full catalogue before the static index is redeployed. The crawler is not a Vercel function.

Do not label a referred standard as a normative reference, test method, or safety standard unless the source establishes that relationship. Certification/QCO recommendations and current-status claims need their own authoritative, dated source.
