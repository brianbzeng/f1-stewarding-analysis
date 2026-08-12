# Analysis Acceptance Criteria

Each analysis earns a claim level independently. The project does not treat model completion as
evidence that the model is reportable.

Frozen machine-readable thresholds are in `config/analysis_thresholds.yml`. Changes after outcome
modeling begins require a documented protocol deviation.

## Universal release gates

- Source lineage and final-version status are complete or explicitly unresolved.
- Independent review is complete for every headline input and case study.
- Missingness and exclusions are quantified by year, incident family, and outcome.
- Train/test grouping prevents the same event or incident from leaking across folds.
- Code, SQL checks, and notebooks run at the release commit.
- The claim ledger records population, estimand, method, sensitivity, grade, and limitation.

## RQ1 - consistency

### Supported for inference

- At least 10 outcome events per effective parameter after regularization, or simulation demonstrates
  acceptable calibration and interval behavior for the chosen model.
- Event-grouped cross-validation exceeds the intercept-only baseline on Brier score.
- Calibration intercept and slope are reported, with a reliability plot and uncertainty.
- The headline effect is stable in direction across leave-one-season-out analysis and is not driven
  exclusively by low-overlap rows.
- Review-priority thresholds are frozen before reading highlighted cases.

### Descriptive only

Use when outcome counts are sparse, calibration fails, or model performance does not exceed the
baseline. Report standardized rates and case strata without individual anomaly claims.

## RQ2 - 2025 guideline conformance

### Supported for document audit

- Applicable guideline version is verified.
- At least 80 percent of eligible decisions are confidently mappable.
- Independent agreement on clause and conformance is at least 90 percent or all disagreements are
  reconciled with reasons.
- Every apparent departure receives a targeted evidence review.

Otherwise report only clause coverage and examples.

## RQ3 - nationality and panel association

### Supported for adjusted association

- Exposure prevalence and outcome counts permit estimation without complete or quasi-separation.
- Positivity/overlap diagnostics show meaningful comparable support.
- Simulation-based power or expected interval width is acceptable for the minimum effect of interest
  defined before outcome modeling.
- Results include adjusted marginal effects and intervals, not odds ratios alone.
- The accused-role result survives leave-one-driver and leave-one-season checks in direction; the
  affected-driver result is analyzed separately.
- Multiplicity is controlled by a predefined primary contrast or false-discovery procedure.

If any core requirement fails, designation is `descriptive only` or `inconclusive`. No claim of bias
is permitted from this observational design.

## RQ4 - competitive impact

### Mechanical

- Penalty is explicitly added after racing.
- Official final classification, completed laps, penalty, and points schedule are verified.
- Same-lap arithmetic is reproduced in code and independently reviewed.

### Bounded

- Direct sanction cost is observable but an alternate race response is not fixed.
- Bounds arise from documented physical or classification constraints, not arbitrary percentages.

### Modeled

- Counterfactual model is validated out of sample for the target use and is calibrated for points or
  position, with uncertainty propagated.

Otherwise use `not_estimable`.

### Victim harm - observed

- Before/after positions or relative timing reproduce from the frozen timing extract.
- Damage, puncture, repair, or incident-caused retirement uses a direct official source or is labeled
  only as observed/alleged.
- A repair stop is causally linked to the incident rather than inferred from proximity alone.
- Observed change is not described as a no-incident counterfactual.

### Victim harm - bounded

- Pit transit, stationary repair, or another direct component is observed.
- The lower/upper bounds follow documented physical, timing, or strategy constraints.
- Planned-stop overlap and Safety Car/VSC state are explicit.

### Victim harm - modeled persistent loss

- At least the frozen minimum clean laps exist before and after the incident.
- Pit in/out, Safety Car/VSC, rain-transition, materially impeded, and other invalid comparison laps
  are excluded under a reproducible rule.
- Compound, tyre age, fuel-lap trend, track evolution, traffic, and teammate/field reference are
  controlled or the omission is justified.
- Grouped out-of-sample validation supports the target use and uncertainty is propagated across the
  exposed laps.
- Alternate pre/post windows and reference choices do not reverse the substantive conclusion.

Otherwise use `insufficient_data` or `not_estimable`; one clean lap cannot establish no lasting
damage.

### Harm-sanction proportionality

- Responsibility is independently reviewed and coded `fault_established`.
- Victim harm and sanction burden each retain their own evidence tier.
- Nominal and realized sanction burdens are both shown.
- Seconds, positions, points, repair, and retirement are reported separately rather than converted
  into a composite score.
- Shared-fault, racing-incident, and no-fault findings are descriptive only unless the report is
  explicitly auditing the responsibility finding with independent evidence.
- The conclusion states that proportionality is an external fairness lens and may differ from FIA
  penalty policy or guideline conformance.

## RQ5 - formal correction

Supported as a descriptive count when all discovered versions have lineage status and the final
outcome is identified. It is never labeled a general error rate because teams challenge decisions
selectively.

## Evidence grades

| Grade | Meaning |
|---|---|
| A | deterministic official-source result with complete lineage and review |
| B | validated adjusted/document-audit result with material limitations |
| C | exploratory adjusted association with adequate diagnostics but high residual uncertainty |
| D | descriptive or case-study evidence only |
| U | unsupported for release |
