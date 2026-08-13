"""Normalized pilot enrichment from FastF1's public timing-data interface."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import fastf1
import pandas as pd

from f1stewards.models import PilotEvent

SESSION_CODES = {"Race": "R", "Sprint": "S"}


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
            "pit_in_time_seconds": _seconds(frame, "PitInTime"),
            "pit_out_time_seconds": _seconds(frame, "PitOutTime"),
            "position": _numeric(frame, "Position"),
            "compound": _column(frame, "Compound"),
            "stint": _numeric(frame, "Stint"),
            "tyre_life": _numeric(frame, "TyreLife"),
            "fresh_tyre": _column(frame, "FreshTyre"),
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


def _add_session_type(frame: pd.DataFrame, session_type: str) -> pd.DataFrame:
    enriched = frame.copy()
    enriched.insert(1, "session_type", session_type)
    return enriched


def add_lap_timestamp_lineage(
    frame: pd.DataFrame, session_date: datetime | pd.Timestamp | None
) -> pd.DataFrame:
    """Fill missing absolute lap starts from FastF1's UTC session anchor with lineage."""

    enriched = frame.copy()
    timestamps = pd.to_datetime(enriched["lap_start_timestamp"], errors="coerce", utc=True)
    direct = timestamps.notna()
    derived = pd.Series(False, index=enriched.index, dtype="bool")
    if session_date is not None and not pd.isna(session_date):
        anchor = pd.Timestamp(session_date)
        anchor = anchor.tz_localize("UTC") if anchor.tzinfo is None else anchor.tz_convert("UTC")
        relative = pd.to_timedelta(enriched["lap_start_time_seconds"], unit="s", errors="coerce")
        derived = timestamps.isna() & relative.notna()
        timestamps.loc[derived] = anchor + relative.loc[derived]
    basis = pd.Series("unavailable", index=enriched.index, dtype="object")
    basis.loc[direct] = "fastf1_lap_start_date"
    basis.loc[derived] = "session_date_plus_lap_start_time"
    enriched["lap_start_timestamp"] = timestamps
    enriched["lap_start_timestamp_basis"] = basis
    enriched["lap_start_timestamp_is_derived"] = derived
    return enriched


def fetch_study_session(
    event: PilotEvent,
    session_type: str,
    cache_dir: Path,
    output_root: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Fetch one Race or Sprint into session-keyed normalized Parquet tables."""

    if session_type not in SESSION_CODES:
        raise ValueError(f"Unsupported FastF1 study session: {session_type}")
    cache_dir.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(cache_dir))
    session = fastf1.get_session(event.season, event.event_name, SESSION_CODES[session_type])
    session.load(laps=True, telemetry=True, weather=False, messages=True)
    retrieved_at = datetime.now(UTC)
    results = _add_session_type(
        normalize_results(pd.DataFrame(session.results), event.pilot_id, retrieved_at),
        session_type,
    )
    laps = normalize_laps(pd.DataFrame(session.laps), event.pilot_id, retrieved_at)
    laps = add_lap_timestamp_lineage(laps, session.date)
    laps = _add_session_type(laps, session_type)
    messages = _add_session_type(
        normalize_messages(
            pd.DataFrame(session.race_control_messages), event.pilot_id, retrieved_at
        ),
        session_type,
    )

    output_dir = (
        output_root
        / str(event.season)
        / _safe_event_slug(event)
        / session_type.casefold()
    )
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


def upsert_session_ingestion(
    connection: duckdb.DuckDBPyConnection,
    event_id: str,
    session_type: str,
    status: str,
    started_at: datetime,
    *,
    finished_at: datetime | None = None,
    result_rows: int | None = None,
    lap_rows: int | None = None,
    message_rows: int | None = None,
    direct_lap_timestamp_rows: int | None = None,
    derived_lap_timestamp_rows: int | None = None,
    missing_lap_timestamp_rows: int | None = None,
    error_message: str | None = None,
) -> None:
    """Record resumable FastF1 session ingestion state."""

    if session_type not in SESSION_CODES:
        raise ValueError(f"Unsupported FastF1 study session: {session_type}")
    if status not in {"running", "succeeded", "failed"}:
        raise ValueError(f"Unsupported FastF1 ingestion status: {status}")
    connection.execute(
        """
        INSERT INTO metadata.fastf1_session_ingestion (
            event_id, session_type, status, started_at, finished_at, fastf1_version,
            result_rows, lap_rows, message_rows, direct_lap_timestamp_rows,
            derived_lap_timestamp_rows, missing_lap_timestamp_rows, error_message
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (event_id, session_type) DO UPDATE SET
            status = EXCLUDED.status,
            started_at = EXCLUDED.started_at,
            finished_at = EXCLUDED.finished_at,
            fastf1_version = EXCLUDED.fastf1_version,
            result_rows = EXCLUDED.result_rows,
            lap_rows = EXCLUDED.lap_rows,
            message_rows = EXCLUDED.message_rows,
            direct_lap_timestamp_rows = EXCLUDED.direct_lap_timestamp_rows,
            derived_lap_timestamp_rows = EXCLUDED.derived_lap_timestamp_rows,
            missing_lap_timestamp_rows = EXCLUDED.missing_lap_timestamp_rows,
            error_message = EXCLUDED.error_message
        """,
        [
            event_id,
            session_type,
            status,
            started_at,
            finished_at,
            fastf1.__version__,
            result_rows,
            lap_rows,
            message_rows,
            direct_lap_timestamp_rows,
            derived_lap_timestamp_rows,
            missing_lap_timestamp_rows,
            error_message,
        ],
    )


def replace_session_enrichment(
    connection: duckdb.DuckDBPyConnection,
    event_id: str,
    session_type: str,
    results: pd.DataFrame,
    laps: pd.DataFrame,
    messages: pd.DataFrame,
    started_at: datetime,
) -> None:
    """Atomically replace one session and mark its resumable ingestion as succeeded."""

    if session_type not in SESSION_CODES:
        raise ValueError(f"Unsupported FastF1 study session: {session_type}")
    expected = {
        "raw.fastf1_session_results": results,
        "raw.fastf1_session_laps": laps,
        "raw.fastf1_session_race_control_messages": messages,
    }
    for table, frame in expected.items():
        if frame.empty and table != "raw.fastf1_session_race_control_messages":
            raise ValueError(f"{table} cannot be empty for a successful session load")
        if frame.empty:
            continue
        if set(frame.get("event_id", [])) != {event_id}:
            raise ValueError(f"{table} event IDs do not match {event_id}")
        if set(frame.get("session_type", [])) != {session_type}:
            raise ValueError(f"{table} session types do not match {session_type}")

    connection.execute("BEGIN TRANSACTION")
    try:
        for table, frame in expected.items():
            connection.execute(
                f"DELETE FROM {table} WHERE event_id = ? AND session_type = ?",
                [event_id, session_type],
            )
            if not frame.empty:
                connection.register("session_enrichment_batch", frame)
                connection.execute(
                    f"INSERT INTO {table} BY NAME SELECT * FROM session_enrichment_batch"
                )
                connection.unregister("session_enrichment_batch")
        timestamp_basis = laps["lap_start_timestamp_basis"].value_counts()
        upsert_session_ingestion(
            connection,
            event_id,
            session_type,
            "succeeded",
            started_at,
            finished_at=datetime.now(UTC),
            result_rows=len(results),
            lap_rows=len(laps),
            message_rows=len(messages),
            direct_lap_timestamp_rows=int(timestamp_basis.get("fastf1_lap_start_date", 0)),
            derived_lap_timestamp_rows=int(
                timestamp_basis.get("session_date_plus_lap_start_time", 0)
            ),
            missing_lap_timestamp_rows=int(timestamp_basis.get("unavailable", 0)),
        )
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise
