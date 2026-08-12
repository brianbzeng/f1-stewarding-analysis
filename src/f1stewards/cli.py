"""Command-line entry points for reproducible pipeline operations."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import duckdb
import typer

from f1stewards.acquisition.fia import (
    build_client,
    discover_event,
    download_documents,
    write_manifest,
)
from f1stewards.config import PROJECT_ROOT, load_document_classes, load_pilot_events
from f1stewards.models import DocumentClass
from f1stewards.parsing.decision import parse_decision_pdf
from f1stewards.warehouse import (
    DEFAULT_DB_PATH,
    connect,
    initialize_database,
    upsert_document_text,
    upsert_pilot_events,
    upsert_source_documents,
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
            (
                PROJECT_ROOT
                / "data"
                / "raw"
                / "fia"
                / str(document.season)
                / document.pilot_id
            ).glob(f"{document.document_id}-*.pdf")
        )
        if len(local_matches) == 1:
            local_path = local_matches[0]
            content = local_path.read_bytes()
            hydrated.append(
                document.model_copy(
                    update={
                        "retrieved_at": datetime.fromtimestamp(
                            local_path.stat().st_mtime, tz=UTC
                        ),
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


@app.command("init-db")
def init_db(
    db_path: Annotated[Path, typer.Option(help="DuckDB database path.")] = DEFAULT_DB_PATH,
) -> None:
    """Create the empty analytical schema and register pilot events."""

    initialize_database(db_path)
    events = load_pilot_events()
    with connect(db_path) as connection:
        upsert_pilot_events(connection, events)
    typer.echo(f"Initialized {db_path} with {len(events)} pilot events")


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
    all_documents = []
    with build_client() as client:
        for event in events:
            documents = discover_event(client, event, classes)
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
                downloaded = download_documents(
                    client, selected, PROJECT_ROOT / "data" / "raw"
                )
                downloaded_by_id = {
                    document.document_id: document for document in downloaded
                }
                documents = [
                    downloaded_by_id.get(document.document_id, document)
                    for document in documents
                ]
                failures = sum(document.retrieval_error is not None for document in downloaded)
                typer.echo(
                    f"{event.pilot_id}: downloaded {len(downloaded) - failures}; "
                    f"failures {failures}"
                )
            all_documents.extend(documents)

    write_manifest(all_documents, manifest_path)
    initialize_database(db_path)
    with connect(db_path) as connection:
        upsert_pilot_events(connection, events)
        upsert_source_documents(connection, all_documents)
    typer.echo(f"Wrote {len(all_documents)} lineage rows to {manifest_path} and {db_path}")


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
                SELECT event_id, title, document_url
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
    output_path.parent.mkdir(parents=True, exist_ok=True)
    queue.to_csv(output_path, index=False)
    typer.echo(f"Wrote {len(queue)} candidate document versions to {output_path}")


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
                count(*) AS parsed_documents,
                count(t.fact_text) AS fact_sections,
                count(t.infringement_text) AS infringement_sections,
                count(t.decision_text) AS decision_sections,
                count(t.reason_text) AS reason_sections
            FROM raw.document_text AS t
            JOIN raw.source_documents AS d USING (document_id)
            GROUP BY d.event_id
            ORDER BY d.event_id
            """
        ).df()
        review = connection.sql(
            """
            SELECT d.event_id, d.title, t.parser_warnings_json
            FROM raw.document_text AS t
            JOIN raw.source_documents AS d USING (document_id)
            WHERE CAST(t.parser_warnings_json AS VARCHAR) <> '[]'
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


if __name__ == "__main__":
    app()
