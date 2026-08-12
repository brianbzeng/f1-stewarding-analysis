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

### `fault_language`

Controlled values include `wholly_to_blame`, `predominantly_to_blame`, `mainly_at_fault`, `shared_fault`, `racing_incident`, `no_conclusion`, and `not_applicable`. This field comes from the decision narrative and cannot independently validate the stewards' fault finding.

## Nationality roles

- `accused_driver_nationality`: nationality represented by the driver in the relevant season.
- `affected_driver_nationality`: nationality represented by the principal counterparty.
- `same_nationality_panel_member`: at least one steward shares the accused driver's defined nationality.
- `home_race_accused`: event country matches the accused driver's defined nationality under the published crosswalk.

Ambiguous nationality relationships are manual-review cases. Nationality is never inferred from a name.
