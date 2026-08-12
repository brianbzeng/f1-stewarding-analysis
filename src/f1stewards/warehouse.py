"""DuckDB initialization and lineage loading."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pandas as pd

from f1stewards.config import PROJECT_ROOT
from f1stewards.models import DecisionSections, PilotEvent, RegulatorySource, SourceDocument

DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "processed" / "f1_stewarding.duckdb"


def connect(db_path: Path = DEFAULT_DB_PATH) -> duckdb.DuckDBPyConnection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(db_path))


def initialize_database(
    db_path: Path = DEFAULT_DB_PATH,
    schema_path: Path | None = None,
) -> None:
    with connect(db_path) as connection:
        if schema_path:
            connection.execute(schema_path.read_text(encoding="utf-8"))
        else:
            for migration_path in sorted((PROJECT_ROOT / "sql").glob("[0-9][0-9][0-9]_*.sql")):
                connection.execute(migration_path.read_text(encoding="utf-8"))


def upsert_pilot_events(
    connection: duckdb.DuckDBPyConnection,
    events: list[PilotEvent],
) -> None:
    rows = [
        {
            "event_id": event.pilot_id,
            "season": event.season,
            "event_date": event.race_date,
            "event_name": event.event_name,
            "archive_url": str(event.archive_url),
            "guideline_regime": event.regime,
            "is_pilot": True,
        }
        for event in events
    ]
    frame = pd.DataFrame(rows)
    connection.register("event_batch", frame)
    connection.execute(
        """
        INSERT INTO metadata.events (
            event_id, season, event_name, event_date, archive_url,
            guideline_regime, is_pilot
        )
        SELECT event_id, season, event_name, event_date, archive_url,
               guideline_regime, is_pilot
        FROM event_batch
        ON CONFLICT (event_id) DO UPDATE SET
            archive_url = EXCLUDED.archive_url,
            event_date = EXCLUDED.event_date,
            guideline_regime = EXCLUDED.guideline_regime,
            is_pilot = EXCLUDED.is_pilot
        """
    )
    connection.unregister("event_batch")


def upsert_regulatory_sources(
    connection: duckdb.DuckDBPyConnection,
    sources: list[RegulatorySource],
) -> None:
    if not sources:
        return
    source_rows = []
    link_rows = []
    for source in sources:
        payload = source.model_dump(mode="json")
        event_ids = payload.pop("event_ids")
        event_role = payload.pop("event_role")
        source_rows.append(payload)
        link_rows.extend(
            {"event_id": event_id, "source_id": source.source_id, "event_role": event_role}
            for event_id in event_ids
        )
    source_frame = pd.DataFrame(source_rows)
    link_frame = pd.DataFrame(link_rows)
    connection.register("regulatory_source_batch", source_frame)
    connection.register("event_regulatory_source_batch", link_frame)
    connection.execute(
        """
        INSERT INTO metadata.regulatory_sources BY NAME
        SELECT * FROM regulatory_source_batch
        ON CONFLICT (source_id) DO UPDATE SET
            document_type = EXCLUDED.document_type,
            title = EXCLUDED.title,
            issuing_body = EXCLUDED.issuing_body,
            publication_date = EXCLUDED.publication_date,
            effective_from = EXCLUDED.effective_from,
            effective_through = EXCLUDED.effective_through,
            source_url = EXCLUDED.source_url,
            resolved_url = EXCLUDED.resolved_url,
            source_status = EXCLUDED.source_status,
            applicability_status = EXCLUDED.applicability_status,
            is_guideline = EXCLUDED.is_guideline,
            notes = EXCLUDED.notes
        """
    )
    connection.execute(
        """
        INSERT INTO metadata.event_regulatory_sources BY NAME
        SELECT * FROM event_regulatory_source_batch
        ON CONFLICT (event_id, source_id) DO UPDATE SET
            event_role = EXCLUDED.event_role
        """
    )
    connection.unregister("regulatory_source_batch")
    connection.unregister("event_regulatory_source_batch")


def replace_claim_ledger(
    connection: duckdb.DuckDBPyConnection,
    claim_path: Path | None = None,
) -> int:
    path = claim_path or PROJECT_ROOT / "reports" / "claim_ledger.csv"
    frame = pd.read_csv(path, dtype="string", keep_default_na=False)
    if frame["claim_id"].duplicated().any():
        duplicates = ", ".join(frame.loc[frame["claim_id"].duplicated(), "claim_id"])
        raise ValueError(f"Duplicate claim_id: {duplicates}")
    if frame.isna().any().any() or frame.eq("").any().any():
        raise ValueError("Claim ledger fields cannot be empty")
    connection.register("claim_ledger_batch", frame)
    connection.execute("DELETE FROM metadata.claim_ledger")
    connection.execute(
        "INSERT INTO metadata.claim_ledger BY NAME SELECT * FROM claim_ledger_batch"
    )
    connection.unregister("claim_ledger_batch")
    return len(frame)


def upsert_source_documents(
    connection: duckdb.DuckDBPyConnection,
    documents: list[SourceDocument],
) -> None:
    if not documents:
        return
    rows = []
    for document in documents:
        payload = document.model_dump(mode="json")
        payload["event_id"] = payload.pop("pilot_id")
        rows.append(payload)
    frame = pd.DataFrame(rows)
    selected_columns = [
        "document_id",
        "event_id",
        "title",
        "document_url",
        "archive_url",
        "document_class",
        "published_at_raw",
        "published_at",
        "discovered_at",
        "retrieved_at",
        "source_domain",
        "content_sha256",
        "local_path",
        "http_status",
        "content_type",
        "retrieval_error",
        "is_recalled",
        "supersedes_document_id",
    ]
    connection.register("document_batch", frame[selected_columns])
    connection.execute(
        """
        INSERT INTO raw.source_documents (
            document_id, event_id, title, document_url, archive_url, document_class,
            published_at_raw, published_at, discovered_at, retrieved_at, source_domain,
            content_sha256, local_path, http_status, content_type, retrieval_error
            , is_recalled, supersedes_document_id
        )
        SELECT
            document_id, event_id, title, document_url, archive_url, document_class,
            published_at_raw, published_at, discovered_at, retrieved_at, source_domain,
            content_sha256, local_path, http_status, content_type, retrieval_error
            , is_recalled, supersedes_document_id
        FROM document_batch
        ON CONFLICT (document_id) DO UPDATE SET
            title = EXCLUDED.title,
            published_at_raw = EXCLUDED.published_at_raw,
            published_at = EXCLUDED.published_at,
            retrieved_at = EXCLUDED.retrieved_at,
            content_sha256 = EXCLUDED.content_sha256,
            local_path = EXCLUDED.local_path,
            http_status = EXCLUDED.http_status,
            content_type = EXCLUDED.content_type,
            retrieval_error = EXCLUDED.retrieval_error,
            is_recalled = EXCLUDED.is_recalled,
            supersedes_document_id = EXCLUDED.supersedes_document_id
        """
    )
    connection.unregister("document_batch")


def upsert_document_text(
    connection: duckdb.DuckDBPyConnection,
    sections: list[DecisionSections],
    *,
    parser_version: str = "decision-sections-v1",
) -> None:
    if not sections:
        return
    parsed_at = datetime.now(UTC)
    rows = []
    for record in sections:
        payload = record.model_dump()
        payload["parser_version"] = parser_version
        payload["parsed_at"] = parsed_at
        payload["parser_warnings_json"] = json.dumps(payload.pop("parser_warnings"))
        rows.append(payload)
    frame = pd.DataFrame(rows)
    connection.register("document_text_batch", frame)
    connection.execute(
        """
        INSERT INTO raw.document_text (
            document_id, parser_version, parsed_at, page_count, raw_text,
            driver_number, driver_name, session_type, incident_time_raw,
            fact_text, infringement_text, decision_text, reason_text,
            parser_warnings_json
        )
        SELECT
            document_id, parser_version, parsed_at, page_count, raw_text,
            driver_number, driver_name, session_type, incident_time_raw,
            fact_text, infringement_text, decision_text, reason_text,
            parser_warnings_json
        FROM document_text_batch
        ON CONFLICT (document_id) DO UPDATE SET
            parser_version = EXCLUDED.parser_version,
            parsed_at = EXCLUDED.parsed_at,
            page_count = EXCLUDED.page_count,
            raw_text = EXCLUDED.raw_text,
            driver_number = EXCLUDED.driver_number,
            driver_name = EXCLUDED.driver_name,
            session_type = EXCLUDED.session_type,
            incident_time_raw = EXCLUDED.incident_time_raw,
            fact_text = EXCLUDED.fact_text,
            infringement_text = EXCLUDED.infringement_text,
            decision_text = EXCLUDED.decision_text,
            reason_text = EXCLUDED.reason_text,
            parser_warnings_json = EXCLUDED.parser_warnings_json
        """
    )
    connection.unregister("document_text_batch")
