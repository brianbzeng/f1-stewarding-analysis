# Gated Analysis Feature Release

Status: provisional design diagnostics materialized; inferential release blocked by human review.

The feature layer converts the protected full-corpus coding workspace into explicit analytical
grains without treating machine suggestions as findings. It is built with:

```powershell
f1stewards build-analysis-features `
  data/manual/full_corpus_workspaces/full-coding-4b0c0d5ddd72
```

The current content-addressed build is `features-416a202a8006`. It uses workspace
`full-coding-4b0c0d5ddd72`, the sourced 43-driver nationality registry, the controlled 28-label
event-country crosswalk, and all 3,938 Race/Sprint classifications.

## Two analytical grains

`analysis.adjudication_features` has one row per candidate accused-driver adjudication. It stores
the proposed or reviewed session, incident family, outcome, sanction amounts, accused-driver
identity, nationality, home-race exposure, affected-role summary, timing availability, and the
provenance of each field.

`analysis.adjudication_driver_roles` has one row per accused or affected driver within that
adjudication. This bridge prevents a four-car incident from being reduced to a false two-driver
record. `role_sequence` preserves multiple affected drivers, while `role_number_basis` states
whether the number was machine-extracted or human-reviewed.

The current provisional build contains:

| Diagnostic | Count |
|---|---:|
| Primary-candidate adjudication rows | 260 |
| Accused-driver role rows | 260 |
| Affected-driver role rows | 243 |
| Total driver-role rows | 503 |
| Rows with more than one affected driver | 13 |
| Missing accused or affected identity joins | 0 |
| Suggestions mapped to a binary sanction outcome | 252 |
| `other` outcome suggestions withheld from binary mapping | 8 |
| Suggested British accused-driver exposures | 34 |
| Suggested accused-driver home-race exposures | 12 |
| Reporting-eligible rows | 0 |

These are workload and design-coverage counts. They are not sanction rates, nationality effects,
or evidence of bias.

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

`analysis.feature_release_controls` records eight fail-fast checks. The current workspace passes
all 19 lineage and editing controls, but correctly fails these substantive gates:

- 0 of 2,002 document dispositions independently reviewed;
- 0 of 1,951 adjudication seeds independently reviewed;
- 0 of 403 frozen exclusion-QA rows independently reviewed; and
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
- panel exposure is explicitly `not_collected` until steward signatures and nationalities have
  source-backed coverage.

Grouped validation, overlap diagnostics, and outcome-free simulation power are implemented in
[`model_validation_method.md`](model_validation_method.md). Substantive estimates stay suppressed
until the release gate becomes reportable.
