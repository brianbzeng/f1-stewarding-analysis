import pandas as pd

from f1stewards.study_v2_layers import (
    build_sanction_layer,
    estimate_reference_adjusted_pace,
)


def _laps(offset_before: float, offset_after: float) -> pd.DataFrame:
    rows = []
    for lap in range(2, 18):
        offset = offset_before if lap < 10 else offset_after
        rows.append(
            {
                "lap_number": lap,
                "lap_time_seconds": 90.0 + lap * 0.02 + offset,
                "track_status": "1",
                "is_accurate": True,
                "pit_in_time_seconds": None,
                "pit_out_time_seconds": None,
                "compound": "MEDIUM",
                "tyre_life": lap,
            }
        )
    return pd.DataFrame(rows)


def test_reference_adjusted_pace_recovers_relative_change() -> None:
    result = estimate_reference_adjusted_pace(_laps(0.2, 0.7), _laps(0.0, 0.0), 10)

    assert result["pace_screen_status"].startswith("estimable")
    assert result["matched_laps_before"] >= 5
    assert result["matched_laps_after"] >= 5
    assert abs(result["pace_change_seconds_per_lap"] - 0.5) < 1e-9


def test_sanction_layer_does_not_treat_nominal_seconds_as_realized_cost() -> None:
    conduct = pd.DataFrame(
        [
            {
                "adjudication_instance_id": "a",
                "adjudication_id_final": "a",
                "incident_id_final": "i",
                "document_id": "d",
                "event_id": "2024-mia",
                "season": 2024,
                "session_type_final": "Race",
                "accused_driver_number_final": 55,
                "outcome_family_final": "time_penalty",
                "penalty_seconds_final": 5,
                "penalty_points_final": 1,
                "grid_places_final": "",
                "review_status": "model_reviewed_agree",
            }
        ]
    )

    layer = build_sanction_layer(conduct)

    assert layer.loc[0, "realized_seconds"] == ""
    assert layer.loc[0, "realized_burden_status"].startswith("application_timing_required")
