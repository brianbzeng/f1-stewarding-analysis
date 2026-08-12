from pathlib import Path

import duckdb

from f1stewards.config import (
    PROJECT_ROOT,
    load_international_sporting_code_issues,
    load_pilot_events,
    load_regulatory_sources,
    load_sporting_regulation_issues,
)
from f1stewards.warehouse import (
    initialize_database,
    replace_claim_ledger,
    replace_international_sporting_code_issues,
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
        code_issue_count = replace_international_sporting_code_issues(
            connection, load_international_sporting_code_issues()
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
        selected_code = connection.sql(
            """
            SELECT event_id, source_id
            FROM analysis.v_event_international_sporting_code_selection
            ORDER BY event_id
            """
        ).fetchall()
    assert count == 3
    assert source_count == 11
    assert link_count == 11
    assert claim_count == 14
    assert issue_count == 65
    assert code_issue_count == 9
    assert selected == [
        ("2019-aut", "fia-f1sr-2019-03"),
        ("2023-abu", "fia-f1sr-2023-07"),
        ("2025-aut", "fia-f1sr-2025-05"),
    ]
    assert selected_code == [
        ("2019-aut", "fia-isc-2019-01"),
        ("2023-abu", "fia-isc-2023-01"),
        ("2025-aut", "fia-isc-2025-01"),
    ]
    assert view_count == 1
    assert (PROJECT_ROOT / "sql" / "quality_checks.sql").exists()
