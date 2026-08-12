import re

import duckdb

from f1stewards.config import PROJECT_ROOT
from f1stewards.snowflake import (
    TABLE_NAMES,
    build_snowflake_frames,
    export_snowflake_pilot,
    validate_snowflake_export,
)
from f1stewards.warehouse import initialize_database


def manual_paths() -> tuple:
    root = PROJECT_ROOT / "data" / "manual"
    return (
        root / "pilot_coded_adjudications.csv",
        root / "pilot_impact_assessments.csv",
        root / "pilot_independent_review.csv",
    )


def test_snowflake_export_is_content_addressed_and_locally_validated(tmp_path) -> None:
    db_path = tmp_path / "pilot.duckdb"
    initialize_database(db_path)
    coding_path, impact_path, review_path = manual_paths()

    with duckdb.connect(str(db_path), read_only=True) as connection:
        first = export_snowflake_pilot(
            connection,
            PROJECT_ROOT,
            tmp_path / "exports",
            coding_path,
            impact_path,
            review_path,
        )
        second = export_snowflake_pilot(
            connection,
            PROJECT_ROOT,
            tmp_path / "exports",
            coding_path,
            impact_path,
            review_path,
        )

    validation = validate_snowflake_export(first.output_directory)
    assert first.created is True
    assert second.created is False
    assert second.export_id == first.export_id
    assert first.manifest["release_status"] == "provisional"
    assert first.manifest["table_count"] == len(TABLE_NAMES) == 12
    assert validation.status.eq("pass").all()
    assert first.manifest["tables"]["curated_adjudications"]["row_count"] == 9
    assert first.manifest["tables"]["curated_impact_assessments"]["row_count"] == 4
    assert first.manifest["tables"]["audit_independent_review"]["row_count"] == 13


def test_export_omits_machine_specific_source_path(tmp_path) -> None:
    db_path = tmp_path / "pilot.duckdb"
    initialize_database(db_path)
    coding_path, impact_path, review_path = manual_paths()

    with duckdb.connect(str(db_path), read_only=True) as connection:
        frames = build_snowflake_frames(
            connection, coding_path, impact_path, review_path
        )

    assert "local_path" not in frames["raw_source_documents"].columns

    ddl = (PROJECT_ROOT / "snowflake" / "01_tables.sql").read_text(encoding="utf-8")
    for export_name, table_name in TABLE_NAMES.items():
        match = re.search(
            rf"CREATE TABLE IF NOT EXISTS {re.escape(table_name)}\s*\((.*?)\);",
            ddl,
            re.IGNORECASE | re.DOTALL,
        )
        assert match is not None
        ddl_columns = [
            line.strip().split()[0].rstrip(",")
            for line in match.group(1).splitlines()
            if line.strip() and not line.strip().upper().startswith("PRIMARY KEY")
        ]
        assert ddl_columns == [column.upper() for column in frames[export_name].columns]


def test_validation_detects_tampered_parquet(tmp_path) -> None:
    db_path = tmp_path / "pilot.duckdb"
    initialize_database(db_path)
    coding_path, impact_path, review_path = manual_paths()
    with duckdb.connect(str(db_path), read_only=True) as connection:
        result = export_snowflake_pilot(
            connection,
            PROJECT_ROOT,
            tmp_path / "exports",
            coding_path,
            impact_path,
            review_path,
        )

    target = result.output_directory / "curated_adjudications.parquet"
    target.write_bytes(target.read_bytes() + b"tampered")
    validation = validate_snowflake_export(result.output_directory)

    row = validation.loc[validation.export_name.eq("curated_adjudications")].iloc[0]
    assert not row.hash_match
    assert row.status == "fail"
