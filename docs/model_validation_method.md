# Grouped Validation and Nationality Design Diagnostics

Status: outcome validation and nationality diagnostics executed on the disclosed model-reviewed
release.

The frozen specification is `config/outcome_model_spec.yml`. It defines the analytical unit,
release filter, event grouping, covariates, regularization, calibration outputs, overlap method,
simulation assumptions, and circularity safeguards outside the notebook.

## Outcome model

`validate_released_outcome_model` selects only `reporting_eligible=true` rows and accepts only
completed, disclosed review labels: `human_reviewed_final` or `model_reviewed_final`. It requires a
complete binary outcome and event ID for every released row.

Five-fold `GroupKFold` holds out whole events. Each prediction and its simple prevalence baseline
come only from the matching training fold. The same Grand Prix cannot appear in both train and test.
The model uses incident type, season, and multi-car status. Penalty amount, outcome family, decision
reason, fault language, and other post-decision fields are excluded.

The model-reviewed population contains 346 rows across 131 events:

| Measure | Result |
|---|---:|
| Observed sanction rate | 61.85% |
| Model Brier score | 0.23934 |
| Training-fold prevalence baseline | 0.23988 |
| Brier improvement | 0.00054 |
| ROC AUC | 0.55767 |
| Calibration intercept | 0.28634 |
| Calibration slope | 0.35551 |

The broad model barely improves on the baseline and ranks outcomes weakly. This does not prove that
stewarding is inconsistent. It means the three broad predictors omit too much case-specific context
to judge consistency or produce a defensible anomaly ranking. Leave-one-season-out results are
published with the final report as a sensitivity check.

## Nationality overlap

The released population contains 44 British and 302 other accused-driver cases. The overlap
diagnostic does not read the sanction outcome.

| Diagnostic | Result |
|---|---:|
| British exposure prevalence | 12.72% |
| Rows inside estimated common support | 97.69% |
| Overlap-weight effective N, British | 43.06 |
| Overlap-weight effective N, other | 212.60 |
| Maximum absolute SMD, unweighted | 0.521 |
| Maximum absolute SMD, overlap weighted | 0.039 |
| Extreme raw propensity rows requiring clipping | 4 |

Overlap weighting improves measured balance, but it cannot fix a small exposed group, unmeasured
case details, missing referrals, or incomplete panel-nationality evidence.

## Simulation-based power

The simulation fixes the observed exposure, covariates, and 131-event cluster structure. It tests
5, 10, 15, and 20 percentage-point differences from 50% and 70% baselines, with 500 repetitions per
scenario and a prespecified 80% power target.

| Baseline | Target difference | Detection power |
|---:|---:|---:|
| 50% | 5 points | 7.8% |
| 50% | 10 points | 17.4% |
| 50% | 15 points | 37.8% |
| 50% | 20 points | 69.8% |
| 70% | 5 points | 7.4% |
| 70% | 10 points | 25.4% |
| 70% | 15 points | 53.6% |
| 70% | 20 points | 80.0% |

Only the most favorable 20-point scenario reaches the target. The study is underpowered for subtle
nationality differences.

## Reporting consequence

The raw sanction rate is 56.8% for British accused drivers and 62.6% for other accused drivers, a
-5.8 percentage-point difference. It is not an adjusted or causal estimate. The final report labels
the nationality result inconclusive and does not interpret the gap as evidence of bias or no bias.
