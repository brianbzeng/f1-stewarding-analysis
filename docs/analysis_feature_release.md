# Gated Analysis Feature Release

Status: disclosed model-reviewed release materialized; independent human review remains separate.

The feature layer converts the protected full-corpus coding workspace into explicit analytical
grains without presenting machine suggestions as human-reviewed facts. The current release is built
from the GPT-5.6 Sol workspace:

```powershell
f1stewards build-analysis-features `
  data/manual/full_corpus_model_review/model-review-3dacc1268f13/full-coding-e0192ecbd9e4 `
  --strict-release
```

The content-addressed build is `features-57542b24ea9f`. Its release status is
`reportable_model_reviewed`. The protocol, correction audit, source hashes, and assurance boundary
are documented in [`model_review_protocol.md`](model_review_protocol.md).

## Two analytical grains

`analysis.adjudication_features` has one row per candidate accused-driver adjudication. It stores
the reviewed session, incident family, outcome, sanction amounts, accused-driver identity,
nationality, home-race exposure, affected-role summary, timing availability, panel context, and
field provenance.

`analysis.adjudication_driver_roles` has one row per accused or affected driver within an
adjudication. This prevents a multi-car incident from being reduced to a false two-driver record.

The current build contains:

| Measure | Count |
|---|---:|
| Feature rows retained for lineage | 348 |
| Model-reviewed reporting-eligible primary rows | 346 |
| Events represented | 131 |
| Total driver-role rows | 692 |
| Released multi-car primary cases | 24 |
| British accused-driver exposures | 44 |
| Other accused-driver exposures | 302 |
| Accused-driver home-race exposures | 14 |
| Missing released accused identity joins | 0 |
| Missing released binary outcomes | 0 |
| Released rows with source-observed panel context | 346 |

Two source rows that were previously counted as primary candidates remain in the feature table for
lineage but are not reporting eligible because the model review identified them as superseded
predecessor decisions. This is why the table has 348 rows while the released primary population has
346.

## Label separation

Every feature row carries `feature_label_status`, `population_status`, and `reporting_eligible`.
Model-reviewed analytical rows use `model_reviewed_final`; genuine independent human work remains
reserved for `human_reviewed_final`. The corresponding build statuses are
`reportable_model_reviewed` and `reportable_human_reviewed`.

The builder never fills final penalty amounts from unreviewed suggestions. Blank final values stay
blank. This prevents a corrected outcome from silently carrying forward a wrong parsed sanction.

## Release controls

`analysis.feature_release_controls` records nine fail-fast checks. The current build passes:

- all 19 protected workspace and lineage controls;
- 2,003 of 2,003 document dispositions reviewed;
- 1,952 of 1,952 adjudication codings reviewed;
- 486 of 486 frozen exclusion checks reviewed;
- 346 final primary cases present;
- zero missing accused identities; and
- zero missing or unmapped released outcomes.

The four recalled records without source binaries are metadata-only exclusions. They cannot enter
the analytical population. Panel-country exposure remains separately withheld until all steward
country evidence is temporally and source coherent.

## Interpretation boundary

The release supports descriptive full-corpus rates and grouped model validation. It does not turn a
model-led second pass into independent human assurance, make missing referrals observable, or make
descriptive nationality differences causal. The report names GPT-5.6 Sol, the run ID, corrections,
unavailable sources, and the lack of independent human review.
