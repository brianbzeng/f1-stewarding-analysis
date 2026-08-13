# Study v2 Protocol

Status: frozen on 13 August 2026. This protocol extends the disclosed model-reviewed release; it
does not relabel model review as independent human review.

## Purpose

Study v2 asks four related but distinct questions:

1. **Conduct consistency:** were comparable driving acts handled similarly?
2. **Consequence burden:** what observable cost did the incident impose on each participant?
3. **Sanction burden:** what did the imposed sanction actually cost the accused driver?
4. **Distributive fairness:** where responsibility and harm are independently established, how did
   the sanction burden compare with the burden imposed on others?

The fourth question is an external fairness lens. It is not automatically an allegation that the
stewards misapplied FIA rules. FIA reporting from 2021 describes a long-standing incident-not-outcome
approach, while the public 2025 Penalty Guidelines include specific consequence distinctions. The
study therefore preserves the rule and guideline issue in force for each event and never applies a
later standard retrospectively.

The machine-readable design is `config/study_v2.yml`. Any change to an estimand, sample, matching
field, damage-evidence rule, or release gate requires a dated protocol amendment before the affected
results are inspected.

## Frozen population and parent lineage

- Seasons: 2018–2025.
- Parent model-review run: `model-review-3dacc1268f13`.
- Parent feature build: `features-57542b24ea9f`.
- Primary population: Race and Sprint decisions in the frozen driving-incident families.
- Model-reviewed labels remain disclosed as model reviewed until genuine independent human review
  is completed.

## Phase 1: risk-based independent human audit

Reviewer A receives every elevated-risk source, every included multi-party source, and a
deterministic sample of 150 otherwise clean exclusions. Reviewer B receives every high-risk
inclusion, a separate stratified sample of 100 exclusions, and every case intended for publication.
Packets hide model final fields and display source evidence before any proposed answer. Exact
agreement is retained; disagreements go to a separate reconciliation ledger.

A sample audit can validate error rates and individual records. It cannot upgrade the full corpus to
`human_reviewed_final`. Unreviewed rows remain model reviewed and are labeled that way in every
table and figure.

## Phase 2: Race Control referral funnel

Session-keyed official-feed Race Control messages are grouped into episodes while preserving all
named cars. The episode taxonomy is: noted, investigation, post-session investigation, no
investigation, no further action, and sanction announced. Episodes are linked to FIA documents using
event, session, car set, lap, location, time, and normalized wording. Link confidence and basis are
stored. Unmatched episodes and unmatched decisions remain visible.

This funnel measures observable public process states. It does not recover incidents that were never
mentioned in the public message feed and cannot estimate the universe of unnoticed conduct.

## Phase 3: incident context and close-case matching

Incident timing follows this priority: explicit FIA lap, explicit Race Control lap, FIA incident
clock mapped into a lap interval, then reviewed video. Every inferred lap stores its basis and error
bound. Multi-car collisions remain one incident with multiple driver roles and edge-specific fault.

Close-case matching is frozen before anomaly review. Incident family, session, and guideline regime
are exact-match fields. Reviewed pre-outcome context determines distance. Penalty, fault finding,
damage, retirement, finishing position, and any other post-incident outcome are forbidden inputs to
the primary conduct match. A separate sanction-calibration analysis may exact-match on reviewed fault
language after responsibility is established. A case needs at least five comparable neighbors for a
population-level anomaly flag.

## Phase 4: conduct, consequence, and sanction layers

Conduct models predict the sanction outcome from source-available, pre-outcome context only. Harm is
measured separately as observed position change, incident-responsive repair, retirement, or a
reviewed persistent pace change. Sanction burden remains separated into time, positions, grid
positions, and points. The study prohibits conversion of these units into one subjective fairness
score.

Formal proportionality comparison is restricted to fault-established incidents with reviewed harm
evidence. A large loss in a no-action racing incident can be reported descriptively but cannot by
itself prove an incorrect decision.

## Phase 5: damage and persistent pace

The source hierarchy and claim rules are frozen in `config/damage_evidence_sources.yml` and explained
in `docs/damage_evidence_source_method.md`. Timing anomalies screen records for research; they do not
prove damage. Confirmed damage requires an explicit high-grade source. A persistent pace estimate
requires five clean laps on each side in the primary specification, a teammate or field reference,
and controls for compound, tyre age, fuel-lap trend, track state, weather, and traffic. Three- and
eight-lap windows are sensitivity analyses.

Pit-in/out, Safety Car, VSC, weather transition, and materially impeded laps are excluded. A forced
stop is not automatically harmful: Safety Car timing, planned strategy windows, useful tyre offsets,
and undercuts are recorded. A beneficial counterfactual requires separate review and validation.

## Phase 6: nationality diagnostic

Nationality remains secondary and gated. The current British-accused cell is too small for modest
effects. Before fitting any Study v2 nationality effect, the design requires at least 90% common
support, a maximum weighted absolute standardized difference of 0.10, an exposed effective sample
size of at least 30, 98 British-accused cases, adequate simulated power, completed independent
review, event-grouped inference, and multiplicity control. These numerical overlap thresholds were
added on 13 August 2026 before any Study v2 nationality effect was fitted or released. Until every
gate passes, the report shows descriptive composition and power limits rather than a bias verdict.

## Release contract

Every published claim receives a status: supported for inference, descriptive only, case study only,
or dropped. The final notebook must reproduce the population funnel, audit coverage, referral-link
coverage, timing eligibility, match support, harm evidence grades, model validation, and unresolved
queues. Unknowns remain explicit. The executable report may be updated as phases complete, but no
human-review gate passes until the independent ledgers are actually completed.

`python scripts/audit_study_v2_completion.py` verifies the frozen content-addressed artifacts,
release gates, executed notebooks, integrated HTML, and Study v2 claim-ledger entries. A passing
completion audit establishes implementation and reproducibility coverage only; it cannot satisfy an
independent-human-review gate.
