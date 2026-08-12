"""Command-line entry points for reproducible pipeline operations."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import duckdb
import pandas as pd
import typer

from f1stewards.acquisition.fia import (
    build_client,
    discover_event,
    download_documents,
    write_manifest,
)
from f1stewards.config import (
    PROJECT_ROOT,
    load_document_classes,
    load_pilot_events,
    load_regulatory_sources,
)
from f1stewards.enrichment.fastf1 import fetch_pilot_race, replace_event_enrichment
from f1stewards.impact import remove_post_race_time_penalty
from f1stewards.manual import CodedAdjudication, ImpactAssessment, IndependentReviewRecord
from f1stewards.models import DocumentClass
from f1stewards.parsing.decision import parse_decision_pdf
from f1stewards.warehouse import (
    DEFAULT_DB_PATH,
    connect,
    initialize_database,
    replace_claim_ledger,
    upsert_document_text,
    upsert_pilot_events,
    upsert_regulatory_sources,
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


@app.command("init-db")
def init_db(
    db_path: Annotated[Path, typer.Option(help="DuckDB database path.")] = DEFAULT_DB_PATH,
) -> None:
    """Create the empty analytical schema and register pilot events."""

    initialize_database(db_path)
    events = load_pilot_events()
    regulatory_sources = load_regulatory_sources()
    with connect(db_path) as connection:
        upsert_pilot_events(connection, events)
        upsert_regulatory_sources(connection, regulatory_sources)
        claim_count = replace_claim_ledger(connection)
    typer.echo(
        f"Initialized {db_path} with {len(events)} pilot events and "
        f"{len(regulatory_sources)} regulatory sources; loaded {claim_count} report claims"
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
                downloaded = download_documents(client, selected, PROJECT_ROOT / "data" / "raw")
                downloaded_by_id = {document.document_id: document for document in downloaded}
                documents = [
                    downloaded_by_id.get(document.document_id, document) for document in documents
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


if __name__ == "__main__":
    app()
