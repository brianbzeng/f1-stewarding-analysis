# Competitive Impact Method

Competitive impact is reported as a property of an observed sanction, not as proof that the
underlying decision was correct or incorrect.

The analysis now has two distinct tracks:

1. **sanction burden** - what the penalized driver actually lost because of the sanction; and
2. **victim harm** - what the affected driver observably or credibly lost because of the incident.

Responsibility evidence is the third required input. The report never treats severe harm as proof of
fault and never treats a nominal five-second penalty as five seconds of realized competitive cost.
Seconds, positions, points, repair stops, and retirements remain separate outputs rather than being
collapsed into an arbitrary fairness score.

## Evidence tiers

| Tier | Label | Allowed claim |
|---|---|---|
| A | `mechanical` | remove a post-race-added time and re-rank the official same-lap cohort |
| B | `bounded` | report a defensible range when direct cost is observed but race response is not fixed |
| C | `modeled` | estimate an outcome only with an independently validated counterfactual model |
| D | `not_estimable` | describe the mechanism without a numerical alternate result |

## Mechanical algorithm

For a post-race-added time penalty:

1. Start with the official final classification and completed-lap total; visually inspect tables
   that are not text-extractable.
2. Compare the official table with the normalized timing feed, then convert result timing to a
   classification gap with the race winner fixed at zero.
3. Subtract only the announced penalty from the penalized driver's official gap.
4. Re-rank against drivers who completed the same number of laps.
5. Retain official order on an exact tie.
6. Recalculate standard finishing-position points; handle fastest-lap or other bonuses separately.

This is deterministic classification arithmetic. It does not simulate a different on-track race.

## Victim-harm evidence tiers

| Tier | Label | Allowed claim |
|---|---|---|
| A | `observed` | report an official/timing-observed position change, repair stop, puncture, retirement, or relative-time swing without claiming a no-incident counterfactual |
| B | `bounded` | bound a direct pit-lane or repair cost while leaving uncertain strategy response explicit |
| C | `modeled` | estimate persistent pace or points loss only with a validated counterfactual and propagated uncertainty |
| D | `not_estimable` | describe possible harm when public evidence cannot support a number |

Damage is never inferred from a slow lap alone. `confirmed` requires an FIA decision, official team
debrief, or similarly direct source. A visible repair can support `repair_observed`; timing-only
patterns remain `alleged`, `unknown`, or `no_confirmed_damage` as appropriate.

## Immediate position and relative-time change

For the affected driver, record position immediately before and after the incident and preserve a
signed net change. When both cars have valid timing, calculate the affected driver's relative loss
across the incident lap as:

```text
(counterparty start - affected start) before
  - (counterparty start - affected start) after
```

This captures what changed on the clock. It does not separate contact from the attempted pass,
defensive line, wheel-to-wheel delay, tyre state, or other race dynamics.

## Repair stops and rare beneficial stops

A stop is incident-responsive only when an official source confirms it or the timing/video evidence
makes the link defensible. Report separately:

- normal pit-lane transit under the observed green/Safety Car/VSC state;
- stationary service time beyond a comparable tyre-only stop;
- observed positions lost between pit entry and stable rejoin order; and
- uncertainty about whether the stop overlapped the team's planned window.

An incident-triggered stop is not automatically coded as harmful. It can be `possible_benefit` or
`benefit` when it coincides with a planned stop window, occurs under a cheaper Safety Car/VSC pit
window, supplies a useful tyre offset, or produces a favorable undercut. A confirmed benefit needs a
validated alternate-strategy comparison; otherwise the mechanism is reported without a numerical
claim. This prevents the analysis from assigning a generic 30-second loss to every forced stop.

## Persistent pace loss

Persistent loss is modeled only when enough clean laps exist on both sides of the incident. The
primary design compares the affected driver's change with a teammate/field reference while
controlling for compound, tyre age, fuel-lap trend, track evolution, traffic, weather, and Safety
Car/VSC state. Pit in/out laps, materially impeded laps, first laps, and end-of-race anomalies are
excluded. The minimum clean-lap rule and sensitivity windows are frozen in
`config/analysis_thresholds.yml`.

For an estimated per-lap deficit `d` over `L` exposed laps:

```text
persistent loss = d * L
```

The report includes lower/point/upper estimates from grouped bootstrap or posterior uncertainty.
If the minimum clean-lap requirement fails, the case is `insufficient_data`; one normal-looking lap
does not establish that the car was undamaged.

## Harm-sanction proportionality

The proportionality table displays, side by side:

- responsibility status and its evidence;
- victim harm by time, position, points, repair, or retirement;
- nominal sanction; and
- realized sanction burden in time, position, and points.

Formal proportionality review is limited to fault-established incidents with reviewed harm evidence.
A no-action racing incident can show large observed harm, but it is labeled
`not_comparable_without_fault_finding` rather than automatically called an inadequate penalty.
Likewise, a five-second post-race penalty that changes no position or points has a five-second nominal
value but zero realized classification burden.

This is an external distributive-fairness lens, not the same estimand as FIA guideline conformance.
The [2018 Azerbaijan Right of Review decision](https://www.fia.com/file/68044/download?token=T9Ow9Dxc)
states that the consequences of penalties were not taken into account, while the
[2024 Australian Grand Prix decision on Car 14](https://www.fia.com/sites/default/files/decision-document/2024%20Australian%20Grand%20Prix%20-%20Infringement%20-%20Car%2014%20-%20Potentially%20dangerous%20driving.pdf)
explicitly says that panel did not consider the consequences of the crash. The report therefore may
identify a large competitive asymmetry without claiming that the stewards misapplied the governing
rule or guideline.

## Pilot examples, pending review

- Sergio Perez, 2023 Abu Dhabi: removing a five-second post-race addition changes the calculated
  classification from P4 to P2 and standard finishing points from 12 to 18.
- Franco Colapinto, 2025 Austria: removing five seconds leaves the calculated classification at P15.
- Yuki Tsunoda, 2025 Austria: the ten-second penalty was served during the race, so no mechanical
  finishing-position counterfactual is reported.
- Kimi Antonelli, 2025 Austria: the three-place drop applies at the next event, so no Austrian-race
  counterfactual is reported.

All four rows are `single_coded_pending_human`. These are pipeline demonstrations, not final study
findings.

The first two mirrored victim-harm pilot rows are also pending review. In 2019 Austria,
official/timing evidence shows Leclerc moving from P1 to P2 and Verstappen from P2 to P1, with a
1.683-second relative swing across lap 69. Neither car made a repair stop. Leclerc's one clean
post-incident lap was not slower than his short pre-incident baseline, but one lap is insufficient for
a persistent-damage estimate; the mirrored Verstappen row is similarly insufficient. The FIA found
neither driver wholly or predominantly responsible, so these rows demonstrate observed harm/gain
without a reportable harm-sanction proportionality verdict.
