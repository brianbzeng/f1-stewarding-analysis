from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from f1stewards.enrichment.fastf1 import (
    add_lap_timestamp_lineage,
    normalize_laps,
    normalize_messages,
    normalize_results,
    replace_session_enrichment,
)
from f1stewards.warehouse import initialize_database

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
    laps = add_lap_timestamp_lineage(laps, pd.Timestamp("2025-01-01T12:00:00Z"))
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


def session_frames(
    event_id: str, session_type: str
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    results = normalize_results(
        pd.DataFrame(
            {
                "DriverNumber": ["22"],
                "FullName": ["Yuki Tsunoda"],
                "Position": [1.0],
                "Laps": [3.0],
                "Time": [pd.to_timedelta(360.0, unit="s")],
                "Points": [8.0],
            }
        ),
        event_id,
        RETRIEVED_AT,
    )
    laps = normalize_laps(
        pd.DataFrame(
            {
                "DriverNumber": ["22"],
                "LapNumber": [1.0],
                "LapTime": [pd.to_timedelta(90.0, unit="s")],
                "LapStartTime": [pd.to_timedelta(10.0, unit="s")],
            }
        ),
        event_id,
        RETRIEVED_AT,
    )
    laps = add_lap_timestamp_lineage(laps, pd.Timestamp("2025-01-01T12:00:00Z"))
    messages = normalize_messages(
        pd.DataFrame(
            {"Time": [pd.to_timedelta(10.0, unit="s")], "Message": ["GREEN LIGHT"]}
        ),
        event_id,
        RETRIEVED_AT,
    )
    for frame in (results, laps, messages):
        frame.insert(1, "session_type", session_type)
    return results, laps, messages


def test_session_keyed_enrichment_keeps_race_and_sprint_separate(tmp_path: Path) -> None:
    db_path = tmp_path / "sessions.duckdb"
    initialize_database(db_path)
    race = session_frames("2025-tst", "Race")
    sprint = session_frames("2025-tst", "Sprint")

    with duckdb.connect(str(db_path)) as connection:
        replace_session_enrichment(
            connection, "2025-tst", "Race", *race, RETRIEVED_AT
        )
        replace_session_enrichment(
            connection, "2025-tst", "Sprint", *sprint, RETRIEVED_AT
        )
        counts = connection.sql(
            """
            SELECT session_type, count(*) AS rows
            FROM raw.fastf1_session_results
            GROUP BY session_type
            ORDER BY session_type
            """
        ).fetchall()
        statuses = connection.sql(
            """
            SELECT session_type, status, result_rows, lap_rows, message_rows,
                   direct_lap_timestamp_rows, derived_lap_timestamp_rows,
                   missing_lap_timestamp_rows
            FROM metadata.fastf1_session_ingestion
            ORDER BY session_type
            """
        ).fetchall()

    assert counts == [("Race", 1), ("Sprint", 1)]
    assert statuses == [
        ("Race", "succeeded", 1, 1, 1, 0, 1, 0),
        ("Sprint", "succeeded", 1, 1, 1, 0, 1, 0),
    ]


def test_missing_absolute_lap_start_uses_utc_session_anchor() -> None:
    laps = normalize_laps(
        pd.DataFrame(
            {
                "DriverNumber": ["22"],
                "LapNumber": [1.0],
                "LapStartTime": [pd.to_timedelta(427.988, unit="s")],
            }
        ),
        "2018-aus",
        RETRIEVED_AT,
    )
    enriched = add_lap_timestamp_lineage(laps, pd.Timestamp("2018-03-25T05:10:00"))

    assert enriched.loc[0, "lap_start_timestamp"] == pd.Timestamp(
        "2018-03-25T05:17:07.988Z"
    )
    assert enriched.loc[0, "lap_start_timestamp_basis"] == (
        "session_date_plus_lap_start_time"
    )
    assert bool(enriched.loc[0, "lap_start_timestamp_is_derived"])


def test_session_enrichment_rejects_cross_session_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "mismatch.duckdb"
    initialize_database(db_path)
    race = session_frames("2025-tst", "Race")

    with duckdb.connect(str(db_path)) as connection:
        with pytest.raises(ValueError, match="session types do not match"):
            replace_session_enrichment(
                connection, "2025-tst", "Sprint", *race, RETRIEVED_AT
            )
        assert connection.sql(
            "SELECT count(*) FROM raw.fastf1_session_results"
        ).fetchone()[0] == 0
