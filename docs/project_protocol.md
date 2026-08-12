# Research Protocol

Version: 0.1

Status: drafted before full data collection
Coverage: completed FIA Formula One World Championship seasons 2018-2025

## Purpose

This study evaluates the consistency and competitive consequences of formally adjudicated Formula One driving incidents. It also tests whether decision outcomes are associated with nationality or steward-panel composition after accounting for observable incident context.

The study is designed as an oversight analysis. Its models prioritize cases for review and quantify associations; they do not determine fault, intent, corruption, or the correctness of evidence that is unavailable to the public.

## Primary unit of analysis

The primary unit is an **accused-driver adjudication**. An underlying incident may produce multiple rows when more than one driver is formally adjudicated. Documents are not observations: a summons, initial decision, corrected decision, and Right of Review may all describe the same adjudication.

Each adjudication belongs to one `incident_id` and one final `decision_id`. Superseded documents remain in the provenance table.

## Study population

### Include

- Formula One Race and Sprint sessions from 2018-2025.
- Formal steward documents concerning subjective on-track driving conduct.
- Penalties, reprimands, warnings, and no-further-action decisions.
- Recalled, corrected, reviewed, and appealed decisions when their lineage is recoverable.
- The following primary allegation families:
  - causing a collision;
  - forcing another driver off track;
  - leaving the track and gaining a lasting advantage;
  - unsafe rejoining;
  - moving under braking;
  - more than one change of direction while defending.

### Exclude from primary models

- Technical nonconformity and disqualification.
- Power-unit, gearbox, and parc ferme allocation penalties.
- Pit-lane speeding and other mechanically prescribed sanctions.
- Equipment, curfew, procedural, financial, and personnel offences.
- Routine track-limit strike accumulation.
- Race Control operational decisions, safety-car deployment, and red-flag procedure.

Qualifying impeding is a planned secondary population with a separate outcome model because grid penalties are not comparable to race time penalties.

## Research questions and estimands

### RQ1: comparable-case consistency

Among formally adjudicated driving incidents, estimate the probability of a sanction and the distribution of sanction severity conditional on observable incident characteristics.

Primary outputs:

- out-of-sample Brier score and calibration;
- adjusted sanction probability;
- expected severity range;
- comparable-case residual;
- matched case twins with sufficient overlap.

Model disagreement is not itself proof of inconsistency. Unpublished video, telemetry, radio, testimony, and steward judgment are plausible unobserved causes.

### RQ2: 2025 public-guideline conformance

For 2025 adjudications that map confidently to the public guidelines, classify the observed sanction as:

1. exact baseline;
2. within the recommended range;
3. different from baseline with explicit mitigation/aggravation;
4. outside the apparent range without a clear written explanation;
5. not confidently mappable;
6. guideline not applicable.

This is a document-conformance audit, not a legal determination. The FIA states that the guidelines have no regulatory value.

### RQ3: nationality and panel association

Estimate adjusted differences in sanction probability and severity associated with:

- British accused driver;
- British affected driver/counterparty;
- same-nationality steward exposure;
- home-race status;
- panel composition;
- championship-contender status.

Nationality fields must be defined before outcome analysis. Driver nationality means the nationality represented in FIA/F1 records for that season. Team nationality is excluded from the primary nationality test because entrant nationality, ownership, and operational base are different constructs.

### RQ4: competitive impact

Measure separately:

- exact mechanical classification changes for time added after the session;
- bounded estimates for penalties served during the session;
- modeled expected-points changes if validation supports them;
- non-estimable counterfactuals such as grid penalties and governance decisions.

### RQ5: formal correction

Describe decisions amended or removed through corrections, Rights of Review, protests, or appeals. This is not an overall error rate because challenges are selective and strategic.

## Predefined covariates

The initial context set is:

- season and rule regime;
- session type;
- incident family;
- lap and proportion of session complete;
- first-lap indicator;
- multi-car indicator;
- wet/dry track state;
- Safety Car or VSC state;
- accused driver role (attacking/defending/other);
- inside/outside attempt;
- contact;
- damage;
- immediate position loss;
- retirement;
- lasting advantage retained or returned;
- written mitigation;
- written aggravation;
- driver, team, event, and panel identifiers.

Variables derived only from a steward's conclusion must be marked to prevent circular models. For example, `predominantly_to_blame` cannot be used to independently predict whether the stewards found the driver at fault unless the analysis explicitly studies sanction choice after fault was established.

## Modeling sequence

1. Descriptive baseline by incident family and rule regime.
2. Penalized logistic regression for sanction versus no action.
3. Ordinal or multinomial model for sanction severity within comparable sessions.
4. Hierarchical model with partial pooling for driver, event/panel, and season effects.
5. Tree-based predictive benchmark only if sample size, class balance, and grouped validation support it.
6. Nearest-neighbor or propensity-distance case matching within incident family and rule regime.

Cross-validation groups must prevent documents or adjudications from the same event leaking across train and test folds. Leave-one-season-out sensitivity is required for headline models.

## Nationality safeguards

- Report accused and affected-driver effects separately.
- Evaluate all nationalities descriptively before highlighting Britain.
- Present adjusted marginal effects and interval estimates, not raw counts alone.
- Repeat models without the British Grand Prix, each British driver, and each season.
- Use permutation tests within incident family and era when feasible.
- Report inadequate power as inconclusive.
- Do not generalize beyond formally adjudicated incidents.

## Competitive-impact evidence levels

- **A — exact mechanical:** official elapsed time can be recalculated without an added post-session penalty.
- **B — bounded:** direct time cost is observable, but race strategy and position response are not fixed.
- **C — modeled:** expected-points counterfactual from a validated simulation or predictive model.
- **D — qualitative only:** no defensible numerical counterfactual.

Every reported impact must include its evidence level.

## Case-study selection

Abu Dhabi 2021 is selected a priori as a governance boundary case and is not part of the standard penalty model.

All other detailed case studies will be selected after model freeze using a published score combining:

- absolute consistency residual;
- comparable-case support;
- data completeness;
- competitive impact;
- robustness across model specifications.

Famous incidents receive no automatic preference.

## Reporting commitments

Each headline conclusion will state:

1. claim;
2. magnitude;
3. uncertainty;
4. applicable population;
5. primary limitation.

The final report will use `review priority`, `adjusted association`, and `potential inconsistency`, not `wrong`, `corrupt`, or `proven bias` unless an authoritative decision explicitly supports that wording.

## Feasibility gates

The full collector will not begin until the pilot verifies:

- event-page document discovery;
- PDF retrieval and hashing;
- extraction of Fact, Infringement, Decision, and Reason;
- identification of penalties and no-action decisions;
- corrected/recalled decision lineage;
- final classification discovery;
- rule-version mapping;
- FastF1 event/session linkage;
- an estimate of manual-review burden.

After full EDA, each inferential question receives a supported, descriptive-only, or dropped designation based on sample size, overlap, missingness, and power.
