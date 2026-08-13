# Evidence and review explorers

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

`full_corpus_review.html` is a separate operational console for the complete 2018–2025 coding
workspace. It embeds all 4,441 review targets: 2,003 document dispositions, 1,952 adjudication
starters, and 486 frozen exclusion-QA checks. It is intentionally labeled
`blocked_pending_human_review` and does not publish consistency, competitive-impact, or nationality
effect estimates.

Rebuild it only from a workspace that passes the edited-workspace lineage validator:

```powershell
f1stewards build-full-corpus-review-explorer `
  data/manual/full_corpus_workspaces/full-coding-e0192ecbd9e4
```

Reviewer edits remain in browser-local draft state until exported. Apply an exported ledger to a
separate workspace copy with:

```powershell
f1stewards apply-full-corpus-review-ledger `
  data/manual/full_corpus_workspaces/full-coding-e0192ecbd9e4 `
  <exported-review-ledger.json>
```

The ledger contains only editable final fields and is bound to the exact source-workspace SHA-256.
Stale ledgers, unknown IDs, protected-field changes, and invalid edited workspaces fail closed. The
browser cannot create supported one-to-many adjudication splits; use the documented CSV split
procedure and rebuild the console for those cases.

`full_corpus_first_pass_review.html` is the same review interface rebuilt over conservative first
pass `first-pass-29113bebd312`. It shows 1,696 document and 1,649 adjudication rows as
`single_coded_pending_human`, while 307 document exceptions, 303 adjudication exceptions, and all
486 exclusion-QA checks remain unstarted. It is the operational starting point for source-level
review; `full_corpus_review.html` remains the untouched-starter reference.
