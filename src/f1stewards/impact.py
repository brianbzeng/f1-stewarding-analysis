"""Conservative competitive-impact calculations for reviewed sanctions."""

from __future__ import annotations

from typing import Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

RACE_POSITION_POINTS = {1: 25, 2: 18, 3: 15, 4: 12, 5: 10, 6: 8, 7: 6, 8: 4, 9: 2, 10: 1}
SPRINT_2021_POSITION_POINTS = {1: 3, 2: 2, 3: 1}
SPRINT_2022_POSITION_POINTS = {1: 8, 2: 7, 3: 6, 4: 5, 5: 4, 6: 3, 7: 2, 8: 1}
POINTS_SCOPE = "standard_position_points_only_excludes_bonuses_and_exceptional_awards"


class MechanicalPositionResult(BaseModel):
    """Exact re-ranking result under a narrow time-removal counterfactual."""

    model_config = ConfigDict(extra="forbid")

    driver_number: int
    official_finish_position: int = Field(ge=1)
    counterfactual_finish_position: int = Field(ge=1)
    positions_gained_without_penalty: int = Field(ge=0)
    official_gap_seconds: float = Field(ge=0)
    counterfactual_gap_seconds: float = Field(ge=0)
    laps_completed: int = Field(ge=1)
    passed_driver_numbers: list[int]
    season: int | None = Field(default=None, ge=2018, le=2025)
    session_type: Literal["Race", "Sprint"] | None = None
    official_position_points: float | None = Field(default=None, ge=0)
    counterfactual_position_points: float | None = Field(default=None, ge=0)
    position_points_gained_without_penalty: float | None = Field(default=None, ge=0)
    podium_changed: bool
    win_changed: bool
    points_scope: str | None = None


class GridDisplacementResult(BaseModel):
    """Observed grid displacement with conservative mechanical-attribution status."""

    model_config = ConfigDict(extra="forbid")

    qualifying_position: int = Field(ge=1)
    starting_grid_position: int = Field(ge=1)
    nominal_grid_places: int = Field(gt=0)
    grid_size: int = Field(ge=1)
    realized_grid_places_lost: int
    maximum_nominal_loss_with_grid_saturation: int = Field(ge=0)
    attribution_status: Literal[
        "mechanical_exact_nominal",
        "mechanical_grid_saturation",
        "confounded_grid_reordering",
        "confounded_position_gain",
    ]
    finish_effect_status: Literal["not_estimable_from_grid_displacement"]


def standard_position_points(season: int, session_type: str, position: int) -> float:
    """Return standard position points, excluding bonuses and exceptional race awards."""

    if not 2018 <= season <= 2025:
        raise ValueError("season must be between 2018 and 2025")
    if position < 1:
        raise ValueError("position must be positive")
    if session_type == "Race":
        schedule = RACE_POSITION_POINTS
    elif session_type == "Sprint" and season == 2021:
        schedule = SPRINT_2021_POSITION_POINTS
    elif session_type == "Sprint" and season >= 2022:
        schedule = SPRINT_2022_POSITION_POINTS
    elif session_type == "Sprint":
        raise ValueError(f"Formula One Sprint points do not apply in {season}")
    else:
        raise ValueError("session_type must be Race or Sprint")
    return float(schedule.get(position, 0))


def calculate_grid_displacement(
    qualifying_position: int,
    starting_grid_position: int,
    nominal_grid_places: int,
    *,
    grid_size: int = 20,
) -> GridDisplacementResult:
    """Separate observed grid movement from strategy-dependent race consequences."""

    if grid_size < 1:
        raise ValueError("grid_size must be positive")
    if not 1 <= qualifying_position <= grid_size:
        raise ValueError("qualifying_position must fall within the grid")
    if not 1 <= starting_grid_position <= grid_size:
        raise ValueError("starting_grid_position must fall within the grid")
    if nominal_grid_places <= 0:
        raise ValueError("nominal_grid_places must be positive")
    realized = starting_grid_position - qualifying_position
    maximum_nominal_loss = min(nominal_grid_places, grid_size - qualifying_position)
    if realized < 0:
        status = "confounded_position_gain"
    elif realized == nominal_grid_places:
        status = "mechanical_exact_nominal"
    elif nominal_grid_places > grid_size - qualifying_position and realized == maximum_nominal_loss:
        status = "mechanical_grid_saturation"
    else:
        status = "confounded_grid_reordering"
    return GridDisplacementResult(
        qualifying_position=qualifying_position,
        starting_grid_position=starting_grid_position,
        nominal_grid_places=nominal_grid_places,
        grid_size=grid_size,
        realized_grid_places_lost=realized,
        maximum_nominal_loss_with_grid_saturation=maximum_nominal_loss,
        attribution_status=status,
        finish_effect_status="not_estimable_from_grid_displacement",
    )


def remove_post_race_time_penalty(
    results: pd.DataFrame,
    driver_number: int,
    penalty_seconds: float,
    *,
    season: int | None = None,
    session_type: Literal["Race", "Sprint"] | None = None,
) -> MechanicalPositionResult:
    """Remove an added post-race penalty and re-rank only the same-lap cohort.

    This deliberately does not model strategy, traffic, tyre state, or a penalty served during
    the race. Equal adjusted times retain official order, a conservative tie treatment.
    """

    if penalty_seconds <= 0:
        raise ValueError("penalty_seconds must be positive")
    required = {
        "driver_number",
        "finish_position",
        "laps_completed",
        "classification_gap_seconds",
    }
    missing = required - set(results.columns)
    if missing:
        raise ValueError(f"results missing required columns: {', '.join(sorted(missing))}")
    if results["driver_number"].duplicated().any():
        raise ValueError("driver_number must be unique in one official classification")
    if (season is None) != (session_type is None):
        raise ValueError("season and session_type must be supplied together for points arithmetic")
    target = results.loc[results["driver_number"] == driver_number]
    if len(target) != 1:
        raise ValueError(f"expected one result for driver {driver_number}; found {len(target)}")
    target_row = target.iloc[0]
    if pd.isna(target_row["finish_position"]) or pd.isna(target_row["laps_completed"]):
        raise ValueError("target classification position or completed laps is missing")
    if pd.isna(target_row["classification_gap_seconds"]):
        raise ValueError("target has no classification gap for exact arithmetic")

    official_position = int(target_row["finish_position"])
    laps_completed = int(target_row["laps_completed"])
    official_gap = float(target_row["classification_gap_seconds"])
    same_lap = results.loc[
        results["laps_completed"].eq(laps_completed)
        & results["finish_position"].notna()
        & results["classification_gap_seconds"].notna()
    ].sort_values("finish_position", kind="stable")
    if same_lap["finish_position"].duplicated().any():
        raise ValueError("same-lap official finish positions must be unique")
    if not same_lap["classification_gap_seconds"].astype(float).is_monotonic_increasing:
        raise ValueError("same-lap classification gaps must follow official finishing order")
    adjusted_gap = max(0.0, official_gap - penalty_seconds)
    cohort = same_lap.loc[
        same_lap["finish_position"].lt(official_position)
        & same_lap["classification_gap_seconds"].gt(adjusted_gap)
    ].sort_values("finish_position", kind="stable")
    passed = [int(number) for number in cohort["driver_number"].tolist()]
    counterfactual_position = official_position - len(passed)
    official_points = (
        standard_position_points(season, session_type, official_position)
        if season is not None and session_type is not None
        else None
    )
    counterfactual_points = (
        standard_position_points(season, session_type, counterfactual_position)
        if season is not None and session_type is not None
        else None
    )
    return MechanicalPositionResult(
        driver_number=driver_number,
        official_finish_position=official_position,
        counterfactual_finish_position=counterfactual_position,
        positions_gained_without_penalty=len(passed),
        official_gap_seconds=official_gap,
        counterfactual_gap_seconds=adjusted_gap,
        laps_completed=laps_completed,
        passed_driver_numbers=passed,
        season=season,
        session_type=session_type,
        official_position_points=official_points,
        counterfactual_position_points=counterfactual_points,
        position_points_gained_without_penalty=(
            counterfactual_points - official_points
            if official_points is not None and counterfactual_points is not None
            else None
        ),
        podium_changed=official_position > 3 and counterfactual_position <= 3,
        win_changed=official_position > 1 and counterfactual_position == 1,
        points_scope=POINTS_SCOPE if season is not None else None,
    )
