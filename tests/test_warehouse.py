from datetime import UTC, datetime
from pathlib import Path

import duckdb

from f1stewards.config import (
    PROJECT_ROOT,
    load_international_sporting_code_issues,
    load_pilot_events,
    load_regulatory_sources,
    load_sporting_regulation_issues,
)
from f1stewards.models import DocumentClass, SourceDocument
from f1stewards.warehouse import (
    initialize_database,
    replace_claim_ledger,
    replace_international_sporting_code_issues,
    replace_sporting_regulation_issues,
    synchronize_source_documents_for_events,
    upsert_pilot_events,
    upsert_regulatory_sources,
    upsert_source_documents,
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
        typed_view_count = connection.sql(
            "SELECT count(*) FROM information_schema.views "
            "WHERE table_name = 'v_source_documents_typed'"
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
    assert claim_count == 19
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
    assert typed_view_count == 1
    assert (PROJECT_ROOT / "sql" / "quality_checks.sql").exists()


def test_source_document_upsert_refreshes_document_class(tmp_path: Path) -> None:
    db_path = tmp_path / "test.duckdb"
    event = load_pilot_events()[0]
    document = SourceDocument(
        document_id="test-document",
        pilot_id=event.pilot_id,
        season=event.season,
        event_name=event.event_name,
        title="Administrative archive title",
        document_url=f"{event.archive_url}#test-document",
        archive_url=event.archive_url,
        document_class=DocumentClass.OTHER,
        discovered_at=datetime(2026, 8, 12, tzinfo=UTC),
    )

    initialize_database(db_path)
    with duckdb.connect(str(db_path)) as connection:
        upsert_pilot_events(connection, [event])
        upsert_source_documents(connection, [document])
        upsert_source_documents(
            connection,
            [document.model_copy(update={"document_class": DocumentClass.STEWARD_DECISION})],
        )
        stored_class = connection.sql(
            "SELECT document_class FROM raw.source_documents WHERE document_id = 'test-document'"
        ).fetchone()[0]

    assert stored_class == "steward_decision"


def test_source_document_event_synchronization_removes_only_stale_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "test.duckdb"
    event = load_pilot_events()[0]
    base = SourceDocument(
        document_id="kept-document",
        pilot_id=event.pilot_id,
        season=event.season,
        event_name=event.event_name,
        title="Kept decision",
        document_url=f"{event.archive_url}#kept-document",
        archive_url=event.archive_url,
        document_class=DocumentClass.STEWARD_DECISION,
        discovered_at=datetime(2026, 8, 12, tzinfo=UTC),
    )
    stale = SourceDocument.model_validate(
        {
            **base.model_dump(mode="json"),
            "document_id": "stale-document",
            "title": "Stale decision",
            "document_url": f"{event.archive_url}#stale-document",
        }
    )
    replacement = SourceDocument.model_validate(
        {
            **base.model_dump(mode="json"),
            "document_id": "replacement-document",
            "title": "Replacement decision",
            "document_url": f"{event.archive_url}#replacement-document",
        }
    )

    initialize_database(db_path)
    with duckdb.connect(str(db_path)) as connection:
        upsert_pilot_events(connection, [event])
        upsert_source_documents(connection, [base, stale])
        connection.execute(
            "INSERT INTO curated.panels "
            "(panel_id, event_id, panel_size, panel_source_document_id) "
            "VALUES ('stale-source-panel', ?, 4, 'stale-document')",
            [event.pilot_id],
        )
        synchronize_source_documents_for_events(connection, {event.pilot_id}, [base, replacement])
        stored = connection.sql(
            "SELECT document_id FROM raw.source_documents ORDER BY document_id"
        ).fetchall()
        panel_source = connection.sql(
            "SELECT panel_source_document_id FROM curated.panels "
            "WHERE panel_id = 'stale-source-panel'"
        ).fetchone()[0]

    assert stored == [("kept-document",), ("replacement-document",)]
    assert panel_source is None
