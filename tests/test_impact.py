import pandas as pd
import pytest

from f1stewards.impact import remove_post_race_time_penalty


def test_remove_post_race_penalty_reorders_same_lap_finishers() -> None:
    results = pd.DataFrame(
        {
            "driver_number": [1, 16, 63, 11, 4],
            "finish_position": [1, 2, 3, 4, 5],
            "laps_completed": [58, 58, 58, 58, 58],
            "classification_gap_seconds": [0.0, 17.993, 20.328, 21.453, 24.284],
        }
    )

    impact = remove_post_race_time_penalty(results, 11, 5)

    assert impact.counterfactual_finish_position == 2
    assert impact.positions_gained_without_penalty == 2
    assert impact.passed_driver_numbers == [16, 63]
    assert impact.counterfactual_gap_seconds == pytest.approx(16.453)


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
