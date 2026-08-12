"""Conservative competitive-impact calculations for reviewed sanctions."""

from __future__ import annotations

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field


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


def remove_post_race_time_penalty(
    results: pd.DataFrame,
    driver_number: int,
    penalty_seconds: float,
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
    adjusted_gap = max(0.0, official_gap - penalty_seconds)
    cohort = results.loc[
        results["laps_completed"].eq(laps_completed)
        & results["finish_position"].notna()
        & results["classification_gap_seconds"].notna()
        & results["finish_position"].lt(official_position)
        & results["classification_gap_seconds"].gt(adjusted_gap)
    ]
    passed = [int(number) for number in cohort["driver_number"].tolist()]
    counterfactual_position = official_position - len(passed)
    return MechanicalPositionResult(
        driver_number=driver_number,
        official_finish_position=official_position,
        counterfactual_finish_position=counterfactual_position,
        positions_gained_without_penalty=len(passed),
        official_gap_seconds=official_gap,
        counterfactual_gap_seconds=adjusted_gap,
        laps_completed=laps_completed,
        passed_driver_numbers=passed,
    )
