"""Validation contracts for reviewable manual analytical inputs."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class CodedAdjudication(BaseModel):
    model_config = ConfigDict(extra="forbid")

    adjudication_id: str
    incident_id: str
    event_id: str
    source_document_id: str
    source_url: HttpUrl
    accused_driver_number: int = Field(ge=1, le=99)
    affected_driver_number: int = Field(ge=1, le=99)
    session_type: Literal["Race", "Sprint"]
    lap_number: int = Field(ge=1)
    turn_number: int | None = Field(default=None, ge=1)
    incident_family: Literal[
        "causing_collision",
        "forcing_off_track",
        "gaining_advantage_off_track",
        "unsafe_rejoin",
        "moving_under_braking",
        "multiple_defensive_moves",
    ]
    outcome_family: Literal[
        "no_further_action",
        "warning",
        "reprimand",
        "time_penalty",
        "drive_through",
        "stop_go",
        "grid_penalty",
        "disqualification",
        "other",
    ]
    penalty_seconds: float | None = Field(default=None, ge=0)
    penalty_points: int | None = Field(default=None, ge=0)
    grid_places: int | None = Field(default=None, ge=0)
    fault_language: Literal[
        "wholly_to_blame",
        "predominantly_to_blame",
        "mainly_at_fault",
        "shared_fault",
        "racing_incident",
        "no_conclusion",
        "not_applicable",
    ]
    evidence_video: bool
    evidence_positioning: bool
    evidence_telemetry: bool
    evidence_team_radio: bool
    guideline_regime: str
    guideline_clause: str
    guideline_expected_outcome: str
    conformance_status: Literal[
        "conformant", "mitigated", "aggravated", "departed", "not_applicable", "unclear"
    ]
    mitigating_factor_written: bool
    first_lap: bool
    include_primary: bool
    coder_id: str
    review_status: Literal["single_coded_pending_human", "double_coded", "adjudicated"]
    coding_notes: str

    @model_validator(mode="after")
    def validate_outcome_fields(self) -> CodedAdjudication:
        if self.accused_driver_number == self.affected_driver_number:
            raise ValueError("accused and affected drivers must differ")
        if self.outcome_family == "no_further_action" and any(
            value not in (None, 0)
            for value in (self.penalty_seconds, self.penalty_points, self.grid_places)
        ):
            raise ValueError("no-further-action records cannot carry a sanction")
        if self.outcome_family == "time_penalty" and not self.penalty_seconds:
            raise ValueError("time penalties require penalty_seconds")
        if self.outcome_family == "grid_penalty" and not self.grid_places:
            raise ValueError("grid penalties require grid_places")
        return self


class ImpactAssessment(BaseModel):
    """One explicitly tiered competitive-impact assessment."""

    model_config = ConfigDict(extra="forbid")

    impact_assessment_id: str
    adjudication_id: str
    event_id: str
    source_document_id: str
    classification_source_document_id: str
    driver_number: int = Field(ge=1, le=99)
    sanction_type: Literal["time_penalty", "grid_penalty"]
    penalty_seconds: float | None = Field(default=None, gt=0)
    grid_places: int | None = Field(default=None, gt=0)
    sanction_application: Literal["post_race_added", "served_during_race", "next_event_grid"]
    impact_level: Literal["mechanical", "bounded", "modeled", "not_estimable"]
    official_finish_position: int | None = Field(default=None, ge=1)
    counterfactual_finish_position: int | None = Field(default=None, ge=1)
    positions_gained_without_penalty: int | None = Field(default=None, ge=0)
    official_points: float = Field(ge=0)
    counterfactual_points: float | None = Field(default=None, ge=0)
    points_gained_without_penalty: float | None = Field(default=None, ge=0)
    podium_changed: bool | None = None
    win_changed: bool | None = None
    calculation_method: str
    assumptions: str
    review_status: Literal["single_coded_pending_human", "double_coded", "adjudicated"]

    @model_validator(mode="after")
    def validate_impact_tier(self) -> ImpactAssessment:
        if self.sanction_type == "time_penalty" and self.penalty_seconds is None:
            raise ValueError("time penalties require penalty_seconds")
        if self.sanction_type == "grid_penalty" and self.grid_places is None:
            raise ValueError("grid penalties require grid_places")
        arithmetic = (
            self.counterfactual_finish_position,
            self.positions_gained_without_penalty,
            self.counterfactual_points,
            self.points_gained_without_penalty,
            self.podium_changed,
            self.win_changed,
        )
        if self.impact_level == "mechanical":
            if self.sanction_application != "post_race_added":
                raise ValueError("mechanical impact requires a post-race-added sanction")
            if self.official_finish_position is None:
                raise ValueError("mechanical impact requires an official finish position")
            if any(value is None for value in arithmetic):
                raise ValueError("mechanical impact requires complete arithmetic")
            if self.positions_gained_without_penalty != (
                self.official_finish_position - self.counterfactual_finish_position
            ):
                raise ValueError("positions_gained_without_penalty does not match positions")
            if self.points_gained_without_penalty != (
                self.counterfactual_points - self.official_points
            ):
                raise ValueError("points_gained_without_penalty does not match points")
        if self.impact_level == "not_estimable" and any(
            value is not None for value in arithmetic
        ):
            raise ValueError("not-estimable impact cannot contain counterfactual arithmetic")
        return self


class HarmAssessment(BaseModel):
    """One affected-driver assessment of incident harm and any lasting consequence."""

    model_config = ConfigDict(extra="forbid")

    harm_assessment_id: str
    adjudication_id: str
    incident_id: str
    event_id: str
    source_document_id: str
    classification_source_document_id: str
    affected_driver_number: int = Field(ge=1, le=99)
    counterparty_driver_number: int = Field(ge=1, le=99)
    responsibility_status: Literal[
        "fault_established",
        "shared_or_racing_incident",
        "no_fault_finding",
        "unresolved",
    ]
    harm_evidence_level: Literal["observed", "bounded", "modeled", "not_estimable"]
    damage_evidence: Literal[
        "confirmed",
        "repair_observed",
        "alleged",
        "no_confirmed_damage",
        "unknown",
    ]
    damage_type: Literal[
        "none_identified",
        "front_wing",
        "puncture",
        "floor_or_bodywork",
        "suspension",
        "terminal",
        "multiple",
        "other",
        "unknown",
    ]
    repair_stop_required: Literal["yes", "no", "unclear"]
    pit_lap: int | None = Field(default=None, ge=1)
    pit_response_status: Literal["confirmed", "plausible", "no", "unclear"]
    pit_lane_loss_seconds: float | None = Field(default=None, ge=0)
    repair_stationary_seconds: float | None = Field(default=None, ge=0)
    retirement_status: Literal[
        "incident_caused", "no_retirement", "other_cause", "unclear"
    ]
    position_before: int | None = Field(default=None, ge=1)
    position_after: int | None = Field(default=None, ge=1)
    net_positions_lost_observed: int | None = Field(default=None, ge=-19, le=19)
    position_window_start_lap: int | None = Field(default=None, ge=1)
    position_window_end_lap: int | None = Field(default=None, ge=1)
    relative_time_comparator_driver_number: int | None = Field(default=None, ge=1, le=99)
    affected_relative_time_loss_seconds: float | None = None
    relative_time_window_start_lap: int | None = Field(default=None, ge=1)
    relative_time_window_end_lap: int | None = Field(default=None, ge=1)
    post_incident_clean_laps: int = Field(ge=0)
    persistent_pace_status: Literal[
        "confirmed_loss",
        "modeled_loss",
        "no_detectable_loss",
        "insufficient_data",
        "not_applicable",
    ]
    persistent_delta_per_lap_seconds: float | None = Field(default=None, ge=0)
    persistent_laps_exposed: int | None = Field(default=None, ge=1)
    persistent_loss_seconds_lower: float | None = Field(default=None, ge=0)
    persistent_loss_seconds_estimate: float | None = Field(default=None, ge=0)
    persistent_loss_seconds_upper: float | None = Field(default=None, ge=0)
    net_effect_direction: Literal[
        "harmed", "neutral", "possible_benefit", "benefit", "unclear"
    ]
    benefit_mechanism: str | None = None
    evidence_urls: str
    calculation_method: str
    assumptions: str
    review_status: Literal["single_coded_pending_human", "double_coded", "adjudicated"]

    @model_validator(mode="after")
    def validate_harm_evidence(self) -> HarmAssessment:
        if self.affected_driver_number == self.counterparty_driver_number:
            raise ValueError("affected and counterparty drivers must differ")

        position_fields = (
            self.position_before,
            self.position_after,
            self.net_positions_lost_observed,
        )
        if any(value is not None for value in position_fields):
            if any(value is None for value in position_fields):
                raise ValueError("observed position harm requires complete before/after arithmetic")
            if self.net_positions_lost_observed != self.position_after - self.position_before:
                raise ValueError("net_positions_lost_observed does not match positions")
        position_laps = (self.position_window_start_lap, self.position_window_end_lap)
        if any(value is not None for value in position_laps):
            if any(value is None for value in position_laps) or any(
                value is None for value in position_fields
            ):
                raise ValueError("position windows require complete lap and position arithmetic")
            if self.position_window_end_lap <= self.position_window_start_lap:
                raise ValueError("position window must end after it starts")

        relative_time_fields = (
            self.relative_time_comparator_driver_number,
            self.relative_time_window_start_lap,
            self.relative_time_window_end_lap,
        )
        if self.affected_relative_time_loss_seconds is None and any(
            value is not None for value in relative_time_fields
        ):
            raise ValueError("relative-time context requires a relative-time observation")
        if self.relative_time_window_start_lap is not None:
            if self.relative_time_window_end_lap is None:
                raise ValueError("relative-time windows require both lap bounds")
            if self.relative_time_window_end_lap <= self.relative_time_window_start_lap:
                raise ValueError("relative-time window must end after it starts")
        elif self.relative_time_window_end_lap is not None:
            raise ValueError("relative-time windows require both lap bounds")

        pit_fields = (self.pit_lap, self.pit_lane_loss_seconds, self.repair_stationary_seconds)
        if self.repair_stop_required == "yes" and (
            self.pit_lap is None
            or self.pit_response_status not in {"confirmed", "plausible"}
        ):
            raise ValueError("repair stops require a pit lap and incident-response evidence")
        if self.repair_stop_required == "no" and (
            any(value is not None for value in pit_fields) or self.pit_response_status != "no"
        ):
            raise ValueError("no-repair-stop records cannot contain pit-loss fields")

        if self.damage_evidence in {"confirmed", "repair_observed"} and self.damage_type in {
            "none_identified",
            "unknown",
        }:
            raise ValueError("confirmed or observed damage requires a specific damage type")

        pace_fields = (
            self.persistent_delta_per_lap_seconds,
            self.persistent_laps_exposed,
            self.persistent_loss_seconds_lower,
            self.persistent_loss_seconds_estimate,
            self.persistent_loss_seconds_upper,
        )
        if self.persistent_pace_status == "modeled_loss":
            if self.harm_evidence_level != "modeled" or any(
                value is None for value in pace_fields
            ):
                raise ValueError("modeled persistent loss requires a complete modeled estimate")
            expected = self.persistent_delta_per_lap_seconds * self.persistent_laps_exposed
            if abs(self.persistent_loss_seconds_estimate - expected) > 1e-9:
                raise ValueError("persistent loss estimate must equal delta per lap times exposure")
        elif self.persistent_pace_status in {
            "no_detectable_loss",
            "insufficient_data",
            "not_applicable",
        } and any(value is not None for value in pace_fields):
            raise ValueError("non-modeled persistent-pace status cannot contain pace estimates")

        interval = (
            self.persistent_loss_seconds_lower,
            self.persistent_loss_seconds_estimate,
            self.persistent_loss_seconds_upper,
        )
        if all(value is not None for value in interval) and not (
            self.persistent_loss_seconds_lower
            <= self.persistent_loss_seconds_estimate
            <= self.persistent_loss_seconds_upper
        ):
            raise ValueError("persistent loss interval must contain the estimate")

        if self.net_effect_direction in {"possible_benefit", "benefit"}:
            if not self.benefit_mechanism:
                raise ValueError("beneficial effects require a documented mechanism")
        elif self.benefit_mechanism:
            raise ValueError("benefit_mechanism is only valid for possible or observed benefit")
        return self


class IncidentLocation(BaseModel):
    """Supplemental incident location when one scalar turn cannot preserve the source."""

    model_config = ConfigDict(extra="forbid")

    location_id: str
    incident_id: str
    event_id: str
    source_document_id: str
    session_type: Literal["Race", "Sprint"]
    lap_number: int = Field(ge=1)
    location_type: Literal[
        "single_turn", "turn_range", "straight", "pit_lane", "other", "unknown"
    ]
    turn_start_number: int | None = Field(default=None, ge=1)
    turn_end_number: int | None = Field(default=None, ge=1)
    location_text: str
    evidence_urls: str
    coding_notes: str
    coder_id: str
    review_status: Literal["single_coded_pending_human", "double_coded", "adjudicated"]

    @model_validator(mode="after")
    def validate_location(self) -> IncidentLocation:
        if self.location_type == "single_turn":
            if self.turn_start_number is None or self.turn_end_number is not None:
                raise ValueError("single-turn locations require only turn_start_number")
        elif self.location_type == "turn_range":
            if self.turn_start_number is None or self.turn_end_number is None:
                raise ValueError("turn ranges require both turn bounds")
            if self.turn_end_number <= self.turn_start_number:
                raise ValueError("turn ranges must end after they start")
        elif self.turn_start_number is not None or self.turn_end_number is not None:
            raise ValueError("non-turn locations cannot contain turn bounds")
        return self


class IncidentRelation(BaseModel):
    """One directed, evidence-tiered edge in a potentially multi-car incident chain."""

    model_config = ConfigDict(extra="forbid")

    relation_id: str
    incident_id: str
    event_id: str
    source_document_id: str
    sequence: int = Field(ge=1)
    source_driver_number: int = Field(ge=1, le=99)
    target_driver_number: int = Field(ge=1, le=99)
    relation_type: Literal[
        "direct_contact",
        "secondary_contact",
        "forced_off_track",
        "visibility_obstruction",
        "avoidance",
        "debris_effect",
        "sporting_benefit",
        "other",
    ]
    relation_scope: Literal[
        "primary_infringement",
        "mitigating_context",
        "aggravating_context",
        "downstream_harm",
        "observed_context",
        "unresolved",
    ]
    fault_attributed: bool
    evidence_level: Literal[
        "official_explicit", "official_implied", "manual_observed", "unresolved"
    ]
    evidence_urls: str
    coding_notes: str
    coder_id: str
    review_status: Literal["single_coded_pending_human", "double_coded", "adjudicated"]

    @model_validator(mode="after")
    def validate_relation(self) -> IncidentRelation:
        if self.source_driver_number == self.target_driver_number:
            raise ValueError("incident relations require distinct drivers")
        if self.fault_attributed and self.relation_scope not in {
            "primary_infringement",
            "downstream_harm",
        }:
            raise ValueError("fault attribution requires an infringement or downstream-harm edge")
        return self


class CrossEventSanctionEffect(BaseModel):
    """Realized application of a sanction carried from one event into another."""

    model_config = ConfigDict(extra="forbid")

    cross_event_effect_id: str
    adjudication_id: str
    origin_event_id: str
    application_event_id: str
    source_document_id: str
    driver_number: int = Field(ge=1, le=99)
    sanction_type: Literal["grid_penalty"]
    nominal_grid_places: int = Field(gt=0)
    qualifying_position: int = Field(ge=1, le=20)
    starting_grid_position: int = Field(ge=1, le=20)
    realized_grid_places_lost: int = Field(ge=-19, le=19)
    grid_effect_level: Literal["mechanical", "bounded", "not_estimable"]
    official_finish_position: int | None = Field(default=None, ge=1, le=20)
    race_status: Literal[
        "finished", "classified_lapped", "retired", "did_not_start", "disqualified", "unknown"
    ]
    official_points: float = Field(ge=0)
    finish_effect_level: Literal["mechanical", "bounded", "modeled", "not_estimable"]
    counterfactual_finish_position: int | None = Field(default=None, ge=1, le=20)
    counterfactual_points: float | None = Field(default=None, ge=0)
    application_grid_url: HttpUrl
    application_classification_url: HttpUrl
    evidence_urls: str
    calculation_method: str
    assumptions: str
    review_status: Literal["single_coded_pending_human", "double_coded", "adjudicated"]

    @model_validator(mode="after")
    def validate_cross_event_effect(self) -> CrossEventSanctionEffect:
        if self.origin_event_id == self.application_event_id:
            raise ValueError("cross-event sanctions require distinct origin and application events")
        if self.realized_grid_places_lost != (
            self.starting_grid_position - self.qualifying_position
        ):
            raise ValueError("realized grid loss does not match qualifying and starting positions")
        if self.grid_effect_level == "mechanical" and self.realized_grid_places_lost < 0:
            raise ValueError("mechanical grid effects cannot report a position gain")
        maximum_nominal_loss = min(
            self.nominal_grid_places,
            20 - self.qualifying_position,
        )
        if (
            self.grid_effect_level == "mechanical"
            and self.realized_grid_places_lost != maximum_nominal_loss
        ):
            raise ValueError(
                "mechanical grid loss must equal the nominal sanction after grid saturation"
            )
        if self.race_status in {"finished", "classified_lapped"} and (
            self.official_finish_position is None
        ):
            raise ValueError("classified race statuses require an official finish position")
        if self.finish_effect_level == "not_estimable" and (
            self.counterfactual_finish_position is not None
            or self.counterfactual_points is not None
        ):
            raise ValueError("not-estimable finish effects cannot contain counterfactual outcomes")
        return self


class IndependentReviewRecord(BaseModel):
    """Human review record that preserves the initial coding rather than overwriting it."""

    model_config = ConfigDict(extra="forbid")

    review_id: str
    target_type: Literal[
        "adjudication",
        "impact_assessment",
        "harm_assessment",
        "incident_location",
        "incident_relation",
        "cross_event_sanction_effect",
    ]
    target_id: str
    evidence_urls: str
    initial_summary: str
    review_status: Literal["pending", "agree", "correct", "needs_discussion"]
    reviewer_id: str | None = None
    reviewed_at_utc: datetime | None = None
    review_minutes: float | None = Field(default=None, gt=0)
    corrected_fields_json: str | None = None
    reviewer_notes: str | None = None

    @model_validator(mode="after")
    def validate_review_completion(self) -> IndependentReviewRecord:
        if self.review_status == "pending":
            return self
        if not self.reviewer_id or self.reviewed_at_utc is None or self.review_minutes is None:
            raise ValueError(
                "completed review requires reviewer_id, reviewed_at_utc, and review_minutes"
            )
        if self.review_status == "agree" and self.corrected_fields_json:
            raise ValueError("agree review cannot contain corrected_fields_json")
        if self.review_status == "correct":
            if not self.corrected_fields_json or not self.reviewer_notes:
                raise ValueError("correct review requires corrected fields and reviewer notes")
            try:
                corrected = json.loads(self.corrected_fields_json)
            except json.JSONDecodeError as exc:
                raise ValueError("corrected_fields_json must be valid JSON") from exc
            if not isinstance(corrected, dict) or not corrected:
                raise ValueError("corrected_fields_json must be a non-empty object")
        if self.review_status == "needs_discussion" and not self.reviewer_notes:
            raise ValueError("needs-discussion review requires reviewer notes")
        return self
