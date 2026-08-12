"""Normalized pilot enrichment from FastF1's public timing-data interface."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import fastf1
import pandas as pd

from f1stewards.models import PilotEvent


def _column(frame: pd.DataFrame, name: str, default: object = pd.NA) -> pd.Series:
    if name in frame.columns:
        return frame[name]
    return pd.Series(default, index=frame.index, dtype="object")


def _numeric(frame: pd.DataFrame, name: str) -> pd.Series:
    return pd.to_numeric(_column(frame, name), errors="coerce")


def _seconds(frame: pd.DataFrame, name: str) -> pd.Series:
    values = _column(frame, name)
    if pd.api.types.is_timedelta64_dtype(values.dtype):
        return values.dt.total_seconds()
    if pd.api.types.is_datetime64_any_dtype(values.dtype):
        return pd.Series(float("nan"), index=frame.index, dtype="float64")
    return pd.to_timedelta(values, errors="coerce").dt.total_seconds()


def _timestamp(frame: pd.DataFrame, name: str) -> pd.Series:
    return pd.to_datetime(_column(frame, name), errors="coerce", utc=True)


def normalize_results(frame: pd.DataFrame, event_id: str, retrieved_at: datetime) -> pd.DataFrame:
    finish_position = _numeric(frame, "Position")
    result_time_seconds = _seconds(frame, "Time")
    return pd.DataFrame(
        {
            "event_id": event_id,
            "driver_number": _numeric(frame, "DriverNumber"),
            "driver_name": _column(frame, "FullName"),
            "abbreviation": _column(frame, "Abbreviation"),
            "country_code": _column(frame, "CountryCode"),
            "team_name": _column(frame, "TeamName"),
            "grid_position": _numeric(frame, "GridPosition"),
            "finish_position": finish_position,
            "classified_position": _column(frame, "ClassifiedPosition"),
            "laps_completed": _numeric(frame, "Laps"),
            "result_time_seconds": result_time_seconds,
            "classification_gap_seconds": result_time_seconds.where(
                finish_position.ne(1), 0.0
            ),
            "status": _column(frame, "Status"),
            "points": _numeric(frame, "Points"),
            "retrieved_at": retrieved_at,
        }
    )


def normalize_laps(frame: pd.DataFrame, event_id: str, retrieved_at: datetime) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "event_id": event_id,
            "driver_number": _numeric(frame, "DriverNumber"),
            "lap_number": _numeric(frame, "LapNumber"),
            "lap_time_seconds": _seconds(frame, "LapTime"),
            "lap_start_time_seconds": _seconds(frame, "LapStartTime"),
            "lap_start_timestamp": _timestamp(frame, "LapStartDate"),
            "position": _numeric(frame, "Position"),
            "compound": _column(frame, "Compound"),
            "stint": _numeric(frame, "Stint"),
            "track_status": _column(frame, "TrackStatus"),
            "is_accurate": _column(frame, "IsAccurate"),
            "retrieved_at": retrieved_at,
        }
    )


def normalize_messages(frame: pd.DataFrame, event_id: str, retrieved_at: datetime) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "event_id": event_id,
            "message_timestamp": _timestamp(frame, "Time"),
            "message_time_seconds": _seconds(frame, "Time"),
            "category": _column(frame, "Category"),
            "message": _column(frame, "Message"),
            "status": _column(frame, "Status"),
            "flag": _column(frame, "Flag"),
            "scope": _column(frame, "Scope"),
            "sector": _numeric(frame, "Sector"),
            "racing_number": _numeric(frame, "RacingNumber"),
            "lap_number": _numeric(frame, "Lap"),
            "retrieved_at": retrieved_at,
        }
    )


def _safe_event_slug(event: PilotEvent) -> str:
    return re.sub(r"[^a-z0-9]+", "-", event.event_name.casefold()).strip("-")


def fetch_pilot_race(
    event: PilotEvent,
    cache_dir: Path,
    output_root: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Fetch one Race session, save normalized Parquet, and return its three tables."""

    cache_dir.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(cache_dir))
    session = fastf1.get_session(event.season, event.event_name, "R")
    # Telemetry loading is required for FastF1 to calculate the session's absolute
    # time-zero and populate LapStartDate. Raw car/position streams remain cached only;
    # the warehouse stores the much smaller normalized lap table.
    session.load(laps=True, telemetry=True, weather=False, messages=True)
    retrieved_at = datetime.now(UTC)

    results = normalize_results(pd.DataFrame(session.results), event.pilot_id, retrieved_at)
    laps = normalize_laps(pd.DataFrame(session.laps), event.pilot_id, retrieved_at)
    messages = normalize_messages(
        pd.DataFrame(session.race_control_messages), event.pilot_id, retrieved_at
    )

    output_dir = output_root / str(event.season) / _safe_event_slug(event)
    output_dir.mkdir(parents=True, exist_ok=True)
    results.to_parquet(output_dir / "results.parquet", index=False)
    laps.to_parquet(output_dir / "laps.parquet", index=False)
    messages.to_parquet(output_dir / "race_control_messages.parquet", index=False)
    return results, laps, messages


def replace_event_enrichment(
    connection: duckdb.DuckDBPyConnection,
    event_id: str,
    results: pd.DataFrame,
    laps: pd.DataFrame,
    messages: pd.DataFrame,
) -> None:
    batches = {
        "raw.fastf1_results": results,
        "raw.fastf1_laps": laps,
        "raw.fastf1_race_control_messages": messages,
    }
    connection.execute("BEGIN TRANSACTION")
    try:
        for table, frame in batches.items():
            connection.execute(f"DELETE FROM {table} WHERE event_id = ?", [event_id])
            connection.register("enrichment_batch", frame)
            connection.execute(f"INSERT INTO {table} BY NAME SELECT * FROM enrichment_batch")
            connection.unregister("enrichment_batch")
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise
