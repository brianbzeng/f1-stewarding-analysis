"""DuckDB initialization and lineage loading."""

from __future__ import annotations

import json
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pandas as pd

from f1stewards.config import PROJECT_ROOT
from f1stewards.models import (
    DecisionSections,
    InternationalSportingCodeIssue,
    PilotEvent,
    RegulatorySource,
    SourceDocument,
    SportingRegulationIssue,
)

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
            "round_number": event.round_number,
            "event_date": event.race_date,
            "event_name": event.event_name,
            "country": event.country,
            "archive_url": str(event.archive_url),
            "guideline_regime": event.regime,
            "is_pilot": event.is_pilot,
            "event_timezone": event.event_timezone,
            "archive_system": event.archive_system,
            "event_format": event.event_format,
            "has_sprint": event.has_sprint,
            "catalog_source_url": (
                str(event.catalog_source_url) if event.catalog_source_url else None
            ),
        }
        for event in events
    ]
    frame = pd.DataFrame(rows)
    connection.register("event_batch", frame)
    connection.execute(
        """
        INSERT INTO metadata.events (
            event_id, season, round_number, event_name, country, event_date, archive_url,
            guideline_regime, is_pilot, event_timezone, archive_system, event_format,
            has_sprint, catalog_source_url
        )
        SELECT event_id, season, round_number, event_name, country, event_date, archive_url,
               guideline_regime, is_pilot, event_timezone, archive_system, event_format,
               has_sprint, catalog_source_url
        FROM event_batch
        ON CONFLICT (event_id) DO UPDATE SET
            round_number = EXCLUDED.round_number,
            event_name = EXCLUDED.event_name,
            country = EXCLUDED.country,
            archive_url = EXCLUDED.archive_url,
            event_date = EXCLUDED.event_date,
            guideline_regime = EXCLUDED.guideline_regime,
            is_pilot = EXCLUDED.is_pilot,
            event_timezone = EXCLUDED.event_timezone,
            archive_system = EXCLUDED.archive_system,
            event_format = EXCLUDED.event_format,
            has_sprint = EXCLUDED.has_sprint,
            catalog_source_url = EXCLUDED.catalog_source_url
        """
    )
    connection.unregister("event_batch")


upsert_study_events = upsert_pilot_events


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


def replace_sporting_regulation_issues(
    connection: duckdb.DuckDBPyConnection,
    issues: list[SportingRegulationIssue],
) -> int:
    """Replace the archive-derived Sporting Regulation issue catalog."""

    if not issues:
        raise ValueError("Sporting Regulation issue catalog cannot be empty")
    frame = pd.DataFrame([issue.model_dump(mode="json") for issue in issues])
    connection.register("sporting_regulation_issue_batch", frame)
    connection.execute("DELETE FROM metadata.sporting_regulation_issues")
    connection.execute(
        """
        INSERT INTO metadata.sporting_regulation_issues BY NAME
        SELECT * FROM sporting_regulation_issue_batch
        """
    )
    connection.unregister("sporting_regulation_issue_batch")
    return len(frame)


def replace_international_sporting_code_issues(
    connection: duckdb.DuckDBPyConnection,
    issues: list[InternationalSportingCodeIssue],
) -> int:
    """Replace the season-effective International Sporting Code catalog."""

    if not issues:
        raise ValueError("International Sporting Code issue catalog cannot be empty")
    frame = pd.DataFrame([issue.model_dump(mode="json") for issue in issues])
    connection.register("international_sporting_code_issue_batch", frame)
    connection.execute("DELETE FROM metadata.international_sporting_code_issues")
    connection.execute(
        """
        INSERT INTO metadata.international_sporting_code_issues BY NAME
        SELECT * FROM international_sporting_code_issue_batch
        """
    )
    connection.unregister("international_sporting_code_issue_batch")
    return len(frame)


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
        "source_availability_status",
        "source_availability_note",
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
            , source_availability_status, source_availability_note
            , is_recalled, supersedes_document_id
        )
        SELECT
            document_id, event_id, title, document_url, archive_url, document_class,
            published_at_raw, published_at, discovered_at, retrieved_at, source_domain,
            content_sha256, local_path, http_status, content_type, retrieval_error
            , source_availability_status, source_availability_note
            , is_recalled, supersedes_document_id
        FROM document_batch
        ON CONFLICT (document_id) DO UPDATE SET
            title = EXCLUDED.title,
            document_class = EXCLUDED.document_class,
            published_at_raw = EXCLUDED.published_at_raw,
            published_at = EXCLUDED.published_at,
            retrieved_at = EXCLUDED.retrieved_at,
            content_sha256 = EXCLUDED.content_sha256,
            local_path = EXCLUDED.local_path,
            http_status = EXCLUDED.http_status,
            content_type = EXCLUDED.content_type,
            retrieval_error = EXCLUDED.retrieval_error,
            source_availability_status = EXCLUDED.source_availability_status,
            source_availability_note = EXCLUDED.source_availability_note,
            is_recalled = EXCLUDED.is_recalled,
            supersedes_document_id = EXCLUDED.supersedes_document_id
        """
    )
    connection.unregister("document_batch")


def synchronize_source_documents_for_events(
    connection: duckdb.DuckDBPyConnection,
    event_ids: set[str],
    documents: list[SourceDocument],
) -> None:
    """Make selected event inventories exact while preserving unchanged parsed documents."""

    if not event_ids:
        upsert_source_documents(connection, documents)
        return
    document_event_ids = {document.pilot_id for document in documents}
    if unexpected := document_event_ids - event_ids:
        raise ValueError(
            "Source-document batch contains events outside replacement scope: "
            + ", ".join(sorted(unexpected))
        )
    if missing := event_ids - document_event_ids:
        raise ValueError(
            "Cannot synchronize events without discovered documents: "
            + ", ".join(sorted(missing))
        )

    incoming_ids = {document.document_id for document in documents}
    placeholders = ", ".join("?" for _ in event_ids)
    prior_rows = connection.execute(
        f"SELECT document_id FROM raw.source_documents WHERE event_id IN ({placeholders})",  # noqa: S608
        sorted(event_ids),
    ).fetchall()
    stale_ids = {row[0] for row in prior_rows} - incoming_ids
    if not stale_ids:
        upsert_source_documents(connection, documents)
        return

    stale_frame = pd.DataFrame({"document_id": sorted(stale_ids)})
    connection.register("stale_source_document_ids", stale_frame)
    try:
        protected_reference_count = connection.sql(
            """
            SELECT count(*)
            FROM (
                SELECT source_document_id AS document_id FROM curated.incidents
                UNION ALL
                SELECT decision_document_id FROM curated.adjudications
                UNION ALL
                SELECT source_document_id FROM curated.harm_assessments
                UNION ALL
                SELECT classification_source_document_id FROM curated.harm_assessments
                UNION ALL
                SELECT source_document_id FROM curated.incident_locations
                UNION ALL
                SELECT source_document_id FROM curated.incident_relations
                UNION ALL
                SELECT source_document_id FROM curated.cross_event_sanction_effects
            ) AS reference
            JOIN stale_source_document_ids USING (document_id)
            """
        ).fetchone()[0]
        if protected_reference_count:
            raise ValueError(
                f"Refusing to remove {len(stale_ids)} stale source documents because "
                f"{protected_reference_count} curated references require manual migration"
            )

        affected_feature_builds = connection.sql(
            """
            SELECT DISTINCT feature_build_id
            FROM analysis.adjudication_features
            JOIN stale_source_document_ids USING (document_id)
            """
        ).df()
        # DuckDB cannot delete a referenced child and its parent in one transaction.
        # Commit generated/parsed child invalidation first; a failed second phase leaves
        # the old source inventory visible and therefore detectable by reconciliation.
        connection.execute("BEGIN TRANSACTION")
        if not affected_feature_builds.empty:
            connection.register("affected_feature_build_ids", affected_feature_builds)
            for table in (
                "analysis.adjudication_driver_roles",
                "analysis.feature_release_controls",
                "analysis.adjudication_features",
                "metadata.analysis_feature_builds",
            ):
                connection.execute(
                    f"DELETE FROM {table} WHERE feature_build_id IN "  # noqa: S608
                    "(SELECT feature_build_id FROM affected_feature_build_ids)"
                )
            connection.unregister("affected_feature_build_ids")
        connection.execute(
            "DELETE FROM curated.document_panels WHERE document_id IN "
            "(SELECT document_id FROM stale_source_document_ids)"
        )
        connection.execute(
            "UPDATE curated.panels SET panel_source_document_id = NULL "
            "WHERE panel_source_document_id IN "
            "(SELECT document_id FROM stale_source_document_ids)"
        )
        connection.execute(
            "DELETE FROM raw.document_text WHERE document_id IN "
            "(SELECT document_id FROM stale_source_document_ids)"
        )
        connection.execute("COMMIT")
        connection.execute("BEGIN TRANSACTION")
        connection.execute(
            "DELETE FROM raw.source_documents WHERE document_id IN "
            "(SELECT document_id FROM stale_source_document_ids)"
        )
        upsert_source_documents(connection, documents)
        connection.execute("COMMIT")
    except Exception:
        with suppress(duckdb.TransactionException):
            connection.execute("ROLLBACK")
        raise
    finally:
        connection.unregister("stale_source_document_ids")


def upsert_document_text(
    connection: duckdb.DuckDBPyConnection,
    sections: list[DecisionSections],
    *,
    parser_version: str = "decision-sections-v4",
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
            content_document_class, content_classification_basis,
            driver_number, driver_name, session_type, incident_time_raw,
            fact_text, infringement_text, decision_text, reason_text,
            parser_warnings_json
        )
        SELECT
            document_id, parser_version, parsed_at, page_count, raw_text,
            content_document_class, content_classification_basis,
            driver_number, driver_name, session_type, incident_time_raw,
            fact_text, infringement_text, decision_text, reason_text,
            parser_warnings_json
        FROM document_text_batch
        ON CONFLICT (document_id) DO UPDATE SET
            parser_version = EXCLUDED.parser_version,
            parsed_at = EXCLUDED.parsed_at,
            page_count = EXCLUDED.page_count,
            raw_text = EXCLUDED.raw_text,
            content_document_class = EXCLUDED.content_document_class,
            content_classification_basis = EXCLUDED.content_classification_basis,
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
