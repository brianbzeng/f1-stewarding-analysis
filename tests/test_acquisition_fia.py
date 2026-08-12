from datetime import UTC, datetime
from pathlib import Path

from f1stewards.acquisition.fia import (
    classify_document,
    extract_document_links,
    sanitize_transport_url,
)
from f1stewards.config import load_document_classes, load_pilot_events
from f1stewards.models import DocumentClass

FIXTURES = Path(__file__).parent / "fixtures"


def test_classification_respects_includes_and_excludes() -> None:
    config = load_document_classes()
    assert classify_document("Decision - Car 33", config) == DocumentClass.STEWARD_DECISION
    assert classify_document("Summons - Car 33", config) == DocumentClass.SUMMONS
    assert (
        classify_document("Final Race Classification", config) == DocumentClass.FINAL_CLASSIFICATION
    )
    assert classify_document("Race scrutineering", config) == DocumentClass.OTHER


def test_extract_document_links_filters_navigation_duplicates_and_external_domains() -> None:
    html = (FIXTURES / "fia_archive.html").read_text(encoding="utf-8")
    event = load_pilot_events()[0]
    records = extract_document_links(
        html,
        event,
        load_document_classes(),
        discovered_at=datetime(2026, 8, 12, tzinfo=UTC),
    )

    assert len(records) == 4
    assert len({record.document_id for record in records}) == 4
    assert records[0].title == "Decision - Car 33 (Turn 3 incident with car 16)"
    assert records[0].published_at is not None
    assert records[0].document_class == DocumentClass.STEWARD_DECISION
    assert all(record.source_domain == "fia.com" for record in records)
    recalled = [record for record in records if record.is_recalled]
    assert len(recalled) == 1
    assert recalled[0].retrieval_error == "recalled_document_not_linked_by_source_archive"


def test_sanitize_transport_url_only_encodes_stray_percent_signs() -> None:
    url = "https://fia.com/a%20b/within%20107%.pdf"
    assert sanitize_transport_url(url) == "https://fia.com/a%20b/within%20107%25.pdf"
