# Damage Evidence Source Method

Status: source landscape reviewed and evidence rules frozen on 13 August 2026.

## What the web review found

No single public source can answer every damage question. The reliable design is a joined evidence
chain:

1. FIA event pages establish the official classification, lap chart, lap analysis, pit-stop summary,
   Race Control messages, and steward documents. A typical event page exposes all of those products
   separately, so a repair stop and a retirement can be checked without treating a news story as the
   official result: [FIA 2025 Bahrain timing page](https://www.fia.com/events/fia-formula-one-world-championship/season-2025/bahrain-grand-prix/eventtiming-information).
2. Official team reports and attributed driver or engineer debriefs are the strongest public sources
   for the damaged component and the team's causal account. They are first-party evidence, not
   neutral adjudications.
3. Formula1.com official reporting is useful when it preserves a named team/driver attribution or
   explicitly connects contact, damage, repair, and observed result. It remains secondary to the FIA
   finding on responsibility.
4. Pirelli material is useful for tyre-failure mechanisms and compound context. It is not a general
   source for vehicle damage or fault.
5. Accredited media, broadcast video, photographs, social media, and timing anomalies are discovery
   tools unless the protocol's source and review requirements are satisfied.

The machine-readable register is `config/damage_evidence_sources.yml`. It records source grade,
permitted claims, retrieval route, and limitations. The register is deliberately domain-based; every
case-level record must still preserve its exact URL, publication date, retrieval date, author or
speaker, evidence span, and archive status.

## Evidence grades

| Grade | Source | What it can establish |
|---|---|---|
| A1 | FIA regulation, decision, classification, timing or Race Control | official finding and observed race record |
| A2 | team report or named team/driver debrief | component, repair, retirement mechanism, attributed pace estimate |
| A3 | official Formula 1 editorial/interview | attributed or explicitly reported damage narrative |
| B1 | official tyre supplier | tyre mechanism, compound and strategy context |
| C | accredited secondary reporting | discovery or attributed quote when the primary is unavailable |
| D | visual, social, broadcast or timing pattern | review lead only |

An A2 source may be more informative about a floor or diffuser than an FIA decision, but it is still
an interested-party statement. Where it makes a numerical or race-order claim, the analysis checks
that claim against A1 timing and classification data.

## Examples that define the coding boundary

- Formula 1 reported Mercedes engineer Andrew Shovlin's estimate that Hamilton initially lost about
  six-tenths per lap from Imola front-wing damage and later two-to-three tenths after part detached.
  This is an A3 article carrying an A2 attribution, so the estimate is stored as attributed and is
  tested against the lap model rather than treated as ground truth:
  [Formula 1, 22 April 2021](https://www.formula1.com/en/latest/article/front-wing-damage-cost-hamilton-0-6s-per-lap-until-imola-red-flag-mercedes.4YdB5ZdPJaoMCfjnx5Nk3u).
- Formula 1's 2024 Miami report explicitly links the Sainz–Piastri contact to Piastri's front-wing
  damage, a forced stop, and a drop down the order. That supports damage and repair-stop coding; the
  FIA decision remains controlling for fault:
  [Formula 1 Miami decision report](https://www.formula1.com/en/latest/article/sainz-hit-with-five-second-time-penalty-after-collision-with-piastri-in.3D1JHk6lYz0GzKch77GcrZ).
- Mercedes' 2022 Singapore report distinguishes a wing-change cost from subsequent Safety Car
  position loss and separately links a collision to a puncture. This is why the schema separates
  direct repair burden, neutralization timing, and strategy response:
  [Mercedes Singapore report](https://www.mercedesamgf1.com/news/difficult-race-for-mercedes-amg-in-singapore).
- Williams' 2023 Japanese report states that front wings could be changed but floor damage worsened
  until both cars were retired. That supports a persistent-damage mechanism rather than assuming the
  visible wing replacement fixed the car:
  [Williams Japanese GP report](https://www.williamsf1.com/posts/05f49fb5-62ac-4308-b14d-52f8959cfee8/2023-japanese-grand-prix).
- Haas' 2024 Monaco report explicitly says two cars retired because of damage in a multi-car
  collision. The source is informative for separate harm records for each participant, not one
  two-car row:
  [Haas Monaco report](https://www.haasf1team.com/news/monaco-grand-prix-race-recap-3).

These examples are validation anchors for the schema. They are not a convenience sample for an
effect estimate.

## Required case-level fields

Every damage claim must store:

- incident and affected-driver identifiers;
- exact source URL, owner, grade, publication and retrieval dates;
- source title, speaker/author, and a short evidence span;
- damaged component and damage state;
- whether the source explicitly connects the damage to this incident;
- repair action, stop lap, neutralization state, and observed positions lost;
- retirement link, if any;
- claimed per-lap cost and units, if explicitly attributed;
- corroborating FIA/FastF1 observations;
- reviewer, review status, disagreement status, and notes.

The allowed damage states are `confirmed`, `repair_observed`, `alleged`, `no_confirmed_damage`, and
`unknown`. Silence is never coded as no damage. A slow lap alone is never coded as confirmed damage.

## Search and collection procedure

For every screened collision:

1. resolve the FIA decision, event page, official classification, lap analysis, pit-stop summary,
   and Race Control sequence;
2. search both participants' team race reports and debriefs using event, driver, car number,
   component, collision, contact, puncture, and retirement terms;
3. search Formula1.com and Pirelli for attributed explanations;
4. save only exact, auditable claims; conflicting first-party accounts remain side by side;
5. validate stop lap, stop duration, retirement status, positions, and clean-lap availability;
6. send uncertain causality, visual-only evidence, benefits, and quantified performance claims to
   independent review.

Broken or rewritten pages retain their retrieval result and archive status. A search snippet is not
case evidence. When a historical team domain changed, the exact accessible page is preserved rather
than silently replacing it with a current brand homepage.

## What the method cannot recover

Public telemetry is incomplete, teams rarely publish full aerodynamic-loss estimates, and damage can
be hidden. A missing report therefore means unknown, not undamaged. Team statements may emphasize
their driver's perspective. Pit timing does not reveal whether a stop was planned. A retirement
status can identify an accident but not every causal component. The final report will show evidence
coverage and missingness before any estimate.

Finally, harm is not fault. FIA's public explanation says the driving and penalty guidelines assist
consistent decision-making but have no regulatory value, and historical FIA practice was described
as judging the incident rather than its outcome:
[FIA guideline publication](https://www.fia.com/news/fia-adds-further-transparency-fia-formula-one-world-championship-publication-stewards),
[Formula 1 interview with the 2021 Race Director](https://www.formula1.com/en/latest/article/masi-backs-stewards-on-hamilton-penalty-adding-that-decisions-are-always.52AUb0ZpArxnTSoCDsfahy).
Study v2 therefore uses damage to measure consequence burden, not to back-fill responsibility.
