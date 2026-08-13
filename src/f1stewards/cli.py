"""Command-line entry points for reproducible pipeline operations."""

from __future__ import annotations

import hashlib
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import duckdb
import httpx
import pandas as pd
import typer

from f1stewards.acquisition.fia import (
    apply_document_lineage,
    apply_retrieval_exceptions,
    build_client,
    discover_event,
    download_documents,
    write_manifest,
)
from f1stewards.catalog import build_study_event_catalog, write_study_event_catalog
from f1stewards.coding_queue import (
    audit_full_corpus_seed_bundle,
    build_exclusion_qa_sample,
    build_full_corpus_coding_queues,
    load_outcome_document_population,
    write_full_corpus_seed_bundle,
)
from f1stewards.config import (
    PROJECT_ROOT,
    load_analysis_thresholds,
    load_document_classes,
    load_document_lineage,
    load_evidence_profiles,
    load_full_collection_settings,
    load_full_corpus_coding_settings,
    load_international_sporting_code_issues,
    load_pilot_events,
    load_regulatory_sources,
    load_retrieval_exceptions,
    load_sporting_regulation_issues,
    load_study_events,
)
from f1stewards.enrichment.fastf1 import fetch_pilot_race, replace_event_enrichment
from f1stewards.explorer import build_explorer_payload, write_explorer
from f1stewards.impact import remove_post_race_time_penalty
from f1stewards.inventory import (
    inventory_reconciliation_is_clean,
    reconcile_document_inventory,
)
from f1stewards.manual import (
    CodedAdjudication,
    HarmAssessment,
    ImpactAssessment,
    IndependentReviewRecord,
)
from f1stewards.models import DocumentClass
from f1stewards.parsing.decision import parse_decision_pdf
from f1stewards.readiness import (
    evaluate_pilot_readiness,
    load_pilot_manual_records,
    readiness_decision,
)
from f1stewards.reconciliation import (
    build_pilot_reconciliation,
    write_reconciliation_bundle,
)
from f1stewards.snowflake import export_snowflake_pilot, validate_snowflake_export
from f1stewards.warehouse import (
    DEFAULT_DB_PATH,
    connect,
    initialize_database,
    replace_claim_ledger,
    replace_international_sporting_code_issues,
    replace_sporting_regulation_issues,
    upsert_document_text,
    upsert_pilot_events,
    upsert_regulatory_sources,
    upsert_source_documents,
    upsert_study_events,
)

app = typer.Typer(no_args_is_help=True, help="Auditable F1 stewarding analytics pipeline.")

PILOT_EVIDENCE_CLASSES = {
    DocumentClass.STEWARD_DECISION,
    DocumentClass.SUMMONS,
    DocumentClass.FINAL_CLASSIFICATION,
    DocumentClass.PROVISIONAL_CLASSIFICATION,
    DocumentClass.CHAMPIONSHIP_POINTS,
    DocumentClass.RACE_DIRECTOR_NOTES,
    DocumentClass.CIRCUIT_MAP,
}


def _reuse_verified_downloads(documents, db_path: Path):
    """Hydrate discovery records from prior successful, still-present downloads."""

    if not db_path.exists():
        return documents
    with duckdb.connect(str(db_path), read_only=True) as connection:
        rows = connection.sql(
            """
            SELECT
                document_id, retrieved_at, content_sha256, local_path,
                http_status, content_type
            FROM raw.source_documents
            WHERE content_sha256 IS NOT NULL
              AND local_path IS NOT NULL
              AND retrieval_error IS NULL
            """
        ).fetchall()
    existing = {
        row[0]: {
            "retrieved_at": row[1],
            "content_sha256": row[2],
            "local_path": Path(row[3]),
            "http_status": row[4],
            "content_type": row[5],
        }
        for row in rows
        if Path(row[3]).exists()
    }
    hydrated = []
    for document in documents:
        if document.document_id in existing:
            hydrated.append(document.model_copy(update=existing[document.document_id]))
            continue
        local_matches = list(
            (PROJECT_ROOT / "data" / "raw" / "fia" / str(document.season) / document.pilot_id).glob(
                f"{document.document_id}-*.pdf"
            )
        )
        if len(local_matches) == 1:
            local_path = local_matches[0]
            content = local_path.read_bytes()
            hydrated.append(
                document.model_copy(
                    update={
                        "retrieved_at": datetime.fromtimestamp(local_path.stat().st_mtime, tz=UTC),
                        "content_sha256": hashlib.sha256(content).hexdigest(),
                        "local_path": local_path,
                        "http_status": 200,
                        "content_type": "application/pdf",
                    }
                )
            )
            continue
        hydrated.append(document)
    return hydrated


def _sql_statements(sql_text: str) -> list[str]:
    return [statement.strip() for statement in sql_text.split(";") if statement.strip()]


def _write_discovery_failures(
    failures: list[dict[str, object]], attempted_event_ids: set[str], path: Path
) -> None:
    """Merge event-level failures while removing successful reruns from the active queue."""

    columns = ["event_id", "season", "archive_url", "failed_at_utc", "error"]
    existing = pd.read_csv(path) if path.exists() else pd.DataFrame(columns=columns)
    if not existing.empty:
        existing = existing[~existing["event_id"].isin(attempted_event_ids)]
    incoming = pd.DataFrame(failures, columns=columns)
    merged = pd.concat([existing, incoming], ignore_index=True).sort_values(
        ["season", "event_id"]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(path, index=False, lineterminator="\n")


@app.command("init-db")
def init_db(
    db_path: Annotated[Path, typer.Option(help="DuckDB database path.")] = DEFAULT_DB_PATH,
) -> None:
    """Create the empty analytical schema and register pilot events."""

    initialize_database(db_path)
    events = load_pilot_events()
    regulatory_sources = load_regulatory_sources()
    sporting_regulation_issues = load_sporting_regulation_issues()
    international_sporting_code_issues = load_international_sporting_code_issues()
    with connect(db_path) as connection:
        upsert_pilot_events(connection, events)
        upsert_regulatory_sources(connection, regulatory_sources)
        issue_count = replace_sporting_regulation_issues(
            connection, sporting_regulation_issues
        )
        code_issue_count = replace_international_sporting_code_issues(
            connection, international_sporting_code_issues
        )
        claim_count = replace_claim_ledger(connection)
    typer.echo(
        f"Initialized {db_path} with {len(events)} pilot events and "
        f"{len(regulatory_sources)} event-linked regulatory sources; loaded "
        f"{issue_count} Sporting Regulation issues, {code_issue_count} International "
        f"Sporting Code issues, and {claim_count} report claims"
    )


@app.command("build-study-catalog")
def build_study_catalog(
    output_path: Annotated[Path, typer.Option(help="Frozen study-event CSV.")] = (
        PROJECT_ROOT / "config" / "study_events.csv"
    ),
) -> None:
    """Freeze completed 2018-2025 FastF1 schedules into official FIA archive targets."""

    import fastf1

    settings = load_full_collection_settings()
    schedules = {
        season: fastf1.get_event_schedule(season, include_testing=False)
        for season in settings["completed_seasons"]
    }
    events = build_study_event_catalog(schedules, settings)
    digest = write_study_event_catalog(events, output_path)
    counts = pd.Series([event.season for event in events]).value_counts().sort_index()
    typer.echo(
        f"Wrote {len(events)} completed events to {output_path}; sha256={digest}\n"
        + counts.rename("events").to_string()
    )


@app.command("study-catalog")
def study_catalog(
    catalog_path: Annotated[Path, typer.Option(help="Frozen study-event CSV.")] = (
        PROJECT_ROOT / "config" / "study_events.csv"
    ),
) -> None:
    """Audit frozen full-study event counts, archive systems, and Sprint coverage."""

    events = load_study_events(catalog_path)
    frame = pd.DataFrame([event.model_dump(mode="json") for event in events])
    summary = (
        frame.groupby(["season", "archive_system"], dropna=False)
        .agg(events=("pilot_id", "size"), sprint_events=("has_sprint", "sum"))
        .reset_index()
    )
    typer.echo(summary.to_string(index=False))
    typer.echo(
        f"\nTotal: {len(events)} events; pilots: {sum(event.is_pilot for event in events)}"
    )


@app.command("init-study-db")
def init_study_db(
    db_path: Annotated[Path, typer.Option(help="DuckDB database path.")] = DEFAULT_DB_PATH,
    catalog_path: Annotated[Path, typer.Option(help="Frozen study-event CSV.")] = (
        PROJECT_ROOT / "config" / "study_events.csv"
    ),
) -> None:
    """Initialize DuckDB and register the complete 2018-2025 event population."""

    initialize_database(db_path)
    events = load_study_events(catalog_path)
    regulatory_sources = load_regulatory_sources()
    with connect(db_path) as connection:
        upsert_study_events(connection, events)
        upsert_regulatory_sources(connection, regulatory_sources)
        issue_count = replace_sporting_regulation_issues(
            connection, load_sporting_regulation_issues()
        )
        code_issue_count = replace_international_sporting_code_issues(
            connection, load_international_sporting_code_issues()
        )
        claim_count = replace_claim_ledger(connection)
    typer.echo(
        f"Initialized {db_path} with {len(events)} study events; loaded {issue_count} "
        f"Sporting Regulation issues, {code_issue_count} Code issues, and "
        f"{claim_count} report claims"
    )


@app.command("claim-audit")
def claim_audit(
    db_path: Annotated[Path, typer.Option(help="DuckDB database path.")] = DEFAULT_DB_PATH,
) -> None:
    """Display the planned report claims, evidence grades, and release status."""

    with duckdb.connect(str(db_path), read_only=True) as connection:
        claims = connection.sql(
            """
            SELECT
                claim_id,
                report_section,
                research_question,
                evidence_grade_if_met,
                status,
                claim_template
            FROM metadata.claim_ledger
            ORDER BY claim_id
            """
        ).df()
    typer.echo(claims.to_string(index=False))


@app.command("regulatory-audit")
def regulatory_audit(
    db_path: Annotated[Path, typer.Option(help="DuckDB database path.")] = DEFAULT_DB_PATH,
) -> None:
    """Show the event-date governing and guidance source matrix."""

    with duckdb.connect(str(db_path), read_only=True) as connection:
        matrix = connection.sql(
            """
            SELECT
                l.event_id,
                l.event_role,
                s.document_type,
                s.publication_date,
                s.applicability_status,
                s.source_status,
                s.title
            FROM metadata.event_regulatory_sources AS l
            JOIN metadata.regulatory_sources AS s USING (source_id)
            ORDER BY l.event_id, l.event_role, s.document_type
            """
        ).df()
    typer.echo(matrix.to_string(index=False))


@app.command("sporting-regulation-audit")
def sporting_regulation_audit(
    db_path: Annotated[Path, typer.Option(help="DuckDB database path.")] = DEFAULT_DB_PATH,
) -> None:
    """Show catalog coverage and the event-date issue selected for each loaded event."""

    with duckdb.connect(str(db_path), read_only=True) as connection:
        coverage = connection.sql(
            """
            SELECT
                season,
                count(*) AS issue_count,
                count(document_url) AS resolved_binary_count,
                min(publication_date) AS first_publication,
                max(publication_date) AS last_publication
            FROM metadata.sporting_regulation_issues
            GROUP BY season
            ORDER BY season
            """
        ).df()
        selected = connection.sql(
            """
            SELECT
                event_id,
                event_date,
                source_id,
                issue_label,
                publication_date,
                resolution_status,
                selection_status
            FROM analysis.v_event_sporting_regulation_selection
            ORDER BY event_date
            """
        ).df()
    typer.echo("Catalog coverage:\n" + coverage.to_string(index=False))
    typer.echo("\nEvent-date selections:\n" + selected.to_string(index=False))


@app.command("international-sporting-code-audit")
def international_sporting_code_audit(
    db_path: Annotated[Path, typer.Option(help="DuckDB database path.")] = DEFAULT_DB_PATH,
) -> None:
    """Show Code catalog coverage and the issue selected for each loaded event."""

    with duckdb.connect(str(db_path), read_only=True) as connection:
        coverage = connection.sql(
            """
            SELECT
                season,
                count(*) AS issue_count,
                count(document_url) AS resolved_binary_count,
                min(effective_from) AS first_effective,
                max(effective_through) AS last_effective
            FROM metadata.international_sporting_code_issues
            GROUP BY season
            ORDER BY season
            """
        ).df()
        selected = connection.sql(
            """
            SELECT
                event_id,
                event_date,
                source_id,
                effective_from,
                effective_through,
                resolution_status,
                selection_status
            FROM analysis.v_event_international_sporting_code_selection
            ORDER BY event_date
            """
        ).df()
    typer.echo("Catalog coverage:\n" + coverage.to_string(index=False))
    typer.echo("\nEvent-date selections:\n" + selected.to_string(index=False))


@app.command("pilot-discover")
def pilot_discover(
    event_id: Annotated[
        str | None, typer.Option(help="One pilot id; default discovers all.")
    ] = None,
    download: Annotated[bool, typer.Option(help="Retrieve pilot evidence PDFs.")] = False,
    db_path: Annotated[Path, typer.Option(help="DuckDB database path.")] = DEFAULT_DB_PATH,
    manifest_path: Annotated[Path, typer.Option(help="Parquet lineage manifest.")] = (
        PROJECT_ROOT / "data" / "interim" / "pilot_source_manifest.parquet"
    ),
) -> None:
    """Discover official documents for the configured pilot events."""

    events = load_pilot_events()
    if event_id:
        events = [event for event in events if event.pilot_id == event_id]
        if not events:
            raise typer.BadParameter(f"Unknown pilot id: {event_id}")
    classes = load_document_classes()
    lineage_links = load_document_lineage()
    all_documents = []
    with build_client() as client:
        for event in events:
            documents = discover_event(client, event, classes)
            documents = apply_document_lineage(documents, lineage_links)
            documents = _reuse_verified_downloads(documents, db_path)
            typer.echo(f"{event.pilot_id}: discovered {len(documents)} documents")
            if download:
                selected = [
                    document
                    for document in documents
                    if document.document_class in PILOT_EVIDENCE_CLASSES
                    and document.content_sha256 is None
                    and not document.is_recalled
                ]
                downloaded = download_documents(client, selected, PROJECT_ROOT / "data" / "raw")
                downloaded_by_id = {document.document_id: document for document in downloaded}
                documents = [
                    downloaded_by_id.get(document.document_id, document) for document in documents
                ]
                download_failure_count = sum(
                    document.retrieval_error is not None for document in downloaded
                )
                typer.echo(
                    f"{event.pilot_id}: downloaded {len(downloaded) - download_failure_count}; "
                    f"failures {download_failure_count}"
                )
            all_documents.extend(documents)

    write_manifest(all_documents, manifest_path)
    initialize_database(db_path)
    with connect(db_path) as connection:
        upsert_pilot_events(connection, events)
        upsert_source_documents(connection, all_documents)
    typer.echo(f"Wrote {len(all_documents)} lineage rows to {manifest_path} and {db_path}")


@app.command("study-discover")
def study_discover(
    event_id: Annotated[str | None, typer.Option(help="One study event id.")] = None,
    season: Annotated[int | None, typer.Option(help="One completed season.")] = None,
    download: Annotated[bool, typer.Option(help="Retrieve selected evidence PDFs.")] = False,
    delay_seconds: Annotated[
        float, typer.Option(help="Delay between document downloads.")
    ] = 1.0,
    event_delay_seconds: Annotated[
        float, typer.Option(help="Delay between FIA event-page requests.")
    ] = 0.5,
    download_profile: Annotated[
        str, typer.Option(help="Configured evidence profile used with --download.")
    ] = "decisions",
    db_path: Annotated[Path, typer.Option(help="DuckDB database path.")] = DEFAULT_DB_PATH,
    catalog_path: Annotated[Path, typer.Option(help="Frozen study-event CSV.")] = (
        PROJECT_ROOT / "config" / "study_events.csv"
    ),
    manifest_path: Annotated[Path, typer.Option(help="Full-corpus Parquet manifest.")] = (
        PROJECT_ROOT / "data" / "interim" / "study_source_manifest.parquet"
    ),
    failure_path: Annotated[Path, typer.Option(help="Active event-discovery failures.")] = (
        PROJECT_ROOT / "data" / "interim" / "study_discovery_failures.csv"
    ),
) -> None:
    """Discover official evidence for frozen 2018-2025 study events."""

    events = load_study_events(catalog_path)
    if event_id:
        events = [event for event in events if event.pilot_id == event_id]
        if not events:
            raise typer.BadParameter(f"Unknown study event id: {event_id}")
    if season is not None:
        if season not in range(2018, 2026):
            raise typer.BadParameter("Season must be between 2018 and 2025")
        events = [event for event in events if event.season == season]
    classes = load_document_classes()
    lineage_links = load_document_lineage()
    evidence_profiles = load_evidence_profiles()
    if download_profile not in evidence_profiles:
        choices = ", ".join(sorted(evidence_profiles))
        raise typer.BadParameter(
            f"Unknown download profile: {download_profile}. Available profiles: {choices}"
        )
    selected_classes = evidence_profiles[download_profile]
    retrieval_exceptions = load_retrieval_exceptions()
    all_documents = []
    failures: list[dict[str, object]] = []
    retrieval_failure_count = 0
    attempted_event_ids = {event.pilot_id for event in events}
    with build_client() as client:
        for index, event in enumerate(events):
            if index and event_delay_seconds > 0:
                time.sleep(event_delay_seconds)
            try:
                documents = discover_event(client, event, classes)
            except (httpx.HTTPError, ValueError) as exc:
                failures.append(
                    {
                        "event_id": event.pilot_id,
                        "season": event.season,
                        "archive_url": str(event.archive_url),
                        "failed_at_utc": datetime.now(UTC).isoformat(),
                        "error": str(exc),
                    }
                )
                typer.echo(f"{event.pilot_id}: discovery failed: {exc}", err=True)
                continue
            documents = apply_document_lineage(documents, lineage_links)
            documents = _reuse_verified_downloads(documents, db_path)
            typer.echo(f"{event.pilot_id}: discovered {len(documents)} documents")
            if download:
                selected = [
                    document
                    for document in documents
                    if document.document_class in selected_classes
                    and document.content_sha256 is None
                    and not document.is_recalled
                ]
                downloaded = download_documents(
                    client,
                    selected,
                    PROJECT_ROOT / "data" / "raw",
                    delay_seconds=delay_seconds,
                )
                downloaded = apply_retrieval_exceptions(downloaded, retrieval_exceptions)
                downloaded_by_id = {document.document_id: document for document in downloaded}
                documents = [
                    downloaded_by_id.get(document.document_id, document) for document in documents
                ]
                download_failure_count = sum(
                    document.retrieval_error is not None
                    and document.source_availability_status != "verified_unavailable"
                    for document in downloaded
                )
                retrieval_failure_count += download_failure_count
                typer.echo(
                    f"{event.pilot_id}: downloaded {len(downloaded) - download_failure_count}; "
                    f"failures {download_failure_count}"
                )
            all_documents.extend(documents)

    if all_documents:
        write_manifest(all_documents, manifest_path)
    _write_discovery_failures(failures, attempted_event_ids, failure_path)
    initialize_database(db_path)
    with connect(db_path) as connection:
        upsert_study_events(connection, events)
        if all_documents:
            upsert_source_documents(connection, all_documents)
    typer.echo(
        f"Wrote {len(all_documents)} lineage rows across {len(events)} events to "
        f"{manifest_path} and {db_path}; active discovery failures: {len(failures)}; "
        f"retrieval failures: {retrieval_failure_count}"
    )
    if failures or retrieval_failure_count:
        raise typer.Exit(code=1)


@app.command("study-inventory")
def study_inventory(
    db_path: Annotated[Path, typer.Option(help="DuckDB database path.")] = DEFAULT_DB_PATH,
    manifest_path: Annotated[Path, typer.Option(help="Full-corpus Parquet manifest.")] = (
        PROJECT_ROOT / "data" / "interim" / "study_source_manifest.parquet"
    ),
    failure_path: Annotated[Path, typer.Option(help="Active event-discovery failures.")] = (
        PROJECT_ROOT / "data" / "interim" / "study_discovery_failures.csv"
    ),
    strict: Annotated[
        bool, typer.Option(help="Exit nonzero when catalog, Parquet, and DuckDB disagree.")
    ] = True,
) -> None:
    """Audit full-study event and evidence coverage by season and archive system."""

    if not manifest_path.exists():
        raise typer.BadParameter(f"Manifest does not exist: {manifest_path}")
    manifest = pd.read_parquet(manifest_path)
    active_failure_count = 0
    if failure_path.exists():
        active_failure_count = len(pd.read_csv(failure_path))
    with duckdb.connect(str(db_path), read_only=True) as connection:
        event_counts = connection.sql(
            """
            SELECT
                season,
                count(*) AS catalog_events,
                count(*) FILTER (WHERE is_pilot) AS pilot_events,
                count(*) FILTER (WHERE has_sprint) AS sprint_events,
                count(DISTINCT archive_system) AS archive_systems
            FROM metadata.events
            GROUP BY season
            ORDER BY season
            """
        ).df()
        evidence_counts = connection.sql(
            """
            SELECT
                e.season,
                count(DISTINCT d.event_id) AS discovered_events,
                count(d.document_id) AS source_records,
                count(*) FILTER (
                    WHERE d.document_class = 'steward_decision'
                ) AS archive_decision_labels,
                count(*) FILTER (
                    WHERE NOT d.is_recalled
                      AND coalesce(t.content_document_class, d.document_class) =
                        'steward_decision'
                ) AS effective_decisions,
                count(t.content_document_class) AS content_typed_documents,
                count(d.content_sha256) AS retrieved_files,
                count(*) FILTER (
                    WHERE d.retrieval_error IS NOT NULL
                      AND NOT d.is_recalled
                      AND d.source_availability_status <> 'verified_unavailable'
                ) AS active_failures,
                count(*) FILTER (
                    WHERE d.source_availability_status = 'verified_unavailable'
                ) AS verified_unavailable_records,
                count(*) FILTER (
                    WHERE d.supersedes_document_id IS NOT NULL
                ) AS corrected_successor_records,
                count(*) FILTER (
                    WHERE d.is_recalled
                      AND d.document_class = 'steward_decision'
                      AND successor.document_id IS NULL
                ) AS unresolved_recalled_decisions,
                count(*) FILTER (WHERE d.is_recalled) AS recalled_records
            FROM metadata.events AS e
            LEFT JOIN raw.source_documents AS d USING (event_id)
            LEFT JOIN raw.document_text AS t USING (document_id)
            LEFT JOIN raw.source_documents AS successor
                ON successor.supersedes_document_id = d.document_id
            GROUP BY e.season
            ORDER BY e.season
            """
        ).df()
        warehouse_documents = connection.sql(
            "SELECT document_id, event_id FROM raw.source_documents"
        ).df()
        active_retrieval_failures = connection.sql(
            """
            SELECT count(*)
            FROM raw.source_documents
            WHERE retrieval_error IS NOT NULL
              AND NOT is_recalled
              AND source_availability_status <> 'verified_unavailable'
            """
        ).fetchone()[0]
        catalog_event_ids = {
            row[0] for row in connection.sql("SELECT event_id FROM metadata.events").fetchall()
        }
    reconciliation = reconcile_document_inventory(
        manifest,
        warehouse_documents,
        catalog_event_ids,
        active_discovery_failures=active_failure_count,
        active_retrieval_failures=active_retrieval_failures,
    )
    reconciliation_frame = pd.DataFrame(
        {"metric": list(reconciliation), "value": list(reconciliation.values())}
    )
    typer.echo("Event catalog:\n" + event_counts.to_string(index=False))
    typer.echo("\nEvidence coverage:\n" + evidence_counts.to_string(index=False))
    typer.echo("\nArtifact reconciliation:\n" + reconciliation_frame.to_string(index=False))
    if strict and not inventory_reconciliation_is_clean(reconciliation):
        raise typer.Exit(code=1)


@app.command("pilot-inventory")
def pilot_inventory(
    db_path: Annotated[Path, typer.Option(help="DuckDB database path.")] = DEFAULT_DB_PATH,
    show_other: Annotated[
        bool, typer.Option(help="Also list titles not recognized by a document rule.")
    ] = False,
    show_decisions: Annotated[
        bool, typer.Option(help="Also list documents classified as steward decisions.")
    ] = False,
    show_failures: Annotated[
        bool, typer.Option(help="Also list evidence retrieval failures.")
    ] = False,
) -> None:
    """Print a compact audit of the discovered pilot document inventory."""

    with duckdb.connect(str(db_path), read_only=True) as connection:
        counts = connection.sql(
            """
            SELECT
                event_id,
                document_class,
                count(*) AS document_count,
                count(content_sha256) AS retrieved_count,
                count(*) FILTER (
                    WHERE retrieval_error IS NOT NULL AND NOT is_recalled
                ) AS failure_count,
                count(*) FILTER (WHERE is_recalled) AS unavailable_recalled_count
            FROM raw.source_documents
            GROUP BY ALL
            ORDER BY event_id, document_count DESC, document_class
            """
        ).df()
        typer.echo(counts.to_string(index=False))
        if show_other:
            other = connection.sql(
                """
                SELECT event_id, title
                FROM raw.source_documents
                WHERE document_class = 'other'
                ORDER BY event_id, published_at, title
                """
            ).df()
            typer.echo("\nUnclassified titles:\n" + other.to_string(index=False))
        if show_decisions:
            decisions = connection.sql(
                """
                SELECT document_id, event_id, title, document_url
                FROM raw.source_documents
                WHERE document_class = 'steward_decision'
                ORDER BY event_id, published_at, title
                """
            ).df()
            typer.echo("\nDecision titles:\n" + decisions.to_string(index=False))
        if show_failures:
            failures = connection.sql(
                """
                SELECT event_id, title, document_url, retrieval_error
                FROM raw.source_documents
                WHERE retrieval_error IS NOT NULL
                  AND NOT is_recalled
                ORDER BY event_id, title
                """
            ).df()
            typer.echo("\nRetrieval failures:\n" + failures.to_string(index=False))


@app.command("parse-decisions")
def parse_decisions(
    db_path: Annotated[Path, typer.Option(help="DuckDB database path.")] = DEFAULT_DB_PATH,
) -> None:
    """Extract labeled sections from downloaded steward-decision PDFs."""

    parsed = []
    failures: list[tuple[str, str]] = []
    with duckdb.connect(str(db_path), read_only=True) as connection:
        documents = connection.sql(
            """
            SELECT document_id, local_path
            FROM raw.source_documents
            WHERE document_class = 'steward_decision'
              AND local_path IS NOT NULL
              AND retrieval_error IS NULL
            ORDER BY event_id, published_at
            """
        ).fetchall()
    for document_id, local_path in documents:
        try:
            parsed.append(parse_decision_pdf(Path(local_path), document_id))
        except (OSError, ValueError) as exc:
            failures.append((document_id, str(exc)))
    with connect(db_path) as connection:
        upsert_document_text(connection, parsed)
    typer.echo(f"Parsed {len(parsed)} decision PDFs; failures {len(failures)}")
    for document_id, error in failures:
        typer.echo(f"  {document_id}: {error}")


@app.command("build-coding-queue")
def build_coding_queue(
    output_path: Annotated[Path, typer.Option(help="Versioned coding-queue CSV path.")] = (
        PROJECT_ROOT / "data" / "manual" / "pilot_coding_queue.csv"
    ),
    db_path: Annotated[Path, typer.Option(help="DuckDB database path.")] = DEFAULT_DB_PATH,
) -> None:
    """Create the primary pilot's human-review queue from parsed evidence."""

    with duckdb.connect(str(db_path), read_only=True) as connection:
        queue = connection.sql(
            """
            SELECT
                d.document_id AS coding_queue_id,
                d.event_id,
                e.season,
                e.event_name,
                d.title,
                d.document_url AS source_url,
                t.driver_number,
                t.driver_name,
                t.session_type,
                t.incident_time_raw,
                t.fact_text,
                t.decision_text,
                CASE
                    WHEN lower(t.decision_text) LIKE '%no further action%'
                        THEN 'no_further_action'
                    WHEN lower(t.decision_text) LIKE '%time penalty%'
                        THEN 'time_penalty'
                    WHEN lower(t.decision_text) LIKE '%warning%'
                        THEN 'warning'
                    WHEN lower(t.decision_text) LIKE '%grid position%'
                        THEN 'grid_penalty'
                    ELSE 'review_required'
                END AS outcome_family_suggestion,
                CASE
                    WHEN regexp_matches(lower(coalesce(t.fact_text, '') || ' ' || d.title),
                                        'caus(e|ing).*collision|collision with')
                        THEN 'causing_collision'
                    WHEN regexp_matches(lower(coalesce(t.fact_text, '') || ' ' || d.title),
                                        'forc(e|ing).*off.*track')
                        THEN 'forcing_off_track'
                    WHEN d.event_id = '2019-aut'
                         AND regexp_matches(lower(coalesce(t.fact_text, '') || ' ' || d.title),
                                            'incident.*car 33.*car 16|incident.*car 16.*car 33')
                        THEN 'manual_family_review'
                    ELSE 'review_required'
                END AS incident_family_suggestion,
                try_cast(
                    nullif(
                        regexp_extract(
                            lower(t.decision_text),
                            '([0-9]+) second time penalty',
                            1
                        ),
                        ''
                    ) AS INTEGER
                ) AS penalty_seconds_suggestion,
                try_cast(
                    nullif(
                        regexp_extract(lower(t.decision_text), '([0-9]+) penalty point', 1),
                        ''
                    ) AS INTEGER
                ) AS penalty_points_suggestion,
                try_cast(
                    nullif(
                        regexp_extract(lower(t.decision_text), 'drop of ([0-9]+) grid', 1),
                        ''
                    ) AS INTEGER
                ) AS grid_places_suggestion,
                CASE
                    WHEN d.event_id = '2019-aut' AND t.driver_number = 16 THEN 33
                    WHEN d.event_id = '2019-aut' AND t.driver_number = 33 THEN 16
                    ELSE try_cast(
                        nullif(
                            regexp_extract(
                                lower(t.fact_text),
                                '(?:with|forcing) car\\s*([0-9]+)',
                                1
                            ),
                            ''
                        ) AS INTEGER
                    )
                END AS affected_driver_number_suggestion,
                try_cast(
                    nullif(regexp_extract(lower(t.reason_text), 'lap\\s+([0-9]+)', 1), '')
                    AS INTEGER
                ) AS lap_number_suggestion,
                try_cast(
                    nullif(regexp_extract(lower(t.fact_text), 'turn\\s+([0-9]+)', 1), '')
                    AS INTEGER
                ) AS turn_number_suggestion,
                '' AS incident_group_id,
                '' AS document_version_status,
                '' AS supersedes_document_id,
                '' AS incident_family_final,
                '' AS outcome_family_final,
                '' AS penalty_seconds,
                '' AS penalty_points,
                '' AS affected_driver_number,
                '' AS lap_number,
                '' AS turn_number,
                '' AS responsibility_share,
                '' AS evidence_video,
                '' AS evidence_telemetry,
                '' AS evidence_team_radio,
                '' AS guideline_clause,
                '' AS guideline_expected_outcome,
                '' AS conformance_status,
                '' AS include_primary,
                '' AS exclusion_reason,
                '' AS coder_id,
                '' AS review_status,
                '' AS analyst_notes
            FROM raw.document_text AS t
            JOIN raw.source_documents AS d USING (document_id)
            JOIN metadata.events AS e USING (event_id)
            WHERE t.session_type IN ('Race', 'Sprint')
              AND (
                  regexp_matches(
                      lower(coalesce(t.fact_text, '') || ' ' || d.title),
                      'collision|forc(e|ing).*off.*track|gaining.*advantage|' ||
                      'unsafe rejoin|moving under braking|multiple defensive'
                  )
                  OR (
                      d.event_id = '2019-aut'
                      AND regexp_matches(
                          lower(coalesce(t.fact_text, '') || ' ' || d.title),
                          'incident.*car 33.*car 16|incident.*car 16.*car 33'
                      )
                  )
              )
            ORDER BY e.season, d.published_at, d.title
            """
        ).df()
        lap_starts = connection.sql(
            """
            SELECT event_id, driver_number, lap_number, lap_start_timestamp
            FROM raw.fastf1_laps
            WHERE lap_start_timestamp IS NOT NULL
            ORDER BY event_id, driver_number, lap_start_timestamp
            """
        ).df()
    events = {event.pilot_id: event for event in load_pilot_events()}
    for index, row in queue.iterrows():
        existing_lap = row["lap_number_suggestion"]
        if (pd.notna(existing_lap) and str(existing_lap).strip()) or not row[
            "incident_time_raw"
        ]:
            continue
        event = events[row["event_id"]]
        incident_at = pd.Timestamp(
            f"{event.race_date.isoformat()} {row['incident_time_raw']}",
            tz=event.event_timezone,
        ).tz_convert("UTC")
        candidates = lap_starts[
            (lap_starts["event_id"] == row["event_id"])
            & (lap_starts["driver_number"] == row["driver_number"])
            & (lap_starts["lap_start_timestamp"] <= incident_at)
        ]
        if not candidates.empty:
            queue.at[index, "lap_number_suggestion"] = candidates.iloc[-1]["lap_number"]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    queue.to_csv(output_path, index=False)
    typer.echo(f"Wrote {len(queue)} candidate document versions to {output_path}")


@app.command("build-full-coding-queues")
def build_full_coding_queues(
    output_directory: Annotated[
        Path, typer.Option(help="Protected full-corpus seed-bundle directory.")
    ] = PROJECT_ROOT / "data" / "manual" / "full_corpus_seed",
    db_path: Annotated[Path, typer.Option(help="DuckDB database path.")] = DEFAULT_DB_PATH,
    settings_path: Annotated[
        Path, typer.Option(help="Frozen machine-suggestion rules.")
    ] = PROJECT_ROOT / "config" / "full_corpus_coding.yml",
    overwrite: Annotated[
        bool,
        typer.Option(
            help="Replace a differing seed bundle after an intentional source/config change."
        ),
    ] = False,
) -> None:
    """Build denominator-preserving document and adjudication seed queues."""

    settings = load_full_corpus_coding_settings(settings_path)
    with duckdb.connect(str(db_path), read_only=True) as connection:
        population = load_outcome_document_population(
            connection, settings["source_document_class"]
        )
    documents, candidates = build_full_corpus_coding_queues(population, settings)
    exclusion_qa = build_exclusion_qa_sample(documents, settings)
    manifest, statuses = write_full_corpus_seed_bundle(
        population,
        documents,
        candidates,
        exclusion_qa,
        output_directory,
        settings,
        settings_path,
        overwrite=overwrite,
    )
    typer.echo(
        f"Full-corpus seed bundle at {output_directory}: "
        f"{len(documents)} outcome labels, {len(candidates)} live decision seeds, "
        f"{len(exclusion_qa)} exclusion-QA rows"
    )
    typer.echo(
        "Files: " + ", ".join(f"{name}={status}" for name, status in statuses.items())
    )
    typer.echo(
        "Eligibility suggestions:\n"
        + pd.Series(manifest["eligibility_suggestion_counts"], name="documents").to_string()
    )


@app.command("audit-full-coding-queues")
def audit_full_coding_queues(
    output_directory: Annotated[
        Path, typer.Option(help="Full-corpus seed-bundle directory.")
    ] = PROJECT_ROOT / "data" / "manual" / "full_corpus_seed",
    db_path: Annotated[Path, typer.Option(help="DuckDB database path.")] = DEFAULT_DB_PATH,
    settings_path: Annotated[
        Path, typer.Option(help="Frozen machine-suggestion rules.")
    ] = PROJECT_ROOT / "config" / "full_corpus_coding.yml",
) -> None:
    """Verify that stored seed queues exactly reproduce from the current source warehouse."""

    settings = load_full_corpus_coding_settings(settings_path)
    with duckdb.connect(str(db_path), read_only=True) as connection:
        population = load_outcome_document_population(
            connection, settings["source_document_class"]
        )
    documents, candidates = build_full_corpus_coding_queues(population, settings)
    exclusion_qa = build_exclusion_qa_sample(documents, settings)
    audit = audit_full_corpus_seed_bundle(
        population,
        documents,
        candidates,
        exclusion_qa,
        output_directory,
        settings,
        settings_path,
    )
    typer.echo(audit.to_string(index=False))
    if not audit["status"].eq("pass").all():
        raise typer.Exit(code=1)


@app.command("parser-audit")
def parser_audit(
    db_path: Annotated[Path, typer.Option(help="DuckDB database path.")] = DEFAULT_DB_PATH,
) -> None:
    """Report section-extraction completeness and documents requiring review."""

    with duckdb.connect(str(db_path), read_only=True) as connection:
        summary = connection.sql(
            """
            SELECT
                d.event_id,
                t.content_document_class,
                count(*) AS parsed_documents,
                count(t.fact_text) AS fact_sections,
                count(t.infringement_text) AS infringement_sections,
                count(t.decision_text) AS decision_sections,
                count(t.reason_text) AS reason_sections
            FROM raw.document_text AS t
            JOIN raw.source_documents AS d USING (document_id)
            GROUP BY d.event_id, t.content_document_class
            ORDER BY d.event_id, t.content_document_class
            """
        ).df()
        review = connection.sql(
            """
            SELECT d.event_id, d.title, t.parser_warnings_json
            FROM raw.document_text AS t
            JOIN raw.source_documents AS d USING (document_id)
            WHERE t.content_document_class = 'steward_decision'
              AND CAST(t.parser_warnings_json AS VARCHAR) <> '[]'
            ORDER BY d.event_id, d.published_at
            """
        ).df()
    typer.echo(summary.to_string(index=False))
    typer.echo("\nManual-review queue:\n" + review.to_string(index=False))


@app.command("parser-sample")
def parser_sample(
    event_id: Annotated[str, typer.Option(help="Pilot event id to inspect.")],
    limit: Annotated[int, typer.Option(min=1, max=5, help="Number of samples.")] = 1,
    characters: Annotated[
        int, typer.Option(min=200, max=5000, help="Characters per sample.")
    ] = 2000,
    db_path: Annotated[Path, typer.Option(help="DuckDB database path.")] = DEFAULT_DB_PATH,
) -> None:
    """Print bounded raw-text samples for parser development."""

    with duckdb.connect(str(db_path), read_only=True) as connection:
        samples = connection.execute(
            """
            SELECT d.title, t.raw_text
            FROM raw.document_text AS t
            JOIN raw.source_documents AS d USING (document_id)
            WHERE d.event_id = ?
            ORDER BY d.published_at DESC
            LIMIT ?
            """,
            [event_id, limit],
        ).fetchall()
    for title, raw_text in samples:
        typer.echo(f"\n--- {title} ---\n{raw_text[:characters]}")


@app.command("quality-check")
def quality_check(
    db_path: Annotated[Path, typer.Option(help="DuckDB database path.")] = DEFAULT_DB_PATH,
    checks_path: Annotated[Path, typer.Option(help="Zero-row checks SQL path.")] = (
        PROJECT_ROOT / "sql" / "quality_checks.sql"
    ),
) -> None:
    """Run each release quality query and fail if any returns rows."""

    failures = 0
    with duckdb.connect(str(db_path), read_only=True) as connection:
        for number, statement in enumerate(
            _sql_statements(checks_path.read_text(encoding="utf-8")), start=1
        ):
            result = connection.sql(statement).df()
            if result.empty:
                typer.echo(f"check {number}: pass")
            else:
                failures += 1
                typer.echo(f"check {number}: FAIL ({len(result)} rows)\n{result}")
    if failures:
        raise typer.Exit(code=1)


@app.command("pilot-fastf1")
def pilot_fastf1(
    event_id: Annotated[
        str | None, typer.Option(help="One pilot id; default loads all missing events.")
    ] = None,
    db_path: Annotated[Path, typer.Option(help="DuckDB database path.")] = DEFAULT_DB_PATH,
) -> None:
    """Load pilot Race results, laps, and race-control messages from FastF1."""

    initialize_database(db_path)
    events = load_pilot_events()
    if event_id:
        events = [event for event in events if event.pilot_id == event_id]
        if not events:
            raise typer.BadParameter(f"Unknown pilot id: {event_id}")
    with connect(db_path) as connection:
        loaded_ids = {
            row[0]
            for row in connection.sql("SELECT DISTINCT event_id FROM raw.fastf1_results").fetchall()
        }
    if not event_id:
        events = [event for event in events if event.pilot_id not in loaded_ids]

    for event in events:
        typer.echo(f"Loading FastF1 Race data for {event.pilot_id}...")
        results, laps, messages = fetch_pilot_race(
            event,
            PROJECT_ROOT / "data" / "cache" / "fastf1",
            PROJECT_ROOT / "data" / "external" / "fastf1",
        )
        with connect(db_path) as connection:
            replace_event_enrichment(connection, event.pilot_id, results, laps, messages)
        typer.echo(
            f"{event.pilot_id}: {len(results)} results, {len(laps)} laps, "
            f"{len(messages)} race-control messages"
        )


@app.command("pilot-messages")
def pilot_messages(
    event_id: Annotated[str, typer.Option(help="Pilot event id.")],
    pattern: Annotated[
        str, typer.Option(help="Case-insensitive regular expression for message text.")
    ] = "incident|collision|forcing|noted|investigation",
    db_path: Annotated[Path, typer.Option(help="DuckDB database path.")] = DEFAULT_DB_PATH,
) -> None:
    """Inspect bounded race-control evidence for pilot incident coding."""

    with duckdb.connect(str(db_path), read_only=True) as connection:
        messages = connection.execute(
            """
            SELECT
                message_timestamp,
                lap_number,
                category,
                racing_number,
                message
            FROM raw.fastf1_race_control_messages
            WHERE event_id = ?
              AND regexp_matches(lower(coalesce(message, '')), lower(?))
            ORDER BY message_timestamp, message_time_seconds
            """,
            [event_id, pattern],
        ).df()
    typer.echo(messages.to_string(index=False))


@app.command("pilot-results")
def pilot_results(
    event_id: Annotated[str, typer.Option(help="Pilot event id.")],
    db_path: Annotated[Path, typer.Option(help="DuckDB database path.")] = DEFAULT_DB_PATH,
) -> None:
    """Inspect normalized pilot Race classifications."""

    with duckdb.connect(str(db_path), read_only=True) as connection:
        results = connection.execute(
            """
            SELECT
                finish_position,
                driver_number,
                abbreviation,
                driver_name,
                grid_position,
                laps_completed,
                result_time_seconds,
                classification_gap_seconds,
                status,
                points
            FROM raw.fastf1_results
            WHERE event_id = ?
            ORDER BY finish_position
            """,
            [event_id],
        ).df()
    typer.echo(results.to_string(index=False))


@app.command("pilot-lap-window")
def pilot_lap_window(
    event_id: Annotated[str, typer.Option(help="Pilot event id.")],
    driver_number: Annotated[int, typer.Option(help="Driver racing number.")],
    local_time: Annotated[str, typer.Option(help="Official incident time as HH:MM.")],
    db_path: Annotated[Path, typer.Option(help="DuckDB database path.")] = DEFAULT_DB_PATH,
) -> None:
    """Show the five lap starts nearest an official local incident time."""

    events = {event.pilot_id: event for event in load_pilot_events()}
    if event_id not in events:
        raise typer.BadParameter(f"Unknown pilot id: {event_id}")
    event = events[event_id]
    incident_at = pd.Timestamp(
        f"{event.race_date.isoformat()} {local_time}", tz=event.event_timezone
    ).tz_convert("UTC")
    with duckdb.connect(str(db_path), read_only=True) as connection:
        laps = connection.execute(
            """
            SELECT
                lap_number,
                lap_start_timestamp,
                date_diff('second', lap_start_timestamp, ?) AS seconds_after_lap_start
            FROM raw.fastf1_laps
            WHERE event_id = ?
              AND driver_number = ?
              AND lap_start_timestamp IS NOT NULL
            ORDER BY abs(date_diff('second', lap_start_timestamp, ?))
            LIMIT 5
            """,
            [incident_at, event_id, driver_number, incident_at],
        ).df()
    typer.echo(f"Incident UTC: {incident_at}\n{laps.to_string(index=False)}")


@app.command("validate-coding")
def validate_coding(
    coding_path: Annotated[Path, typer.Option(help="Reviewable adjudication CSV.")] = (
        PROJECT_ROOT / "data" / "manual" / "pilot_coded_adjudications.csv"
    ),
) -> None:
    """Validate reviewable records and cross-record uniqueness."""

    frame = pd.read_csv(coding_path)
    records = []
    for row_number, row in frame.iterrows():
        payload = {key: None if pd.isna(value) else value for key, value in row.to_dict().items()}
        try:
            records.append(CodedAdjudication.model_validate(payload))
        except ValueError as exc:
            typer.echo(f"row {row_number + 2}: {exc}")
            raise typer.Exit(code=1) from exc
    ids = [record.adjudication_id for record in records]
    if len(ids) != len(set(ids)):
        typer.echo("duplicate adjudication_id detected")
        raise typer.Exit(code=1)
    incidents = len({record.incident_id for record in records})
    pending = sum(record.review_status == "single_coded_pending_human" for record in records)
    typer.echo(
        f"Validated {len(records)} adjudications across {incidents} incidents; "
        f"pending independent human review: {pending}"
    )


@app.command("validate-impact")
def validate_impact(
    impact_path: Annotated[Path, typer.Option(help="Competitive-impact assessment CSV.")] = (
        PROJECT_ROOT / "data" / "manual" / "pilot_impact_assessments.csv"
    ),
    coding_path: Annotated[Path, typer.Option(help="Coded adjudication CSV.")] = (
        PROJECT_ROOT / "data" / "manual" / "pilot_coded_adjudications.csv"
    ),
    db_path: Annotated[Path, typer.Option(help="DuckDB database path.")] = DEFAULT_DB_PATH,
) -> None:
    """Validate impact tiers and reproduce every claimed mechanical position change."""

    frame = pd.read_csv(impact_path)
    records = []
    for row_number, row in frame.iterrows():
        payload = {key: None if pd.isna(value) else value for key, value in row.to_dict().items()}
        try:
            records.append(ImpactAssessment.model_validate(payload))
        except ValueError as exc:
            typer.echo(f"row {row_number + 2}: {exc}")
            raise typer.Exit(code=1) from exc

    coded_ids = set(pd.read_csv(coding_path)["adjudication_id"])
    missing_adjudications = sorted(
        record.adjudication_id for record in records if record.adjudication_id not in coded_ids
    )
    if missing_adjudications:
        typer.echo(f"unknown adjudication ids: {', '.join(missing_adjudications)}")
        raise typer.Exit(code=1)

    mechanical = [record for record in records if record.impact_level == "mechanical"]
    with duckdb.connect(str(db_path), read_only=True) as connection:
        known_documents = {
            row[0]
            for row in connection.sql(
                "SELECT document_id FROM raw.source_documents"
            ).fetchall()
        }
        for record in records:
            for document_id in (
                record.source_document_id,
                record.classification_source_document_id,
            ):
                if document_id not in known_documents:
                    typer.echo(f"unknown source document id: {document_id}")
                    raise typer.Exit(code=1)
        for record in mechanical:
            event_results = connection.execute(
                """
                SELECT
                    driver_number,
                    finish_position,
                    laps_completed,
                    classification_gap_seconds
                FROM raw.fastf1_results
                WHERE event_id = ?
                """,
                [record.event_id],
            ).df()
            calculated = remove_post_race_time_penalty(
                event_results,
                record.driver_number,
                record.penalty_seconds,
            )
            if (
                calculated.official_finish_position != record.official_finish_position
                or calculated.counterfactual_finish_position
                != record.counterfactual_finish_position
                or calculated.positions_gained_without_penalty
                != record.positions_gained_without_penalty
            ):
                typer.echo(f"mechanical impact mismatch: {record.impact_assessment_id}")
                raise typer.Exit(code=1)
    pending = sum(record.review_status == "single_coded_pending_human" for record in records)
    typer.echo(
        f"Validated {len(records)} impact assessments; reproduced {len(mechanical)} mechanical "
        f"calculations; pending independent human review: {pending}"
    )


@app.command("validate-harm")
def validate_harm(
    harm_path: Annotated[Path, typer.Option(help="Affected-driver harm assessment CSV.")] = (
        PROJECT_ROOT / "data" / "manual" / "pilot_harm_assessments.csv"
    ),
    coding_path: Annotated[Path, typer.Option(help="Coded adjudication CSV.")] = (
        PROJECT_ROOT / "data" / "manual" / "pilot_coded_adjudications.csv"
    ),
    db_path: Annotated[Path, typer.Option(help="DuckDB database path.")] = DEFAULT_DB_PATH,
) -> None:
    """Validate harm evidence and reproduce observed position and relative-time changes."""

    frame = pd.read_csv(harm_path)
    records = []
    for row_number, row in frame.iterrows():
        payload = {key: None if pd.isna(value) else value for key, value in row.to_dict().items()}
        try:
            records.append(HarmAssessment.model_validate(payload))
        except ValueError as exc:
            typer.echo(f"row {row_number + 2}: {exc}")
            raise typer.Exit(code=1) from exc
    ids = [record.harm_assessment_id for record in records]
    if len(ids) != len(set(ids)):
        typer.echo("duplicate harm_assessment_id detected")
        raise typer.Exit(code=1)

    coded = pd.read_csv(coding_path).set_index("adjudication_id")
    with duckdb.connect(str(db_path), read_only=True) as connection:
        known_documents = {
            row[0]
            for row in connection.sql(
                "SELECT document_id FROM raw.source_documents"
            ).fetchall()
        }
        for record in records:
            if record.adjudication_id not in coded.index:
                typer.echo(f"unknown adjudication id: {record.adjudication_id}")
                raise typer.Exit(code=1)
            adjudication = coded.loc[record.adjudication_id]
            if (
                int(adjudication["accused_driver_number"]) != record.counterparty_driver_number
                or int(adjudication["affected_driver_number"]) != record.affected_driver_number
            ):
                typer.echo(f"driver-role mismatch: {record.harm_assessment_id}")
                raise typer.Exit(code=1)
            for document_id in (
                record.source_document_id,
                record.classification_source_document_id,
            ):
                if document_id not in known_documents:
                    typer.echo(f"unknown source document id: {document_id}")
                    raise typer.Exit(code=1)

            incident_lap = int(adjudication["lap_number"])
            if record.net_positions_lost_observed is not None:
                position_start_lap = record.position_window_start_lap or incident_lap - 1
                position_end_lap = record.position_window_end_lap or incident_lap
                if position_start_lap < 1:
                    typer.echo(f"invalid position window: {record.harm_assessment_id}")
                    raise typer.Exit(code=1)
                positions = connection.execute(
                    """
                    SELECT CAST(lap_number AS INTEGER) AS lap_number, CAST(position AS INTEGER)
                    FROM raw.fastf1_laps
                    WHERE event_id = ? AND driver_number = ?
                      AND lap_number IN (?, ?)
                    ORDER BY lap_number
                    """,
                    [
                        record.event_id,
                        record.affected_driver_number,
                        position_start_lap,
                        position_end_lap,
                    ],
                ).fetchall()
                if positions != [
                    (position_start_lap, record.position_before),
                    (position_end_lap, record.position_after),
                ]:
                    typer.echo(f"observed position mismatch: {record.harm_assessment_id}")
                    raise typer.Exit(code=1)

            if record.affected_relative_time_loss_seconds is not None:
                comparator_driver = (
                    record.relative_time_comparator_driver_number
                    or record.counterparty_driver_number
                )
                time_start_lap = record.relative_time_window_start_lap or incident_lap
                time_end_lap = record.relative_time_window_end_lap or incident_lap + 1
                starts = connection.execute(
                    """
                    SELECT driver_number, CAST(lap_number AS INTEGER), lap_start_time_seconds
                    FROM raw.fastf1_laps
                    WHERE event_id = ? AND driver_number IN (?, ?)
                      AND lap_number IN (?, ?)
                    """,
                    [
                        record.event_id,
                        record.affected_driver_number,
                        comparator_driver,
                        time_start_lap,
                        time_end_lap,
                    ],
                ).fetchall()
                start_by_driver_lap = {
                    (driver_number, lap_number): lap_start
                    for driver_number, lap_number, lap_start in starts
                }
                affected_before = start_by_driver_lap[
                    (record.affected_driver_number, time_start_lap)
                ]
                counterparty_before = start_by_driver_lap[
                    (comparator_driver, time_start_lap)
                ]
                affected_after = start_by_driver_lap[
                    (record.affected_driver_number, time_end_lap)
                ]
                counterparty_after = start_by_driver_lap[
                    (comparator_driver, time_end_lap)
                ]
                reproduced = (counterparty_before - affected_before) - (
                    counterparty_after - affected_after
                )
                if abs(reproduced - record.affected_relative_time_loss_seconds) > 0.001:
                    typer.echo(f"relative-time mismatch: {record.harm_assessment_id}")
                    raise typer.Exit(code=1)

    pending = sum(record.review_status == "single_coded_pending_human" for record in records)
    typer.echo(
        f"Validated {len(records)} harm assessments with observed timing arithmetic; "
        f"pending independent human review: {pending}"
    )


@app.command("validate-extensions")
def validate_extensions(
    coding_path: Annotated[Path, typer.Option(help="Reviewable adjudication CSV.")] = (
        PROJECT_ROOT / "data" / "manual" / "pilot_coded_adjudications.csv"
    ),
    impact_path: Annotated[Path, typer.Option(help="Impact-assessment CSV.")] = (
        PROJECT_ROOT / "data" / "manual" / "pilot_impact_assessments.csv"
    ),
    harm_path: Annotated[Path, typer.Option(help="Affected-driver harm CSV.")] = (
        PROJECT_ROOT / "data" / "manual" / "pilot_harm_assessments.csv"
    ),
    location_path: Annotated[Path, typer.Option(help="Incident-location CSV.")] = (
        PROJECT_ROOT / "data" / "manual" / "pilot_incident_locations.csv"
    ),
    relation_path: Annotated[Path, typer.Option(help="Incident-relation CSV.")] = (
        PROJECT_ROOT / "data" / "manual" / "pilot_incident_relations.csv"
    ),
    cross_event_path: Annotated[Path, typer.Option(help="Cross-event sanction CSV.")] = (
        PROJECT_ROOT / "data" / "manual" / "pilot_cross_event_sanction_effects.csv"
    ),
    review_path: Annotated[Path, typer.Option(help="Independent-review CSV.")] = (
        PROJECT_ROOT / "data" / "manual" / "pilot_independent_review.csv"
    ),
) -> None:
    """Validate extension contracts, lineage, relation chains, and review coverage."""

    try:
        records = load_pilot_manual_records(
            coding_path,
            impact_path,
            harm_path,
            location_path,
            relation_path,
            cross_event_path,
            review_path,
        )
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc
    pending = sum(record.review_status == "pending" for record in records.reviews)
    typer.echo(
        f"Validated extensions: {len(records.harms)} harms, "
        f"{len(records.locations)} locations, {len(records.relations)} relation edges, "
        f"{len(records.cross_event_effects)} cross-event effects; "
        f"pending independent human review: {pending}"
    )


@app.command("review-status")
def review_status(
    review_path: Annotated[Path, typer.Option(help="Independent-review CSV.")] = (
        PROJECT_ROOT / "data" / "manual" / "pilot_independent_review.csv"
    ),
    coding_path: Annotated[Path, typer.Option(help="Reviewable adjudication CSV.")] = (
        PROJECT_ROOT / "data" / "manual" / "pilot_coded_adjudications.csv"
    ),
    impact_path: Annotated[Path, typer.Option(help="Competitive-impact assessment CSV.")] = (
        PROJECT_ROOT / "data" / "manual" / "pilot_impact_assessments.csv"
    ),
    harm_path: Annotated[Path, typer.Option(help="Affected-driver harm assessment CSV.")] = (
        PROJECT_ROOT / "data" / "manual" / "pilot_harm_assessments.csv"
    ),
    location_path: Annotated[Path, typer.Option(help="Incident-location CSV.")] = (
        PROJECT_ROOT / "data" / "manual" / "pilot_incident_locations.csv"
    ),
    relation_path: Annotated[Path, typer.Option(help="Incident-relation CSV.")] = (
        PROJECT_ROOT / "data" / "manual" / "pilot_incident_relations.csv"
    ),
    cross_event_path: Annotated[Path, typer.Option(help="Cross-event sanction CSV.")] = (
        PROJECT_ROOT / "data" / "manual" / "pilot_cross_event_sanction_effects.csv"
    ),
) -> None:
    """Validate the independent review file and report completion and effort."""

    frame = pd.read_csv(review_path)
    records = []
    for row_number, row in frame.iterrows():
        payload = {key: None if pd.isna(value) else value for key, value in row.to_dict().items()}
        try:
            records.append(IndependentReviewRecord.model_validate(payload))
        except ValueError as exc:
            typer.echo(f"row {row_number + 2}: {exc}")
            raise typer.Exit(code=1) from exc
    review_ids = [record.review_id for record in records]
    if len(review_ids) != len(set(review_ids)):
        typer.echo("duplicate review_id detected")
        raise typer.Exit(code=1)
    target_pairs = [(record.target_type, record.target_id) for record in records]
    if len(target_pairs) != len(set(target_pairs)):
        typer.echo("duplicate review target detected")
        raise typer.Exit(code=1)

    expected = {
        *(
            ("adjudication", target_id)
            for target_id in pd.read_csv(coding_path)["adjudication_id"]
        ),
        *(
            ("impact_assessment", target_id)
            for target_id in pd.read_csv(impact_path)["impact_assessment_id"]
        ),
        *(
            ("harm_assessment", target_id)
            for target_id in pd.read_csv(harm_path)["harm_assessment_id"]
        ),
        *(
            ("incident_location", target_id)
            for target_id in pd.read_csv(location_path)["location_id"]
        ),
        *(
            ("incident_relation", target_id)
            for target_id in pd.read_csv(relation_path)["relation_id"]
        ),
        *(
            ("cross_event_sanction_effect", target_id)
            for target_id in pd.read_csv(cross_event_path)["cross_event_effect_id"]
        ),
    }
    actual = set(target_pairs)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        typer.echo(f"review target mismatch; missing={missing}; extra={extra}")
        raise typer.Exit(code=1)

    completed = [record for record in records if record.review_status != "pending"]
    minutes = sum(record.review_minutes or 0 for record in completed)
    decisions = pd.Series(
        [record.review_status for record in completed], dtype="string"
    ).value_counts()
    typer.echo(
        f"Independent review: {len(completed)}/{len(records)} complete; "
        f"recorded effort: {minutes:.1f} minutes"
    )
    if not decisions.empty:
        typer.echo(decisions.to_string())


@app.command("reconcile-pilot")
def reconcile_pilot(
    review_path: Annotated[Path, typer.Option(help="Completed independent-review CSV.")] = (
        PROJECT_ROOT / "data" / "manual" / "pilot_independent_review.csv"
    ),
    coding_path: Annotated[Path, typer.Option(help="First-pass adjudication CSV.")] = (
        PROJECT_ROOT / "data" / "manual" / "pilot_coded_adjudications.csv"
    ),
    impact_path: Annotated[Path, typer.Option(help="First-pass impact-assessment CSV.")] = (
        PROJECT_ROOT / "data" / "manual" / "pilot_impact_assessments.csv"
    ),
    harm_path: Annotated[Path, typer.Option(help="First-pass harm-assessment CSV.")] = (
        PROJECT_ROOT / "data" / "manual" / "pilot_harm_assessments.csv"
    ),
    location_path: Annotated[Path, typer.Option(help="First-pass incident-location CSV.")] = (
        PROJECT_ROOT / "data" / "manual" / "pilot_incident_locations.csv"
    ),
    relation_path: Annotated[Path, typer.Option(help="First-pass incident-relation CSV.")] = (
        PROJECT_ROOT / "data" / "manual" / "pilot_incident_relations.csv"
    ),
    cross_event_path: Annotated[
        Path, typer.Option(help="First-pass cross-event sanction CSV.")
    ] = PROJECT_ROOT / "data" / "manual" / "pilot_cross_event_sanction_effects.csv",
    output_root: Annotated[
        Path, typer.Option(help="Parent for immutable content-addressed outputs.")
    ] = PROJECT_ROOT / "data" / "manual" / "reconciled",
) -> None:
    """Create validated reconciled versions without changing first-pass inputs."""

    try:
        bundle = build_pilot_reconciliation(
            coding_path,
            impact_path,
            harm_path,
            location_path,
            relation_path,
            cross_event_path,
            review_path,
        )
        output_directory, created = write_reconciliation_bundle(bundle, output_root)
    except (ValueError, FileExistsError) as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc
    action = "Created" if created else "Verified existing"
    typer.echo(
        f"{action} reconciliation {bundle.reconciliation_id} at {output_directory}; "
        f"{len(bundle.adjudications)} adjudications, {len(bundle.impacts)} impacts, "
        f"{len(bundle.harms)} harms, {len(bundle.locations)} locations, "
        f"{len(bundle.relations)} relation edges, "
        f"{len(bundle.cross_event_effects)} cross-event effects, "
        f"{bundle.manifest['field_correction_count']} corrected fields"
    )


@app.command("export-snowflake-pilot")
def export_snowflake_pilot_command(
    output_root: Annotated[
        Path, typer.Option(help="Parent for content-addressed Parquet exports.")
    ] = PROJECT_ROOT / "data" / "processed" / "snowflake_pilot",
    coding_path: Annotated[Path, typer.Option(help="Adjudication CSV to export.")] = (
        PROJECT_ROOT / "data" / "manual" / "pilot_coded_adjudications.csv"
    ),
    impact_path: Annotated[Path, typer.Option(help="Impact-assessment CSV to export.")] = (
        PROJECT_ROOT / "data" / "manual" / "pilot_impact_assessments.csv"
    ),
    harm_path: Annotated[Path, typer.Option(help="Harm-assessment CSV to export.")] = (
        PROJECT_ROOT / "data" / "manual" / "pilot_harm_assessments.csv"
    ),
    location_path: Annotated[Path, typer.Option(help="Incident-location CSV to export.")] = (
        PROJECT_ROOT / "data" / "manual" / "pilot_incident_locations.csv"
    ),
    relation_path: Annotated[Path, typer.Option(help="Incident-relation CSV to export.")] = (
        PROJECT_ROOT / "data" / "manual" / "pilot_incident_relations.csv"
    ),
    cross_event_path: Annotated[
        Path, typer.Option(help="Cross-event sanction CSV to export.")
    ] = PROJECT_ROOT / "data" / "manual" / "pilot_cross_event_sanction_effects.csv",
    review_path: Annotated[Path, typer.Option(help="Independent-review CSV to export.")] = (
        PROJECT_ROOT / "data" / "manual" / "pilot_independent_review.csv"
    ),
    db_path: Annotated[Path, typer.Option(help="DuckDB database path.")] = DEFAULT_DB_PATH,
) -> None:
    """Export a validated pilot package for upload through Snowsight."""

    try:
        with duckdb.connect(str(db_path), read_only=True) as connection:
            result = export_snowflake_pilot(
                connection,
                PROJECT_ROOT,
                output_root,
                coding_path,
                impact_path,
                harm_path,
                location_path,
                relation_path,
                cross_event_path,
                review_path,
            )
    except (ValueError, FileExistsError) as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc
    action = "Created" if result.created else "Verified existing"
    typer.echo(
        f"{action} {result.export_id} at {result.output_directory}; "
        f"{result.manifest['table_count']} Parquet tables; "
        f"status={result.manifest['release_status']}"
    )


@app.command("validate-snowflake-export")
def validate_snowflake_export_command(
    export_directory: Annotated[Path, typer.Argument(help="Export directory to verify.")],
) -> None:
    """Verify a local Snowflake export's hashes, row counts, and columns."""

    try:
        validation = validate_snowflake_export(export_directory)
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc
    typer.echo(validation.to_string(index=False))
    if not validation.status.eq("pass").all():
        raise typer.Exit(code=1)
    typer.echo(f"Validated {len(validation)} Snowflake export tables")


@app.command("scale-readiness")
def scale_readiness(
    review_path: Annotated[Path, typer.Option(help="Independent-review CSV.")] = (
        PROJECT_ROOT / "data" / "manual" / "pilot_independent_review.csv"
    ),
    coding_path: Annotated[Path, typer.Option(help="Reviewable adjudication CSV.")] = (
        PROJECT_ROOT / "data" / "manual" / "pilot_coded_adjudications.csv"
    ),
    impact_path: Annotated[Path, typer.Option(help="Competitive-impact assessment CSV.")] = (
        PROJECT_ROOT / "data" / "manual" / "pilot_impact_assessments.csv"
    ),
    harm_path: Annotated[Path, typer.Option(help="Affected-driver harm assessment CSV.")] = (
        PROJECT_ROOT / "data" / "manual" / "pilot_harm_assessments.csv"
    ),
    location_path: Annotated[Path, typer.Option(help="Incident-location CSV.")] = (
        PROJECT_ROOT / "data" / "manual" / "pilot_incident_locations.csv"
    ),
    relation_path: Annotated[Path, typer.Option(help="Incident-relation CSV.")] = (
        PROJECT_ROOT / "data" / "manual" / "pilot_incident_relations.csv"
    ),
    cross_event_path: Annotated[Path, typer.Option(help="Cross-event sanction CSV.")] = (
        PROJECT_ROOT / "data" / "manual" / "pilot_cross_event_sanction_effects.csv"
    ),
    output_path: Annotated[Path | None, typer.Option(help="Optional CSV snapshot path.")] = None,
    db_path: Annotated[Path, typer.Option(help="DuckDB database path.")] = DEFAULT_DB_PATH,
) -> None:
    """Evaluate measured pilot gates without automating the final scope decision."""

    try:
        records = load_pilot_manual_records(
            coding_path,
            impact_path,
            harm_path,
            location_path,
            relation_path,
            cross_event_path,
            review_path,
        )
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc
    with duckdb.connect(str(db_path), read_only=True) as connection:
        gates = evaluate_pilot_readiness(
            connection,
            records.adjudications,
            records.impacts,
            records.harms,
            records.reviews,
            load_analysis_thresholds(),
        )
    typer.echo(gates.to_string(index=False))
    typer.echo(f"\nOverall: {readiness_decision(gates)}")
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        gates.to_csv(output_path, index=False)
        typer.echo(f"Wrote {output_path}")


@app.command("build-explorer")
def build_explorer(
    coding_path: Annotated[Path, typer.Option(help="Reviewable adjudication CSV.")] = (
        PROJECT_ROOT / "data" / "manual" / "pilot_coded_adjudications.csv"
    ),
    impact_path: Annotated[Path, typer.Option(help="Competitive-impact assessment CSV.")] = (
        PROJECT_ROOT / "data" / "manual" / "pilot_impact_assessments.csv"
    ),
    harm_path: Annotated[Path, typer.Option(help="Affected-driver harm assessment CSV.")] = (
        PROJECT_ROOT / "data" / "manual" / "pilot_harm_assessments.csv"
    ),
    location_path: Annotated[Path, typer.Option(help="Incident-location CSV.")] = (
        PROJECT_ROOT / "data" / "manual" / "pilot_incident_locations.csv"
    ),
    relation_path: Annotated[Path, typer.Option(help="Incident-relation CSV.")] = (
        PROJECT_ROOT / "data" / "manual" / "pilot_incident_relations.csv"
    ),
    cross_event_path: Annotated[Path, typer.Option(help="Cross-event sanction CSV.")] = (
        PROJECT_ROOT / "data" / "manual" / "pilot_cross_event_sanction_effects.csv"
    ),
    review_path: Annotated[Path, typer.Option(help="Independent-review CSV.")] = (
        PROJECT_ROOT / "data" / "manual" / "pilot_independent_review.csv"
    ),
    output_path: Annotated[Path, typer.Option(help="Standalone HTML output path.")] = (
        PROJECT_ROOT / "explorer" / "index.html"
    ),
    db_path: Annotated[Path, typer.Option(help="DuckDB database path.")] = DEFAULT_DB_PATH,
) -> None:
    """Build the standalone evidence explorer from validated pilot evidence."""

    with duckdb.connect(str(db_path), read_only=True) as connection:
        payload = build_explorer_payload(
            connection,
            PROJECT_ROOT,
            coding_path,
            impact_path,
            harm_path,
            location_path,
            relation_path,
            cross_event_path,
            review_path,
        )
    write_explorer(payload, output_path)
    typer.echo(
        f"Wrote {output_path} with {len(payload['adjudications'])} adjudications, "
        f"{len(payload['impacts'])} impact assessments, and "
        f"{len(payload['harms'])} harm assessments, "
        f"{len(payload['locations'])} locations, "
        f"{len(payload['relations'])} relation edges, and "
        f"{len(payload['cross_event_effects'])} cross-event effects; "
        f"status={payload['metadata']['release_status']}"
    )


if __name__ == "__main__":
    app()
