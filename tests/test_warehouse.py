from pathlib import Path

import duckdb

from f1stewards.config import PROJECT_ROOT, load_pilot_events
from f1stewards.warehouse import initialize_database, upsert_pilot_events


def test_schema_and_pilot_upsert(tmp_path: Path) -> None:
    db_path = tmp_path / "test.duckdb"
    initialize_database(db_path)
    with duckdb.connect(str(db_path)) as connection:
        upsert_pilot_events(connection, load_pilot_events())
        upsert_pilot_events(connection, load_pilot_events())
        count = connection.sql("SELECT count(*) FROM metadata.events").fetchone()[0]
        view_count = connection.sql(
            "SELECT count(*) FROM information_schema.views "
            "WHERE table_name = 'v_primary_adjudications'"
        ).fetchone()[0]
    assert count == 3
    assert view_count == 1
    assert (PROJECT_ROOT / "sql" / "quality_checks.sql").exists()
