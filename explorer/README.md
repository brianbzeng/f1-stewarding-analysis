# Evidence explorer

`index.html` is a generated, dependency-free review artifact for the three-event pilot. Open it in
a browser or serve the repository root with any static file server. The page embeds the curated
pilot extract, so its filters and evidence panels work without a database connection.

Rebuild it from the DuckDB database and manual coding files with:

```powershell
f1stewards build-explorer
```

The pilot artifact is intentionally marked **provisional**. It displays official-source lineage,
candidate coding, mechanical impact calculations, and data-quality state, but it does not publish
nearest-case rankings or substantive consistency findings. Those views remain gated on independent
review, reconciliation, full-corpus collection, and model validation.

The default payload excludes nationality ranking fields. Every adjudication must resolve to an
official FIA decision URL, and each non-unclear 2025 conformance label must resolve to an applicable
public guideline and clause before the build is allowed to complete.
