# Full-Corpus Coding Workspace

Status: deterministic starter generated and validated; final human coding has not begun.

The executed [full-corpus readiness notebook](../notebooks/04_full_corpus_readiness.ipynb) is the
recruiter-facing Jupyter view of this release. It uses the same hashes and worklists and preserves
the blocked human-review gate in its conclusion.

## Release identity

The current local workspace is `full-coding-4b0c0d5ddd72`. It is derived from the committed
`full_corpus_coding_v3` seed release and the complete 197-session FastF1 review context.

| Item | Value |
|---|---:|
| Document dispositions | 2,002 |
| Adjudication starter instances | 1,951 |
| Stratified exclusion-QA rows | 403 |
| Timing sessions | 197 |
| Driver classifications | 3,938 |
| Protected seed-manifest SHA-256 | `6f3a48afe57632e0652f0b354ce14da3cf66465aca7ddb879f9127612b796330` |
| Timing-context SHA-256 | `3227b6dac56635caa08a71a9ba789cecc59bb4557786749d9f997d9531e35264` |
| Workspace-content SHA-256 | `c32cee30d5a4030d87d82eb17973d6e59d994c8cbf61895cc76c37bb57271772` |

The workspace ID hashes the schema version, protected seed manifest, timing context, and generated
worklist content. A source, timing, schema, or transformation change therefore creates a different
directory rather than silently replacing this starter.

Generate and verify it with:

```powershell
f1stewards build-full-coding-workspace
f1stewards audit-full-coding-workspace `
  data/manual/full_corpus_workspaces/full-coding-4b0c0d5ddd72
f1stewards validate-edited-full-coding-workspace `
  data/manual/full_corpus_workspaces/full-coding-4b0c0d5ddd72
```

The generated workspace is intentionally git-ignored because it becomes local human working
state. The source warehouse, rules, protected seed tables, code, tests, and this release record are
committed. Do not edit `data/manual/full_corpus_seed/` or `workspace_manifest.json`.

## Worklists and editing boundary

`document_review_worklist.csv` preserves one row per FIA outcome label. Only its final disposition,
reviewer, status, exclusion reason, and notes fields may be edited.

`adjudication_coding_worklist.csv` begins with one `-01` instance per live content-confirmed
decision. Source text, suggestions, review priority, timing quality, and classification context are
protected. Only the final adjudication fields, coder, status, and notes may be edited. The final
fields include separate corrections for penalty seconds, penalty points, grid places, and written
fault language, so a corrected outcome never inherits an unverified parser value.

A source document that independently decides more than one accused driver's case may be split:

1. retain its original `<adjudication_seed_id>-01` row;
2. duplicate the entire row without changing any protected field;
3. assign the duplicate `<adjudication_seed_id>-02`, then `-03`, and so on; and
4. code unique final adjudication IDs and the supported accused-driver unit on each instance.

The edited-workspace validator requires complete seed coverage, unique and well-formed instance
IDs, retention of every `-01` starter, exact protected lineage, unique populated final adjudication
IDs, and mutually exclusive primary/secondary inclusion flags. The exact starter audit is stricter:
it passes only before any final coding fields or row counts change.

`exclusion_qa_worklist.csv` freezes the 403 hash-selected checks across all 223 proposed-exclusion
strata. Only QA disposition, corrections, reviewer, status, and notes may change. A false exclusion
triggers a rule audit and complete queue regeneration; it must not become an undocumented one-row
override.

## Priority and timing context

Work is ordered by evidentiary risk: unresolved recalls, version/content attrition, parser-review
cases, primary candidates, secondary candidates, ambiguous scope, then proposed exclusions. The
priority is operational only and does not change the denominator or imply that an early row is more
severe.

Every primary candidate has a loaded Race/Sprint timing session and an accused-driver
classification: 260 of 260 for each control. Secondary qualifying-impeding cases intentionally lack
Race/Sprint timing joins at this stage because qualifying timing is outside the frozen FastF1
session population.

The seed records how the accused-driver suggestion was obtained:

| Basis | Starter rows | Primary candidates |
|---|---:|---:|
| Parsed decision heading | 1,653 | 259 |
| First explicit `Car N` reference in the official title | 75 | 1 |
| Unavailable | 223 | 0 |

The sole primary title fallback is the 2024 Abu Dhabi Car 81 collision decision. It now joins to the
official classification, but the number remains a machine suggestion pending source review.

Timing columns describe evidence availability, not fault or harm. In particular:

- `timing_incident_eligible_rows` supports incident chronology even when a lap is unsuitable for a
  pace model;
- `timing_pace_eligible_rows` uses the stricter processed, accurate, green-flag, non-pit,
  within-classification, tyre-context gate;
- `timing_beyond_classified_rows` preserves possible retirement or incident laps but excludes them
  from pace models; and
- accused-driver coverage fields refer only to the suggested driver and must be rechecked after a
  multi-driver split.

Three primary contexts carry known source limitations. The 2018 Bahrain session is missing one
within-classified-distance timing row, and the 2022 French session has 958 relative-only laps with
no trustworthy absolute timestamp; two French primary decisions inherit that session flag. No
primary candidate relies on the 2018 Monza raw-timing fallback. These flags require cautious
incident reconstruction, not exclusion or imputation by default.

## Human gate before analysis

The workspace is an auditable review instrument, not an analytical result. Modeling remains blocked
until every document has a reviewed disposition, every included adjudication has one effective
source version and one accused driver, every exclusion has a controlled reason, multi-car incident
relations and harm records are separately coded, and independent review has no unresolved item.
Only then can the project estimate sanction consistency, competitive harm, nationality effects, or
outcome sensitivity.
