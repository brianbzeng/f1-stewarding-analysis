import pandas as pd

from f1stewards.incident_clock import map_local_clock_to_laps


def _laps() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "lap_number": [1, 2, 3],
            "lap_start_timestamp": [
                "2024-05-05T13:00:00Z",
                "2024-05-05T13:01:30Z",
                "2024-05-05T13:03:00Z",
            ],
            "lap_time_seconds": [90.0, 90.0, 90.0],
        }
    )


def test_minute_clock_preserves_two_lap_uncertainty() -> None:
    mapped = map_local_clock_to_laps(_laps(), "15:01", "+02:00")

    assert mapped is not None
    assert mapped.possible_laps == (1, 2)
    assert mapped.mapping_basis == "fia_clock_lap_interval"


def test_second_clock_can_resolve_one_lap() -> None:
    mapped = map_local_clock_to_laps(_laps(), "15:01:45", "+02:00")

    assert mapped is not None
    assert mapped.possible_laps == (2,)


def test_start_clock_tolerance_recovers_lap_one() -> None:
    mapped = map_local_clock_to_laps(_laps(), "14:56", "+02:00")

    assert mapped is not None
    assert mapped.possible_laps == (1,)
    assert mapped.mapping_basis == "fia_clock_pre_start_first_lap_tolerance"
