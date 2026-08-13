# Gated Analysis Feature Release

Status: provisional design diagnostics materialized; inferential release blocked by human review.

The feature layer converts the protected full-corpus coding workspace into explicit analytical
grains without treating machine suggestions as findings. It is built with:

```powershell
f1stewards build-analysis-features `
  data/manual/full_corpus_review_rounds/lineage_rebuild/recalled_versions/full-coding-e0192ecbd9e4
```

The current content-addressed build is `features-8f436aaa3796`. It uses machine-assisted first pass
`first-pass-5aa88d7f05b2`, the 17-case
[parser-format source review](parser_format_source_review.md), and the 18-case
[analytical-scope conflict review](analytical_scope_conflict_review.md) over workspace
`full-coding-e0192ecbd9e4`, plus the 61-case manual-scope source ledger and four unavailable
recalled-version dispositions. The four-step review chain ends at workspace SHA-256
`e1d4c4a969aee29b3db2a4f65e253e444c2e0c7d735cc3ec5451e3ec7b883f8f`. It also uses the sourced 43-driver
nationality registry, the controlled 28-label
event-country crosswalk, all 3,938 Race/Sprint classifications, and the complete decision-document
panel assignment register. The panel register contributes its own SHA-256 lineage field to the
feature-build identity.

## Two analytical grains

`analysis.adjudication_features` has one row per candidate accused-driver adjudication. It stores
the proposed or reviewed session, incident family, outcome, sanction amounts, accused-driver
identity, nationality, home-race exposure, affected-role summary, timing availability, and the
provenance of each field. `panel_id` is an adjustment key; `panel_assignment_basis`,
`panel_signature_parse_status`, `panel_size`, and `panel_data_status` distinguish source-observed
signatures from the tightly constrained event-consensus fallback.

`analysis.adjudication_driver_roles` has one row per accused or affected driver within that
adjudication. This bridge prevents a four-car incident from being reduced to a false two-driver
record. `role_sequence` preserves multiple affected drivers, while `role_number_basis` states
whether the number was machine-extracted or human-reviewed.

The current gated build contains:

| Diagnostic | Count |
|---|---:|
| Primary-candidate adjudication rows | 348 |
| Accused-driver role rows | 348 |
| Affected-driver role rows | 344 |
| Total driver-role rows | 692 |
| Rows with more than one affected driver | 25 |
| Missing accused or affected identity joins | 0 |
| Suggestions or source codes mapped to a binary sanction outcome | 338 |
| `other` outcome suggestions withheld from binary mapping | 10 |
| British accused-driver exposures | 44 |
| Accused-driver home-race exposures | 14 |
| Reporting-eligible rows | 0 |
| Rows with complete document-panel context | 348 |
| Distinct panels represented | 131 |
| Exact document-signature panel assignments | 348 |
| Four-member / five-member panel rows | 337 / 11 |

These are workload and design-coverage counts. They are not sanction rates, nationality effects,
or evidence of bias.

All 348 provisional primary candidates are labeled `incomplete_human_coding`: 174 use a completed
source-coding pass and 174 retain disclosed machine assistance. Every source code remains
`single_coded_pending_human`; no row is relabeled `human_reviewed_final` or allowed into reporting.

## Label separation

Every row carries both `feature_label_status` and `population_status`:

- `provisional_machine_suggestion` permits schema, join, missingness, and overlap diagnostics only;
- `incomplete_human_coding` identifies a started but unreleasable row;
- `human_reviewed_excluded` preserves attrition without entering a model; and
- `human_reviewed_final` can become model-eligible only when the entire release gate passes.

The builder never fills final penalty amounts from protected machine suggestions. A reviewed row
uses only `penalty_seconds_final`, `penalty_points_final`, and `grid_places_final`; a blank final
value remains blank. This prevents an outcome correction from silently carrying forward a wrong
parsed punishment.

## Release controls

`analysis.feature_release_controls` records nine fail-fast checks. The current workspace passes
all 19 lineage and editing controls, but correctly fails these substantive gates:

- 0 of 2,003 document dispositions independently reviewed, despite completed source work on the
  targeted parser, scope, manual-scope, and recalled-version investigations;
- 0 of 1,952 adjudication seeds independently reviewed, despite the same source-coding chain;
- 0 of 486 frozen exclusion-QA rows independently reviewed; and
- no final reviewed primary population yet exists.

Accordingly, `metadata.analysis_feature_builds.release_status` is
`blocked_pending_human_review`, every `reporting_eligible` value is false, and the latest views
cannot be mistaken for report results. Once the complete workspace is reviewed, the same command
rebuilds the features from final fields and changes the release status only if every prerequisite
control passes.

## Why this matters for the report

The structure supports the planned adjusted analyses while preserving the study's limits:

- accused and affected nationality are separate role exposures;
- home-race exposure uses a published code crosswalk rather than names;
- multi-car incidents retain every affected role;
- unmapped outcomes remain null rather than being guessed into sanction/no-sanction; and
- exact panel identity is available as a non-nationality adjustment dimension for every candidate;
  panel-country exposure remains withheld until all 83 steward identities have source-backed,
  temporally coherent country evidence.

Grouped validation, overlap diagnostics, and outcome-free simulation power are implemented in
[`model_validation_method.md`](model_validation_method.md). Substantive estimates stay suppressed
until the release gate becomes reportable.
