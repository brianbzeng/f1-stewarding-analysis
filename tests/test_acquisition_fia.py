from datetime import UTC, datetime
from pathlib import Path

import httpx
import pandas as pd

from f1stewards.acquisition.fia import (
    _normalized_pdf_bytes,
    _resolve_pdf_response,
    apply_retrieval_exceptions,
    classify_document,
    discover_event,
    extract_document_links,
    extract_legacy_document_links,
    extract_legacy_timing_url,
    sanitize_transport_url,
    write_manifest,
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


def test_extract_legacy_event_timing_documents() -> None:
    landing_html = '<a href="/events/legacy/timing">Event&Timing Information</a>'
    timing_url = extract_legacy_timing_url(landing_html, "https://www.fia.com/event/british")
    assert timing_url == "https://www.fia.com/events/legacy/timing"

    timing_html = """
    <a href="/navigation"><div>Not evidence</div></a>
    <ul><li>08.07
      <div class="for-documents"><a href="/file/70380/download">
        <div class="title">Stewards Decision Doc42- K. Räikkönen</div>
      </a></div>
      <div class="for-documents"><a href="/sites/final_race_classification.pdf">
        <div class="title">Final Classification</div>
      </a></div>
    </li></ul>
    """
    event = load_pilot_events()[0].model_copy(
        update={
            "pilot_id": "2018-gbr",
            "season": 2018,
            "archive_system": "legacy_event_timing",
            "season_slug": None,
        }
    )
    records = extract_legacy_document_links(
        timing_html,
        event,
        load_document_classes(),
        archive_url=timing_url,
        discovered_at=datetime(2026, 8, 12, tzinfo=UTC),
    )

    assert len(records) == 2
    assert records[0].document_class == DocumentClass.STEWARD_DECISION
    assert records[0].published_at_raw == "08.07.18 (legacy page; time unavailable)"
    assert records[1].title == "Final Race Classification"
    assert records[1].document_class == DocumentClass.FINAL_CLASSIFICATION
    assert all(str(record.archive_url) == timing_url for record in records)


def test_discover_event_accepts_direct_legacy_timing_page() -> None:
    timing_url = (
        "https://www.fia.com/events/fia-formula-one-world-championship/"
        "season-2018/eventtiming-information-4"
    )
    timing_html = """
    <ul><li>27.05
      <div class="for-documents"><a href="/file/monaco-decision/download">
        <div class="title">Stewards Decision Doc42 - Car 7</div>
      </a></div>
    </li></ul>
    """
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return httpx.Response(200, text=timing_html, request=request)

    event = load_pilot_events()[0].model_copy(
        update={
            "pilot_id": "2018-mco",
            "season": 2018,
            "archive_url": timing_url,
            "archive_system": "legacy_event_timing",
            "season_slug": None,
        }
    )
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        records = discover_event(client, event, load_document_classes())

    assert requests == [timing_url]
    assert len(records) == 1
    assert str(records[0].archive_url) == timing_url


def test_resolve_pdf_response_rejects_non_pdf_target() -> None:
    wrapper_url = "https://www.fia.com/document-wrapper"
    target_url = "https://www.fia.com/not-a-pdf.pdf"

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == wrapper_url:
            return httpx.Response(
                200,
                text=f'<a href="{target_url}">Download</a>',
                request=request,
            )
        return httpx.Response(200, text="still HTML", request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        try:
            _resolve_pdf_response(client, wrapper_url)
        except ValueError as exc:
            assert "not a PDF" in str(exc)
        else:
            raise AssertionError("non-PDF target must fail validation")


def test_normalize_pdf_bytes_decodes_valid_base64_wrapper() -> None:
    encoded = b"JVBERi0xLjQKJXRlc3Q="
    assert _normalized_pdf_bytes(encoded) == b"%PDF-1.4\n%test"
    assert _normalized_pdf_bytes(b"JVBER-not-valid-base64") is None


def test_manifest_retry_can_clear_prior_retrieval_error(tmp_path: Path) -> None:
    path = tmp_path / "manifest.parquet"
    event = load_pilot_events()[0]
    document = extract_document_links(
        (FIXTURES / "fia_archive.html").read_text(encoding="utf-8"),
        event,
        load_document_classes(),
        discovered_at=datetime(2026, 8, 12, tzinfo=UTC),
    )[0]
    failed = document.model_copy(
        update={"retrieved_at": datetime(2026, 8, 12, tzinfo=UTC), "retrieval_error": "bad"}
    )
    succeeded = document.model_copy(
        update={
            "retrieved_at": datetime(2026, 8, 13, tzinfo=UTC),
            "retrieval_error": None,
            "content_sha256": "a" * 64,
            "local_path": tmp_path / "document.pdf",
        }
    )

    write_manifest([failed], path)
    write_manifest([succeeded], path)
    row = pd.read_parquet(path).iloc[0]

    assert pd.isna(row["retrieval_error"])
    assert row["content_sha256"] == "a" * 64


def test_manifest_backfills_source_availability_for_legacy_rows(tmp_path: Path) -> None:
    path = tmp_path / "manifest.parquet"
    event = load_pilot_events()[0]
    documents = extract_document_links(
        (FIXTURES / "fia_archive.html").read_text(encoding="utf-8"),
        event,
        load_document_classes(),
        discovered_at=datetime(2026, 8, 12, tzinfo=UTC),
    )[:2]
    legacy = pd.DataFrame([documents[0].model_dump(mode="json")]).drop(
        columns=["source_availability_status", "source_availability_note"]
    )
    legacy.to_parquet(path, index=False)

    write_manifest([documents[1]], path)
    frame = pd.read_parquet(path)

    assert frame["source_availability_status"].tolist() == ["advertised", "advertised"]


def test_retrieval_exception_preserves_broken_link_evidence() -> None:
    event = load_pilot_events()[0]
    document = extract_document_links(
        (FIXTURES / "fia_archive.html").read_text(encoding="utf-8"),
        event,
        load_document_classes(),
        discovered_at=datetime(2026, 8, 12, tzinfo=UTC),
    )[0].model_copy(update={"retrieval_error": "404 Not Found"})
    exceptions = {
        str(document.document_url): {
            "event_id": document.pilot_id,
            "source_availability_status": "verified_unavailable",
            "verified_at": "2026-08-12",
            "note": "Official link returns HTTP 404.",
        }
    }

    resolved = apply_retrieval_exceptions([document], exceptions)[0]

    assert resolved.retrieval_error == "404 Not Found"
    assert resolved.source_availability_status == "verified_unavailable"
    assert resolved.source_availability_note == (
        "Verified 2026-08-12: Official link returns HTTP 404."
    )
