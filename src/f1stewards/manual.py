"""Validation contracts for reviewable manual analytical inputs."""

from __future__ import annotations

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
