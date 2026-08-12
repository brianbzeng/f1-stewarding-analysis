from pathlib import Path

import duckdb

from f1stewards.config import (
    PROJECT_ROOT,
    load_pilot_events,
    load_regulatory_sources,
    load_sporting_regulation_issues,
)
from f1stewards.warehouse import (
    initialize_database,
    replace_claim_ledger,
    replace_sporting_regulation_issues,
    upsert_pilot_events,
    upsert_regulatory_sources,
)


def test_schema_and_pilot_upsert(tmp_path: Path) -> None:
    db_path = tmp_path / "test.duckdb"
    initialize_database(db_path)
    with duckdb.connect(str(db_path)) as connection:
        upsert_pilot_events(connection, load_pilot_events())
        upsert_pilot_events(connection, load_pilot_events())
        upsert_regulatory_sources(connection, load_regulatory_sources())
        upsert_regulatory_sources(connection, load_regulatory_sources())
        issue_count = replace_sporting_regulation_issues(
            connection, load_sporting_regulation_issues()
        )
        claim_count = replace_claim_ledger(connection)
        count = connection.sql("SELECT count(*) FROM metadata.events").fetchone()[0]
        source_count = connection.sql(
            "SELECT count(*) FROM metadata.regulatory_sources"
        ).fetchone()[0]
        link_count = connection.sql(
            "SELECT count(*) FROM metadata.event_regulatory_sources"
        ).fetchone()[0]
        view_count = connection.sql(
            "SELECT count(*) FROM information_schema.views "
            "WHERE table_name = 'v_primary_adjudications'"
        ).fetchone()[0]
        selected = connection.sql(
            """
            SELECT event_id, source_id
            FROM analysis.v_event_sporting_regulation_selection
            ORDER BY event_id
            """
        ).fetchall()
    assert count == 3
    assert source_count == 11
    assert link_count == 11
    assert claim_count == 12
    assert issue_count == 65
    assert selected == [
        ("2019-aut", "fia-f1sr-2019-03"),
        ("2023-abu", "fia-f1sr-2023-07"),
        ("2025-aut", "fia-f1sr-2025-05"),
    ]
    assert view_count == 1
    assert (PROJECT_ROOT / "sql" / "quality_checks.sql").exists()
