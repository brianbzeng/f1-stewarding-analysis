# Full-Corpus Review Console

Status: implemented and validated; analytical release remains blocked pending human review.

## Purpose

The console converts the three protected 2018–2025 coding worklists into a portable evidence-review
surface. It is an operational control, not a statistical dashboard. Its current build covers:

| Queue | Review unit | Rows | Independently complete |
|---|---|---:|---:|
| Document dispositions | FIA archive outcome label | 2,003 | 0 |
| Adjudication coding | live content-confirmed decision starter | 1,952 | 0 |
| Exclusion QA | frozen hash-selected exclusion check | 486 | 0 |
| **Total** |  | **4,441** | **0** |

Every row links to its official FIA source. Adjudication rows also expose parsed Fact,
Infringement, Decision, and Reason text plus timing-availability context. Suggestions remain visibly
separate from final coding fields.

## Build and identity

```powershell
f1stewards build-full-corpus-review-explorer `
  data/manual/full_corpus_workspaces/full-coding-e0192ecbd9e4
```

The current artifact is [full_corpus_review.html](../explorer/full_corpus_review.html). Before writing
it, the command requires all edited-workspace lineage controls to pass. The embedded build records:

- workspace `full-coding-e0192ecbd9e4`;
- protected seed-manifest SHA-256
  `540082201d4bf4ec98ecbc8f3e26ce17e6c17d883ff017a6fd753204cd4830a5`;
- timing-context SHA-256
  `3227b6dac56635caa08a71a9ba789cecc59bb4557786749d9f997d9531e35264`;
- starter-content SHA-256
  `dec10c707f4e9fa262a3b4f1bfc439fba0cbd73737caf8a7f918aa8e186ea618`; and
- a current-workspace digest over the protected manifest and all three editable CSVs.

The current build passes 19 workspace validation controls and resolves all 4,441 displayed rows to
official FIA URLs.

## Reviewer workflow

1. Choose a queue and follow `workspace_review_order` unless a documented risk-based subset is
   assigned.
2. Filter by season, priority, review status, or free text.
3. Open the official source and compare it with the machine suggestion and extracted evidence.
4. Edit only the final fields. Drafts are stored under a workspace-specific browser key.
5. Download a filtered CSV when a smaller offline packet is useful.
6. Export the draft ledger. It contains only changed final fields, never protected source values.
7. Apply it to a separate workspace and rerun the console from that validated output.

```powershell
f1stewards apply-full-corpus-review-ledger `
  data/manual/full_corpus_workspaces/full-coding-e0192ecbd9e4 `
  <exported-review-ledger.json>
```

By default, the result is written to
`data/manual/full_corpus_review_edits/full-coding-e0192ecbd9e4`. The importer rejects a stale source
hash, wrong workspace ID, unknown queue, unknown or repeated row ID, protected-field edit, or
non-scalar value. The CLI then runs the existing edited-workspace validator and exits nonzero if any
lineage or field control fails.

## Release boundary

The console state is `blocked_pending_human_review` while any row remains unresolved. Completing
every row changes only the workspace state to
`workspace_review_complete_pending_feature_controls`. It does not authorize consistency,
competitive-impact, nationality, or fairness claims. Analytical release remains controlled by the
feature builder, independent-review protocol, multi-car relation coding, separate harm records,
model diagnostics, and report acceptance criteria.

The browser ledger edits existing adjudication instances only. When one official source decides
more than one accused-driver case, perform the protected `-02`, `-03`, and later CSV split procedure,
validate the workspace, and rebuild the console before continuing.
