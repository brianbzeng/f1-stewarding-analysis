from pathlib import Path

import duckdb
import pandas as pd
import pytest

from f1stewards.config import load_study_events
from f1stewards.nationality import (
    DRIVER_REGISTRY_COLUMNS,
    load_driver_nationality_registry,
    load_event_country_crosswalk,
    nationality_audit,
    replace_nationality_registries,
)
from f1stewards.warehouse import initialize_database, upsert_study_events


def test_controlled_registries_cover_study_population() -> None:
    drivers = load_driver_nationality_registry()
    countries = load_event_country_crosswalk()
    study_country_labels = {event.country for event in load_study_events()}

    assert len(drivers) == 43
    assert len(countries) == 28
    assert study_country_labels <= set(countries["event_country_label"])
    assert drivers["driver_id"].is_unique
    assert drivers["abbreviation"].is_unique
    assert drivers["source_url"].str.startswith("https://").all()
    assert drivers["is_british"].eq(drivers["f1_country_code"].eq("GBR")).all()


def test_driver_registry_rejects_british_flag_mismatch(tmp_path: Path) -> None:
    row = {
        "driver_id": "example",
        "abbreviation": "EXA",
        "permanent_number": "99",
        "full_name": "Example Driver",
        "f1_country_code": "USA",
        "nationality": "American",
        "is_british": "True",
        "source_type": "test_source",
        "source_url": "https://example.com/driver",
        "source_note": "Deliberate invalid test row.",
    }
    path = tmp_path / "drivers.csv"
    pd.DataFrame([row], columns=DRIVER_REGISTRY_COLUMNS).to_csv(path, index=False)

    with pytest.raises(ValueError, match="is_british must agree"):
        load_driver_nationality_registry(path)


def test_registry_load_builds_curated_identity_and_home_race_view(tmp_path: Path) -> None:
    db_path = tmp_path / "nationality.duckdb"
    initialize_database(db_path)
    drivers = load_driver_nationality_registry()
    countries = load_event_country_crosswalk()

    with duckdb.connect(str(db_path)) as connection:
        upsert_study_events(connection, load_study_events())
        counts = replace_nationality_registries(connection, drivers, countries)
        connection.execute(
            """
            INSERT INTO raw.fastf1_session_results (
                event_id,
                session_type,
                driver_number,
                driver_name,
                abbreviation,
                country_code,
                retrieved_at
            ) VALUES
                ('2019-aut', 'Race', 44, 'Lewis Hamilton', 'HAM', 'nan', now()),
                ('2019-gbr', 'Race', 44, 'Lewis Hamilton', 'HAM', 'GBR', now())
            """
        )
        rows = connection.sql(
            """
            SELECT event_id, driver_id, nationality_match_status, home_race_driver
            FROM analysis.v_fastf1_driver_identity
            ORDER BY event_id
            """
        ).fetchall()
        curated_count = connection.sql("SELECT count(*) FROM curated.drivers").fetchone()[0]

    assert counts == (43, 28)
    assert curated_count == 43
    assert rows == [
        ("2019-aut", "ham", "registry_backfill", False),
        ("2019-gbr", "ham", "observed_match", True),
    ]


def test_nationality_audit_fails_observed_conflict(tmp_path: Path) -> None:
    db_path = tmp_path / "conflict.duckdb"
    initialize_database(db_path)

    with duckdb.connect(str(db_path)) as connection:
        upsert_study_events(connection, load_study_events())
        replace_nationality_registries(
            connection,
            load_driver_nationality_registry(),
            load_event_country_crosswalk(),
        )
        connection.execute(
            """
            INSERT INTO raw.fastf1_session_results (
                event_id,
                session_type,
                driver_number,
                driver_name,
                abbreviation,
                country_code,
                retrieved_at
            ) VALUES ('2019-aut', 'Race', 44, 'Lewis Hamilton', 'HAM', 'USA', now())
            """
        )
        controls = nationality_audit(connection).set_index("control")

    assert controls.loc["fastf1_country_code_conflicts", "status"] == "fail"
    assert controls.loc["fastf1_country_code_conflicts", "observed"] == 1
