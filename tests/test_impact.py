import pandas as pd
import pytest

from f1stewards.impact import (
    calculate_grid_displacement,
    remove_post_race_time_penalty,
    standard_position_points,
)


def test_remove_post_race_penalty_reorders_same_lap_finishers() -> None:
    results = pd.DataFrame(
        {
            "driver_number": [1, 16, 63, 11, 4],
            "finish_position": [1, 2, 3, 4, 5],
            "laps_completed": [58, 58, 58, 58, 58],
            "classification_gap_seconds": [0.0, 17.993, 20.328, 21.453, 24.284],
        }
    )

    impact = remove_post_race_time_penalty(
        results.sample(frac=1, random_state=7),
        11,
        5,
        season=2023,
        session_type="Race",
    )

    assert impact.counterfactual_finish_position == 2
    assert impact.positions_gained_without_penalty == 2
    assert impact.passed_driver_numbers == [16, 63]
    assert impact.counterfactual_gap_seconds == pytest.approx(16.453)
    assert impact.official_position_points == 12
    assert impact.counterfactual_position_points == 18
    assert impact.position_points_gained_without_penalty == 6
    assert impact.podium_changed
    assert not impact.win_changed


def test_remove_post_race_penalty_does_not_cross_lap_cohorts() -> None:
    results = pd.DataFrame(
        {
            "driver_number": [10, 18, 43, 22],
            "finish_position": [13, 14, 15, 16],
            "laps_completed": [69, 69, 69, 68],
            "classification_gap_seconds": [33.055, 34.462, 42.692, 2.979],
        }
    )

    impact = remove_post_race_time_penalty(results, 43, 5)

    assert impact.counterfactual_finish_position == 15
    assert impact.positions_gained_without_penalty == 0


def test_remove_post_race_penalty_retains_official_order_on_exact_tie() -> None:
    results = pd.DataFrame(
        {
            "driver_number": [1, 16, 63],
            "finish_position": [1, 2, 3],
            "laps_completed": [50, 50, 50],
            "classification_gap_seconds": [0.0, 10.0, 15.0],
        }
    )

    impact = remove_post_race_time_penalty(results, 63, 5)

    assert impact.counterfactual_finish_position == 3
    assert impact.passed_driver_numbers == []


def test_remove_post_race_penalty_rejects_nonmonotonic_same_lap_gaps() -> None:
    results = pd.DataFrame(
        {
            "driver_number": [1, 16, 63],
            "finish_position": [1, 2, 3],
            "laps_completed": [50, 50, 50],
            "classification_gap_seconds": [0.0, 12.0, 11.0],
        }
    )

    with pytest.raises(ValueError, match="classification gaps"):
        remove_post_race_time_penalty(results, 63, 5)


@pytest.mark.parametrize(
    ("season", "session_type", "position", "expected"),
    [
        (2018, "Race", 10, 1),
        (2025, "Race", 11, 0),
        (2021, "Sprint", 3, 1),
        (2021, "Sprint", 4, 0),
        (2022, "Sprint", 1, 8),
        (2025, "Sprint", 8, 1),
    ],
)
def test_standard_position_points(
    season: int,
    session_type: str,
    position: int,
    expected: float,
) -> None:
    assert standard_position_points(season, session_type, position) == expected


def test_grid_displacement_distinguishes_exact_saturation_and_confounding() -> None:
    exact = calculate_grid_displacement(7, 10, 3)
    saturated = calculate_grid_displacement(19, 20, 3)
    confounded = calculate_grid_displacement(7, 9, 3)
    gained = calculate_grid_displacement(7, 6, 3)

    assert exact.attribution_status == "mechanical_exact_nominal"
    assert exact.realized_grid_places_lost == 3
    assert saturated.attribution_status == "mechanical_grid_saturation"
    assert saturated.maximum_nominal_loss_with_grid_saturation == 1
    assert confounded.attribution_status == "confounded_grid_reordering"
    assert gained.attribution_status == "confounded_position_gain"
    assert exact.finish_effect_status == "not_estimable_from_grid_displacement"
