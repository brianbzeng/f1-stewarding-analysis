# The Cost of Discretion - Report Blueprint

## Audience and decision

The primary audience is a mixed technical and oversight readership: a data leader, an investigator
or policy analyst, and a technically curious Formula 1 reader. The report must let each reader answer
three questions quickly:

1. What did the study observe?
2. How strong is the evidence?
3. What action or further review follows?

The report is not a catalog of controversial incidents. It is an audit of formally adjudicated
decisions, their consistency, their written conformance to applicable public guidance, and their
competitive consequences.

## Executive brief - two pages

### Page 1: decision summary

- one-sentence purpose and covered population;
- three to five findings, each containing magnitude, uncertainty, and scope;
- one lead visual chosen for decision relevance, not drama;
- overall conclusion using `consistent with`, `adjusted association`, or `review priority` language;
- three actions: FIA transparency/data action, analyst follow-up, and evidence limitation.

### Page 2: evidence strength

- study population and exclusions;
- referral-conditioned denominator warning;
- finding-by-finding evidence grade;
- exact versus bounded/modeled impact totals;
- model validation summary;
- top limitations and what would change the conclusion.

## Main report

### 1. Why discretion should be measurable

Explain why comparable treatment matters, why judgment is unavoidable, and why an anomaly is a
review signal rather than a declaration that a stewarding decision was wrong.

### 2. What entered the analysis

Use a population-flow visual:

`FIA documents -> document versions -> incidents -> accused-driver adjudications -> model-ready rows`

Report counts by year, session, incident family, outcome, document status, evidence completeness,
and exclusion reason. Show how recalled and corrected versions are retained but not double-counted.

### 3. How decision practice changed over time

Describe sanction rates and severity by rule era and incident family. Separate raw rates from
standardized or adjusted estimates. Identify structural breaks before fitting pooled models.

### 4. Comparable cases and potential inconsistency

Present calibrated expected outcomes, residuals, and matched case twins. Lead with model performance
and overlap; only then show review-priority cases. Every highlighted case links to official evidence
and lists the observable factors included and material factors unavailable.

### 5. Public-guideline conformance in 2025

Report mappable coverage first. Among confidently mapped decisions, distinguish exact baseline,
within range, explicit mitigation/aggravation, unexplained apparent departure, and unclear. Do not
apply 2025 public guidance retrospectively.

### 6. Nationality and panel associations

Show raw distributions as context but base headline conclusions on adjusted marginal effects and
intervals. Report accused and affected-driver roles separately. Include leave-one-driver,
leave-one-season, home-race, and British-Grand-Prix exclusions. Use `inconclusive` when power or
overlap is inadequate.

### 7. Who actually paid the competitive cost?

First report sanction burden by evidence tier:

- exact mechanical position, points, podium, and win changes;
- bounded in-race effects;
- validated modeled expected-points effects;
- non-estimable cases.

Never sum modeled and mechanical impacts without labeling the mixture.

Then report victim harm separately:

- immediate position and relative-time changes;
- confirmed damage, punctures, repair stops, and incident-caused retirements;
- bounded pit-lane and repair cost;
- validated persistent per-lap loss multiplied over exposed laps with uncertainty; and
- harmful, neutral, possibly beneficial, or beneficial incident-triggered pit responses.

The lead visual is a multi-column harm-sanction matrix, not a single fairness ranking. It shows
responsibility status, victim time/position/points/retirement evidence, nominal sanction, and realized
sanction position/points burden. Formal proportionality findings are limited to fault-established,
independently reviewed incidents. Racing incidents and shared-fault cases remain visible but are not
called under-penalized merely because their consequences were severe.

Explain that this is an external distributive-fairness question. A large competitive asymmetry may be
important to fans, teams, and policy discussion even when the stewards correctly applied a conduct-
based penalty framework that did not seek to compensate the affected driver.

### 8. Formal corrections and governance boundary cases

Describe corrected, reviewed, protested, or appealed outcomes without calling them a population
error rate. Treat Abu Dhabi 2021 as a governance case study outside the ordinary penalty model.

### 9. Conclusions and recommendations

Tie every conclusion to the claim ledger. Recommendations should target evidence publication,
decision-template consistency, versioned guidelines, and review prioritization—not replacement of
steward judgment by a model.

## Technical appendix

- protocol deviations and change log;
- source inventory, hashes, and rule-version logic;
- data dictionary and coding agreement;
- missingness and linkage diagnostics;
- model formulas, hyperparameters, and grouped validation;
- calibration, discrimination, residual, and overlap diagnostics;
- multiplicity and sensitivity analyses;
- impact formulas and point schedules;
- victim-harm evidence rules, clean-lap exclusions, forced-stop counterfactuals, and persistent-pace
  model diagnostics;
- nominal-versus-realized sanction-burden definitions and proportionality eligibility rules;
- reproducibility environment and commands;
- disclosure of AI-assisted initial coding and independent human review.

## Figure standards

- Titles state the analytical takeaway, not only the variables plotted.
- Subtitles state population, years, and adjustment status.
- Captions identify source, unit, uncertainty, exclusions, and evidence tier.
- Raw and adjusted charts are never visually conflated.
- Use direct labels and color-blind-safe palettes; do not encode nationality with flag colors.
- No chart reports more precision than the source supports.
- A reader can trace every highlighted value to a table, query, and official URL.

## Release checklist

- Every headline exists in `reports/claim_ledger.csv`.
- Every result includes population, denominator, magnitude, uncertainty, and limitation.
- All notebook outputs and report tables regenerate from a clean database build.
- Quality checks, tests, and notebook execution pass at the tagged commit.
- Independent review and unresolved-source status are current.
- No language exceeds the evidence grade.
- Executive and technical totals reconcile.
