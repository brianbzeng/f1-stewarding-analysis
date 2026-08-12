from datetime import UTC, datetime

import pandas as pd

from f1stewards.enrichment.fastf1 import normalize_laps, normalize_messages, normalize_results

RETRIEVED_AT = datetime(2026, 8, 12, tzinfo=UTC)


def test_normalize_results_selects_stable_fields() -> None:
    source = pd.DataFrame(
        {
            "DriverNumber": ["22"],
            "FullName": ["Yuki Tsunoda"],
            "CountryCode": ["JPN"],
            "Position": [16.0],
            "Laps": [68.0],
            "Time": [pd.to_timedelta(2.979, unit="s")],
            "Points": [0.0],
        }
    )
    result = normalize_results(source, "2025-aut", RETRIEVED_AT)
    assert result.loc[0, "driver_number"] == 22
    assert result.loc[0, "finish_position"] == 16
    assert result.loc[0, "laps_completed"] == 68
    assert result.loc[0, "classification_gap_seconds"] == 2.979
    assert result.loc[0, "event_id"] == "2025-aut"


def test_normalize_laps_and_messages_convert_timedeltas_to_seconds() -> None:
    laps = normalize_laps(
        pd.DataFrame(
            {
                "DriverNumber": ["22"],
                "LapNumber": [3.0],
                "LapTime": [pd.to_timedelta(67.5, unit="s")],
                "LapStartTime": [pd.to_timedelta(140.0, unit="s")],
                "PitInTime": [pd.to_timedelta(204.0, unit="s")],
                "PitOutTime": [pd.to_timedelta(232.5, unit="s")],
                "TyreLife": [18.0],
                "FreshTyre": [False],
            }
        ),
        "2025-aut",
        RETRIEVED_AT,
    )
    messages = normalize_messages(
        pd.DataFrame({"Time": [pd.to_timedelta(151.0, unit="s")], "Message": ["TEST"]}),
        "2025-aut",
        RETRIEVED_AT,
    )
    assert laps.loc[0, "lap_time_seconds"] == 67.5
    assert laps.loc[0, "lap_start_time_seconds"] == 140.0
    assert laps.loc[0, "pit_in_time_seconds"] == 204.0
    assert laps.loc[0, "pit_out_time_seconds"] == 232.5
    assert laps.loc[0, "tyre_life"] == 18.0
    assert laps.loc[0, "fresh_tyre"] is False or not laps.loc[0, "fresh_tyre"]
    assert messages.loc[0, "message_time_seconds"] == 151.0


def test_normalize_messages_preserves_absolute_timestamp() -> None:
    source_time = pd.Timestamp("2019-06-30T13:10:00Z")
    messages = normalize_messages(
        pd.DataFrame({"Time": [source_time], "Message": ["TEST"]}),
        "2019-aut",
        RETRIEVED_AT,
    )
    assert messages.loc[0, "message_timestamp"] == source_time
    assert pd.isna(messages.loc[0, "message_time_seconds"])
