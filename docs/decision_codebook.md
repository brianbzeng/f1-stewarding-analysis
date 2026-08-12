# Incident and Decision Codebook

Status: initial pilot draft. Definitions will be revised before full manual coding and frozen before outcome modeling.

## Outcome fields

### `sanction_outcome`

The final formal outcome for the accused driver. `no_further_action` is an observed outcome and must never be stored as null.

### `penalty_seconds`

Nominal time stated in the final decision. A drive-through or stop-and-go is not converted into seconds in the source field; modeled equivalents belong in a separate analytical field.

### `penalty_points`

Super Licence penalty points explicitly imposed by the final decision.

## Primary incident families

### `causing_collision`

The final allegation or fact states that the accused driver caused a collision. Preserve whether the decision found no driver wholly or predominantly at fault.

### `forcing_off_track`

The accused driver allegedly failed to leave required racing room and forced another driver beyond track limits.

### `leaving_track_gaining_advantage`

The accused driver left the track and retained a sporting advantage in time, position, or maintenance of position.

### `unsafe_rejoin`

The accused driver rejoined after leaving the track in a manner alleged to endanger or impede another competitor.

### `moving_under_braking`

The accused driver changed direction in the braking zone in a manner covered by the applicable rule/guideline.

### `multiple_defensive_moves`

The accused driver made more than one direction change while defending.

## Context fields

### `first_lap`

True only when the incident occurred before the accused driver completed lap one of a Race or Sprint. A restart later in the race is coded separately.

### `immediate_sporting_consequence`

One of `none_obvious`, `position_loss`, `damage`, `retirement`, `multiple`, or `unclear`. Store the underlying component fields as well.

### `mitigating_factor_written`

True only when the final decision explicitly identifies a circumstance that reduced the sanction or affected the finding. The text excerpt is retained.

### `aggravating_factor_written`

True only when the final decision explicitly identifies a circumstance that increased the sanction or affected the finding. The text excerpt is retained.

## Victim-harm fields

### `responsibility_status`

The responsibility condition under which harm may be compared with sanction burden:
`fault_established`, `shared_or_racing_incident`, `no_fault_finding`, or `unresolved`. Large harm does
not change this field and is not evidence of fault by itself.

### `damage_evidence`

One of `confirmed`, `repair_observed`, `alleged`, `no_confirmed_damage`, or `unknown`. `confirmed`
requires an official decision, official team debrief, or similarly direct source. Slow laps or a pit
stop alone do not confirm damage.

### `repair_stop_required` and `pit_response_status`

`repair_stop_required` records `yes`, `no`, or `unclear`. The response link is separately coded as
`confirmed`, `plausible`, `no`, or `unclear`. A stop can be real without its causal link to the
incident being confirmed.

### `net_positions_lost_observed`

Signed arithmetic equal to `position_after - position_before`. Positive values are positions lost;
negative values are positions gained. It is an observed before/after change, not a no-incident
counterfactual.

### `affected_relative_time_loss_seconds`

The affected driver's relative gap deterioration across the incident lap. It includes the attempted
pass, altered lines, contact, and race dynamics, so it is never described as pure damage cost.

### `persistent_pace_status`

One of `confirmed_loss`, `modeled_loss`, `no_detectable_loss`, `insufficient_data`, or
`not_applicable`. A modeled loss requires the frozen clean-lap minimum and a complete uncertainty
interval. One normal post-incident lap is `insufficient_data`, not proof of no damage.

### `net_effect_direction`

One of `harmed`, `neutral`, `possible_benefit`, `benefit`, or `unclear`. `possible_benefit` and
`benefit` require a documented mechanism such as a Safety Car/VSC pit discount, planned-stop overlap,
useful tyre offset, or undercut. A generic forced-stop time assumption is prohibited.

### `fault_language`

Controlled values include `wholly_to_blame`, `predominantly_to_blame`, `mainly_at_fault`, `shared_fault`, `racing_incident`, `no_conclusion`, and `not_applicable`. This field comes from the decision narrative and cannot independently validate the stewards' fault finding.

## Nationality roles

- `accused_driver_nationality`: nationality represented by the driver in the relevant season.
- `affected_driver_nationality`: nationality represented by the principal counterparty.
- `same_nationality_panel_member`: at least one steward shares the accused driver's defined nationality.
- `home_race_accused`: event country matches the accused driver's defined nationality under the published crosswalk.

Ambiguous nationality relationships are manual-review cases. Nationality is never inferred from a name.
