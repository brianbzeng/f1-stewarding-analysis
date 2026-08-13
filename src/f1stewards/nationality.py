"""Sourced driver-nationality and event-country dimensions for adjusted analyses."""

from __future__ import annotations

import re
from pathlib import Path

import duckdb
import pandas as pd

from f1stewards.config import PROJECT_ROOT

DRIVER_REGISTRY_PATH = PROJECT_ROOT / "config" / "driver_nationality_registry.csv"
EVENT_COUNTRY_PATH = PROJECT_ROOT / "config" / "event_country_crosswalk.csv"

DRIVER_REGISTRY_COLUMNS = [
    "driver_id",
    "abbreviation",
    "permanent_number",
    "full_name",
    "f1_country_code",
    "nationality",
    "is_british",
    "source_type",
    "source_url",
    "source_note",
]

EVENT_COUNTRY_COLUMNS = [
    "event_country_label",
    "f1_country_code",
    "source_type",
    "source_url",
    "source_note",
]

COUNTRY_CODE_PATTERN = re.compile(r"[A-Z]{3}")
DRIVER_ID_PATTERN = re.compile(r"[a-z][a-z0-9_]*")
ABBREVIATION_PATTERN = re.compile(r"[A-Z]{3}")


def _read_csv(path: Path, columns: list[str]) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    if list(frame.columns) != columns:
        raise ValueError(f"Unexpected columns in {path.name}")
    if frame.empty:
        raise ValueError(f"{path.name} cannot be empty")
    if frame.eq("").any().any():
        empty_columns = ", ".join(frame.columns[frame.eq("").any()])
        raise ValueError(f"{path.name} contains empty values in: {empty_columns}")
    return frame


def load_driver_nationality_registry(path: Path = DRIVER_REGISTRY_PATH) -> pd.DataFrame:
    """Load the stable F1-identity registry and reject ambiguous or unsourced rows."""

    frame = _read_csv(path, DRIVER_REGISTRY_COLUMNS)
    for key in ("driver_id", "abbreviation"):
        if frame[key].duplicated().any():
            raise ValueError(f"Duplicate {key} in {path.name}")
    if not frame["driver_id"].map(lambda value: bool(DRIVER_ID_PATTERN.fullmatch(value))).all():
        raise ValueError("driver_id values must be lowercase stable identifiers")
    if not frame["abbreviation"].map(
        lambda value: bool(ABBREVIATION_PATTERN.fullmatch(value))
    ).all():
        raise ValueError("abbreviation values must be three uppercase letters")
    if not frame["f1_country_code"].map(
        lambda value: bool(COUNTRY_CODE_PATTERN.fullmatch(value))
    ).all():
        raise ValueError("f1_country_code values must be three uppercase letters")
    if not frame["source_url"].str.startswith("https://").all():
        raise ValueError("Every driver nationality source must be an HTTPS URL")
    parsed_british = frame["is_british"].str.casefold().map({"true": True, "false": False})
    if parsed_british.isna().any():
        raise ValueError("is_british values must be True or False")
    if not parsed_british.eq(frame["f1_country_code"].eq("GBR")).all():
        raise ValueError("is_british must agree exactly with f1_country_code=GBR")
    numbers = pd.to_numeric(frame["permanent_number"], errors="coerce")
    if numbers.isna().any() or not numbers.between(1, 99).all():
        raise ValueError("permanent_number must be between 1 and 99")
    loaded = frame.copy()
    loaded["permanent_number"] = numbers.astype("int64")
    loaded["is_british"] = parsed_british.astype(bool)
    return loaded


def load_event_country_crosswalk(path: Path = EVENT_COUNTRY_PATH) -> pd.DataFrame:
    """Load controlled event-country labels in the same code vocabulary as drivers."""

    frame = _read_csv(path, EVENT_COUNTRY_COLUMNS)
    if frame["event_country_label"].duplicated().any():
        raise ValueError(f"Duplicate event_country_label in {path.name}")
    if not frame["f1_country_code"].map(
        lambda value: bool(COUNTRY_CODE_PATTERN.fullmatch(value))
    ).all():
        raise ValueError("Event f1_country_code values must be three uppercase letters")
    if not frame["source_url"].str.startswith("https://").all():
        raise ValueError("Every event-country source must be an HTTPS URL")
    return frame


def replace_nationality_registries(
    connection: duckdb.DuckDBPyConnection,
    drivers: pd.DataFrame,
    event_countries: pd.DataFrame,
) -> tuple[int, int]:
    """Replace controlled registry metadata and upsert the curated driver dimension."""

    connection.register("driver_nationality_batch", drivers)
    connection.register("event_country_batch", event_countries)
    try:
        connection.execute("BEGIN TRANSACTION")
        connection.execute("DELETE FROM metadata.driver_nationality_registry")
        connection.execute(
            """
            INSERT INTO metadata.driver_nationality_registry BY NAME
            SELECT * FROM driver_nationality_batch
            """
        )
        connection.execute("DELETE FROM metadata.event_country_crosswalk")
        connection.execute(
            """
            INSERT INTO metadata.event_country_crosswalk BY NAME
            SELECT * FROM event_country_batch
            """
        )
        connection.execute(
            """
            INSERT INTO curated.drivers (
                driver_id,
                permanent_number,
                full_name,
                nationality,
                nationality_source_url,
                valid_from,
                valid_to
            )
            SELECT
                driver_id,
                permanent_number,
                full_name,
                nationality,
                source_url,
                DATE '2018-01-01',
                DATE '2025-12-31'
            FROM driver_nationality_batch
            ON CONFLICT (driver_id) DO UPDATE SET
                permanent_number = EXCLUDED.permanent_number,
                full_name = EXCLUDED.full_name,
                nationality = EXCLUDED.nationality,
                nationality_source_url = EXCLUDED.nationality_source_url,
                valid_from = EXCLUDED.valid_from,
                valid_to = EXCLUDED.valid_to
            """
        )
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise
    finally:
        connection.unregister("driver_nationality_batch")
        connection.unregister("event_country_batch")
    return len(drivers), len(event_countries)


def nationality_audit(connection: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Return fail-fast identity, source, conflict, and event-country controls."""

    controls = connection.sql(
        """
        WITH metrics AS (
            SELECT
                (SELECT count(*) FROM metadata.driver_nationality_registry)
                    AS driver_registry_rows,
                (SELECT count(*) FROM metadata.event_country_crosswalk)
                    AS event_country_rows,
                (SELECT count(*) FROM raw.fastf1_session_results)
                    AS classification_rows,
                (SELECT count(*) FROM analysis.v_fastf1_driver_identity
                    WHERE driver_id IS NULL) AS missing_driver_registry_rows,
                (SELECT count(*) FROM analysis.v_fastf1_driver_identity
                    WHERE nationality_match_status = 'observed_conflict')
                    AS observed_country_conflicts,
                (SELECT count(*) FROM analysis.v_event_country_identity
                    WHERE event_country_match_status <> 'matched')
                    AS unmatched_event_countries,
                (SELECT count(*) FROM metadata.driver_nationality_registry
                    WHERE source_url NOT LIKE 'https://%'
                       OR source_type IS NULL
                       OR source_note IS NULL)
                    AS unsourced_driver_rows
        )
        SELECT 'driver_registry_nonempty' AS control,
               CASE WHEN driver_registry_rows > 0 THEN 'pass' ELSE 'fail' END AS status,
               driver_registry_rows AS observed,
               '> 0' AS expected
        FROM metrics
        UNION ALL
        SELECT 'event_country_crosswalk_nonempty',
               CASE WHEN event_country_rows > 0 THEN 'pass' ELSE 'fail' END,
               event_country_rows,
               '> 0'
        FROM metrics
        UNION ALL
        SELECT 'fastf1_driver_identity_complete',
               CASE WHEN missing_driver_registry_rows = 0 THEN 'pass' ELSE 'fail' END,
               missing_driver_registry_rows,
               '0'
        FROM metrics
        UNION ALL
        SELECT 'fastf1_country_code_conflicts',
               CASE WHEN observed_country_conflicts = 0 THEN 'pass' ELSE 'fail' END,
               observed_country_conflicts,
               '0'
        FROM metrics
        UNION ALL
        SELECT 'event_country_crosswalk_complete',
               CASE WHEN unmatched_event_countries = 0 THEN 'pass' ELSE 'fail' END,
               unmatched_event_countries,
               '0'
        FROM metrics
        UNION ALL
        SELECT 'driver_registry_sources_complete',
               CASE WHEN unsourced_driver_rows = 0 THEN 'pass' ELSE 'fail' END,
               unsourced_driver_rows,
               '0'
        FROM metrics
        UNION ALL
        SELECT 'fastf1_classification_population',
               CASE WHEN classification_rows > 0 THEN 'pass' ELSE 'fail' END,
               classification_rows,
               '> 0'
        FROM metrics
        """
    ).df()
    return controls
