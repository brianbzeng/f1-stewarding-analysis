# Full-Corpus Machine-Assisted First Pass

Status: deterministic first pass generated and validated; independent review has not begun.

## Release identity

The current release is `first-pass-5aa88d7f05b2`, schema
`full-corpus-machine-assisted-first-pass-v3`. It is derived from source workspace
`full-coding-e0192ecbd9e4` without changing the protected starter or seed bundle.

| Lineage item | SHA-256 |
|---|---|
| Source workspace | `87f173da216f8c7f3b170322817425d1d79d5638b28104d9b4a403608634566c` |
| First-pass workspace | `de816c98622f6b429529041ad616fe706cbfdf17e82d169d598aff45b6e7bca9` |
| Document worklist | `3d0a2337412cc58a141fbac7424135eea21cefda91764c75b79afe2513de2ee0` |
| Adjudication worklist | `a76e35359f06a30b4e9c557610b24d096d982efd512ac95d91c2fc77a65497c0` |
| Unchanged exclusion-QA worklist | `9daf37d57f558eab0b91001f94921f0f3849288a2f88d1cde17a613fec411987` |
| Row-level audit | `cad8f9fa39c5ad209539725bb72cf6c652124545a78aa4e7e66304375c5d427b` |

Generate or byte-verify the release with:

```powershell
f1stewards build-full-corpus-first-pass `
  data/manual/full_corpus_workspaces/full-coding-e0192ecbd9e4
```

The output is local working state under
`data/manual/full_corpus_first_pass/full-coding-e0192ecbd9e4`. The committed generator, tests,
release record, and [portable first-pass console](../explorer/full_corpus_first_pass_review.html)
make the transformation reproducible without presenting the edited CSVs as reviewed data.

Build the de-duplicated investigation handoff after verifying this release:

```powershell
f1stewards build-full-corpus-exception-packet `
  data/manual/full_corpus_first_pass/full-coding-e0192ecbd9e4
```

The resulting [exception packet](full_corpus_exception_packet.md) converts 682 unstarted queue rows
into 582 unique source-document investigations.

## Scope and exceptions

| Queue | Total | First-pass prefilled | Deliberately unresolved |
|---|---:|---:|---:|
| Document dispositions | 2,003 | 1,903 | 100 |
| Adjudication coding | 1,952 | 1,856 | 96 |
| Exclusion QA | 486 | 0 | 486 |
| **Total** | **4,441** | **3,759** | **682** |

The document exceptions comprise 59 manual-offence rows, 18 manual-session rows, 18 conflict rows,
four unresolved recalled versions, and one parser-warning primary candidate. The adjudication
exceptions comprise 17 parser/multi-decision rows, 61 manual-scope rows, and 18 family-conflict
rows.

All 486 exclusion-QA rows remain blank because copying a proposed exclusion into its own audit would
not constitute evidence review. No cross-family conflict or parser-warning inclusion is prefilled.
The v3 release does prefill 207 parser-warning document exclusions and their 207 adjudication
exclusions because the protected deterministic classification already places them outside the
frozen study population. They remain `single_coded_pending_human`, and sampled rows retain their
independent QA obligation.

## Field rules

Document prefill maps only structurally resolved version, session, family, and eligibility
suggestions. Exclusions receive controlled reasons such as `out_of_scope_session`,
`outside_secondary_offence_scope`, or `excluded_offence_family:<family>`.

Parser warnings are therefore routed by analytical risk rather than treated as one undifferentiated
format failure. A warning blocks every proposed inclusion and every ambiguous/manual path. It may
pass only when `eligibility_suggestion=out_of_scope_suggestion`, where the prefill records an
exclusion pending official-source review. The manifest proves the boundary with zero
`parser_warning_inclusion_rows_prefilled` and separate document/adjudication counts for warning-bearing
exclusions.

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

The immediate first-pass feature build was `features-9c870436c35e`, with 295 rows labeled
`incomplete_human_coding` and one untouched parser case. The subsequent versioned
[parser-format source review](parser_format_source_review.md) resolves that operational exception
as a pending-human Hungarian no-action inclusion and produces `features-8f34710dfddc`, with all 296
rows labeled `incomplete_human_coding`. All document, adjudication, exclusion-QA, population, and
analytical-release gates remain failed as intended. There are zero `human_reviewed_final` and zero
reporting-eligible rows.

Every prefilled row is disclosed as coder `codex_assisted_prefill_v1` with review status
`single_coded_pending_human`. This release is a throughput aid, not independent review, an effect
estimate, or authorization to write substantive consistency, nationality, impact, or fairness
conclusions.
