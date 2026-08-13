# Full-Corpus Machine-Assisted First Pass

Status: deterministic first pass generated and validated; independent review has not begun.

## Release identity

The current release is `first-pass-29113bebd312`, schema
`full-corpus-machine-assisted-first-pass-v2`. It is derived from source workspace
`full-coding-e0192ecbd9e4` without changing the protected starter or seed bundle.

| Lineage item | SHA-256 |
|---|---|
| Source workspace | `87f173da216f8c7f3b170322817425d1d79d5638b28104d9b4a403608634566c` |
| First-pass workspace | `17188e95a22bdfcad8c4dac9985cbe4c3babc494734e2348811748a1e7ab9b09` |
| Document worklist | `4da1d40cf56345b45ee11533b5e47b23f7db1f91a50adfab73039b0bdc962af4` |
| Adjudication worklist | `560c1cc08249a0d9a0de6b208285dfc8070e19060dfe9257a0010b1488dcb4e8` |
| Unchanged exclusion-QA worklist | `9daf37d57f558eab0b91001f94921f0f3849288a2f88d1cde17a613fec411987` |
| Row-level audit | `e7d9f7e6168520ced3b4424201d6a19bdace9845d74cc4b2f99a1e3745b7b7eb` |

Generate or byte-verify the release with:

```powershell
f1stewards build-full-corpus-first-pass `
  data/manual/full_corpus_workspaces/full-coding-e0192ecbd9e4
```

The output is local working state under
`data/manual/full_corpus_first_pass/full-coding-e0192ecbd9e4`. The committed generator, tests,
release record, and [portable first-pass console](../explorer/full_corpus_first_pass_review.html)
make the transformation reproducible without presenting the edited CSVs as reviewed data.

## Scope and exceptions

| Queue | Total | First-pass prefilled | Deliberately unresolved |
|---|---:|---:|---:|
| Document dispositions | 2,003 | 1,696 | 307 |
| Adjudication coding | 1,952 | 1,649 | 303 |
| Exclusion QA | 486 | 0 | 486 |
| **Total** | **4,441** | **3,345** | **1,096** |

The document exceptions comprise 208 parser-review rows, 18 conflict rows, 59 manual-offence rows,
18 manual-session rows, and four unresolved recalled versions. The adjudication exceptions comprise
224 parser/multi-decision rows, 61 manual-scope rows, and 18 family-conflict rows.

All 486 exclusion-QA rows remain blank because copying a proposed exclusion into its own audit would
not constitute evidence review. No row with `parser_review_required=true` or a cross-family conflict
is prefilled.

## Field rules

Document prefill maps only structurally resolved version, session, family, and eligibility
suggestions. Exclusions receive controlled reasons such as `out_of_scope_session`,
`outside_secondary_offence_scope`, or `excluded_offence_family:<family>`.

Adjudication prefill copies the source-parsed accused and affected numbers, session, single lap,
turn location, incident family, formal outcome, and stated sanction fields. Included rows receive
stable adjudication IDs and source-unique provisional incident IDs. The source-unique strategy
deliberately over-separates mirrored decisions until a reviewer can support cross-document incident
grouping; it never guesses that two documents describe the same event.

Written responsibility is populated only when the Reason text explicitly states one of the frozen
categories. The v2 extractor handles racing incidents, shared contribution, no-driver/neither-driver
findings, wholly/fully/solely responsible language, predominant responsibility, and mainly-at-fault
language. It leaves 172 of 295 prefilled primary rows blank rather than infer fault. The observed
first-pass primary labels are:

| Fault language | Rows |
|---|---:|
| `wholly_to_blame` | 38 |
| `predominantly_to_blame` | 29 |
| `no_conclusion` | 34 |
| `racing_incident` | 14 |
| `shared_fault` | 8 |
| blank pending source review | 172 |

## Validation and analytical boundary

All 19 edited-workspace controls pass: exact schemas, complete protected row identity, zero protected
lineage mismatches, complete seed coverage, unique instance and populated final IDs, mutually
exclusive inclusion flags, and valid corrected sanction/fault/status fields.

The derived feature build is `features-0dda4b045f28`, with 295 rows labeled
`incomplete_human_coding` and one untouched parser case labeled
`provisional_machine_suggestion`. All document, adjudication, exclusion-QA, population, and
analytical-release gates remain failed as intended. There are zero `human_reviewed_final` and zero
reporting-eligible rows.

Every prefilled row is disclosed as coder `codex_assisted_prefill_v1` with review status
`single_coded_pending_human`. This release is a throughput aid, not independent review, an effect
estimate, or authorization to write substantive consistency, nationality, impact, or fairness
conclusions.
