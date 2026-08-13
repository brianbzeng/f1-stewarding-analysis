# Grouped Validation and Nationality Design Diagnostics

Status: methods implemented and tested; outcome validation remains blocked; outcome-free design
diagnostics executed.

The frozen specification is `config/outcome_model_spec.yml`. It defines the analytical unit,
release filter, event grouping, covariates, regularization, calibration outputs, overlap method,
simulation assumptions, and circularity safeguards outside the notebook.

## Outcome-model release boundary

`validate_released_outcome_model` selects only rows where `reporting_eligible=true`. It then checks
that every selected row is `human_reviewed_final`, the sanction outcome is complete and binary,
both outcome classes exist, and event IDs are present. With the current feature release it raises a
controlled error rather than accepting provisional suggestions.

When final labels exist, validation will use five-fold `GroupKFold` by `event_id`. The same event can
never occur in train and test within a fold. Each test-row prediction uses only its training fold;
the prevalence baseline is also estimated from that fold. The method returns:

- model and prevalence-baseline Brier scores;
- Brier improvement, log loss, and ROC AUC;
- calibration intercept and slope from out-of-fold probabilities;
- a reliability table;
- a fold-level event-overlap audit; and
- leave-one-season-out sensitivity results.

Penalty amount, outcome family, decision reason, fault language, and other post-decision fields are
not predictors. Tests use synthetic human-reviewed labels to exercise all statistical code without
bypassing the real release gate.

## Outcome-free nationality overlap

`nationality_overlap_diagnostics` does not require or read `sanction_outcome`. Its current input is
the 295 provisional primary candidates solely to evaluate whether British and other accused-driver
exposures occupy comparable parts of the frozen covariate space.

| Diagnostic | Current value |
|---|---:|
| Events | 124 |
| British accused-driver rows | 40 |
| Other accused-driver rows | 255 |
| British exposure prevalence | 13.6% |
| Rows inside estimated common support | 78.3% |
| Overlap-weight effective N, British | 39.0 |
| Overlap-weight effective N, other | 172.2 |
| Maximum absolute SMD, unweighted | 0.655 |
| Maximum absolute SMD, overlap weighted | 0.185 |
| Rows at the 0.01 raw-propensity clipping boundary | 40 |

One one-dimensional support cell contains only one exposure group: 2018 has no British
accused-driver candidate. Overlap weighting substantially improves measured balance, but the
remaining maximum standardized difference of 0.185 is a warning, not evidence
that nationality affected an outcome. Final coding can change these counts; all diagnostics must be
rerun on the released population.

## Simulation-based power

The simulation fixes the observed exposure, covariate, and 124-event cluster structure but excludes
the observed sanction label. For each scenario it:

1. assumes a 50% or 70% unexposed baseline sanction probability;
2. imposes a 5, 10, 15, or 20 percentage-point British-exposure difference;
3. adds a normally distributed event random intercept with SD 0.35;
4. generates a binary outcome; and
5. fits the prespecified logistic adjustment with event-cluster-robust uncertainty.

Each of the eight scenarios uses 500 repetitions. The frozen acceptance targets are at least 90%
successful fits and 80% detection power at two-sided alpha 0.05. Fit stability is 97.4%–100%, so
the power results are usable as design diagnostics.

| Baseline | Target difference | Detection power |
|---:|---:|---:|
| 50% | 5 points | 8.4% |
| 50% | 10 points | 20.6% |
| 50% | 15 points | 33.8% |
| 50% | 20 points | 58.2% |
| 70% | 5 points | 8.4% |
| 70% | 10 points | 20.8% |
| 70% | 15 points | 49.4% |
| 70% | 20 points | 72.0% |

No scenario reaches the 80% target. Under the current provisional exposure structure, the study is
not capable of reliably detecting subtle nationality associations and does not even attain target
power for an assumed 20-point difference. This is a design limitation, not a null result: no
observed nationality effect has been estimated.

## Reporting consequence

The executed
[`05_nationality_design_diagnostics.ipynb`](../notebooks/05_nationality_design_diagnostics.ipynb)
shows the exposure distribution, propensity support, standardized balance, simulation power, and
blocked release controls. Unless the final reviewed population materially improves exposure and
common support, the nationality section should be descriptive or explicitly inconclusive. A bias
claim is not permitted from this design.
