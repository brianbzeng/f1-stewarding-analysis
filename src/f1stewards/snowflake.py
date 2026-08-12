"""Credential-free Snowflake/Snowsight pilot export and local validation."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
from pyarrow import ArrowInvalid

from f1stewards.manual import CodedAdjudication, ImpactAssessment, IndependentReviewRecord
from f1stewards.readiness import load_pilot_manual_records

EXPORT_SCHEMA_VERSION = "snowflake_pilot_v1"

DUCKDB_EXPORTS = {
    "metadata_events": """
        SELECT event_id, season, round_number, event_name, country, event_date,
               archive_url, guideline_regime, is_pilot
        FROM metadata.events
        ORDER BY season, event_date
    """,
    "raw_source_documents": """
        SELECT document_id, event_id, title, document_url, archive_url, document_class,
               published_at_raw, published_at, discovered_at, retrieved_at, source_domain,
               content_sha256, http_status, content_type, retrieval_error, is_recalled,
               supersedes_document_id
        FROM raw.source_documents
        ORDER BY event_id, document_id
    """,
    "raw_document_text": """
        SELECT document_id, parser_version, parsed_at, page_count, raw_text, fact_text,
               infringement_text, decision_text, reason_text, parser_warnings_json,
               driver_number, driver_name, session_type, incident_time_raw
        FROM raw.document_text
        ORDER BY document_id
    """,
    "raw_fastf1_results": """
        SELECT event_id, driver_number, driver_name, abbreviation, country_code, team_name,
               grid_position, finish_position, classified_position, status, points, retrieved_at,
               result_time_seconds, laps_completed, classification_gap_seconds
        FROM raw.fastf1_results
        ORDER BY event_id, finish_position, driver_number
    """,
    "metadata_regulatory_sources": """
        SELECT source_id, document_type, title, issuing_body, publication_date, effective_from,
               effective_through, source_url, resolved_url, source_status, applicability_status,
               is_guideline, notes
        FROM metadata.regulatory_sources
        ORDER BY source_id
    """,
    "metadata_event_regulatory_sources": """
        SELECT event_id, source_id, event_role
        FROM metadata.event_regulatory_sources
        ORDER BY event_id, source_id
    """,
    "metadata_sporting_regulation_issues": """
        SELECT source_id, season, precedence, publication_date, issue_label, title, archive_url,
               document_url, resolution_status, selection_status, notes
        FROM metadata.sporting_regulation_issues
        ORDER BY season, precedence
    """,
    "metadata_international_sporting_code_issues": """
        SELECT source_id, season, precedence, publication_date, effective_from, effective_through,
               title, archive_url, document_url, resolution_status, selection_status, notes
        FROM metadata.international_sporting_code_issues
        ORDER BY season, precedence
    """,
    "metadata_claim_ledger": """
        SELECT claim_id, report_section, research_question, claim_template, estimand, population,
               required_method, minimum_acceptance, required_sensitivity, evidence_grade_if_met,
               status, primary_limitation
        FROM metadata.claim_ledger
        ORDER BY claim_id
    """,
}

TABLE_NAMES = {
    "metadata_events": "METADATA.EVENTS",
    "raw_source_documents": "RAW.SOURCE_DOCUMENTS",
    "raw_document_text": "RAW.DOCUMENT_TEXT",
    "raw_fastf1_results": "RAW.FASTF1_RESULTS",
    "metadata_regulatory_sources": "METADATA.REGULATORY_SOURCES",
    "metadata_event_regulatory_sources": "METADATA.EVENT_REGULATORY_SOURCES",
    "metadata_sporting_regulation_issues": "METADATA.SPORTING_REGULATION_ISSUES",
    "metadata_international_sporting_code_issues": (
        "METADATA.INTERNATIONAL_SPORTING_CODE_ISSUES"
    ),
    "metadata_claim_ledger": "METADATA.CLAIM_LEDGER",
    "curated_adjudications": "CURATED.ADJUDICATIONS",
    "curated_impact_assessments": "CURATED.IMPACT_ASSESSMENTS",
    "audit_independent_review": "AUDIT.INDEPENDENT_REVIEW",
}


@dataclass(frozen=True)
class SnowflakeExportResult:
    export_id: str
    output_directory: Path
    manifest: dict[str, Any]
    created: bool


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_commit(project_root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=project_root,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def _manual_frame(
    records: list[CodedAdjudication]
    | list[ImpactAssessment]
    | list[IndependentReviewRecord],
) -> pd.DataFrame:
    frame = pd.DataFrame([record.model_dump(mode="json") for record in records])
    if "reviewed_at_utc" in frame:
        frame["reviewed_at_utc"] = pd.to_datetime(frame["reviewed_at_utc"], utc=True)
    return frame


def build_snowflake_frames(
    connection: duckdb.DuckDBPyConnection,
    coding_path: Path,
    impact_path: Path,
    review_path: Path,
) -> dict[str, pd.DataFrame]:
    """Assemble the bounded pilot tables with deterministic row ordering."""

    frames = {
        export_name: connection.sql(query).df()
        for export_name, query in DUCKDB_EXPORTS.items()
    }
    coded, impacts, reviews = load_pilot_manual_records(coding_path, impact_path, review_path)
    frames.update(
        {
            "curated_adjudications": _manual_frame(coded),
            "curated_impact_assessments": _manual_frame(impacts),
            "audit_independent_review": _manual_frame(reviews),
        }
    )
    if set(frames) != set(TABLE_NAMES):
        raise ValueError("Snowflake export mapping and generated frames differ")
    return frames


def _release_status(frames: dict[str, pd.DataFrame]) -> str:
    curated_ready = all(
        frame["review_status"].isin({"double_coded", "adjudicated"}).all()
        for frame in (
            frames["curated_adjudications"],
            frames["curated_impact_assessments"],
        )
    )
    reviews_resolved = frames["audit_independent_review"]["review_status"].isin(
        {"agree", "correct"}
    ).all()
    return "reviewed" if curated_ready and reviews_resolved else "provisional"


def export_snowflake_pilot(
    connection: duckdb.DuckDBPyConnection,
    project_root: Path,
    output_root: Path,
    coding_path: Path,
    impact_path: Path,
    review_path: Path,
) -> SnowflakeExportResult:
    """Write a content-addressed set of Snowsight-uploadable Parquet files."""

    frames = build_snowflake_frames(connection, coding_path, impact_path, review_path)
    output_root.mkdir(parents=True, exist_ok=True)
    temporary_directory = Path(tempfile.mkdtemp(prefix=".snowflake-pilot-", dir=output_root))
    try:
        table_metadata: dict[str, dict[str, Any]] = {}
        for export_name, frame in frames.items():
            filename = f"{export_name}.parquet"
            path = temporary_directory / filename
            frame.to_parquet(path, index=False, compression="snappy")
            table_metadata[export_name] = {
                "snowflake_table": TABLE_NAMES[export_name],
                "filename": filename,
                "row_count": len(frame),
                "columns": list(frame.columns),
                "sha256": _sha256(path),
            }

        git_commit = _git_commit(project_root)
        identity = json.dumps(
            {
                "schema_version": EXPORT_SCHEMA_VERSION,
                "git_commit": git_commit,
                "files": {
                    name: metadata["sha256"] for name, metadata in sorted(table_metadata.items())
                },
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        export_id = f"snowflake-pilot-{hashlib.sha256(identity).hexdigest()[:12]}"
        manifest = {
            "schema_version": EXPORT_SCHEMA_VERSION,
            "export_id": export_id,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "git_commit": git_commit,
            "release_status": _release_status(frames),
            "table_count": len(table_metadata),
            "tables": dict(sorted(table_metadata.items())),
            "security_note": "Public FIA evidence and public FastF1 data; no credentials included.",
        }
        (temporary_directory / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        final_directory = output_root / export_id
        if final_directory.exists():
            shutil.rmtree(temporary_directory)
            validation = validate_snowflake_export(final_directory)
            if not validation.status.eq("pass").all():
                raise FileExistsError(f"Existing Snowflake export failed validation: {export_id}")
            existing_manifest = json.loads(
                (final_directory / "manifest.json").read_text(encoding="utf-8")
            )
            return SnowflakeExportResult(
                export_id=export_id,
                output_directory=final_directory,
                manifest=existing_manifest,
                created=False,
            )
        temporary_directory.replace(final_directory)
        return SnowflakeExportResult(
            export_id=export_id,
            output_directory=final_directory,
            manifest=manifest,
            created=True,
        )
    except Exception:
        if temporary_directory.exists():
            shutil.rmtree(temporary_directory, ignore_errors=True)
        raise


def validate_snowflake_export(export_directory: Path) -> pd.DataFrame:
    """Verify table set, checksums, schemas, and row counts without Snowflake credentials."""

    manifest_path = export_directory / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError("Snowflake export manifest is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != EXPORT_SCHEMA_VERSION:
        raise ValueError("Snowflake export schema version is unsupported")
    if set(manifest.get("tables", {})) != set(TABLE_NAMES):
        raise ValueError("Snowflake export manifest has an unexpected table set")

    rows = []
    for export_name, metadata in manifest["tables"].items():
        path = export_directory / metadata["filename"]
        file_exists = path.is_file()
        readable = False
        frame = pd.DataFrame()
        if file_exists:
            try:
                frame = pd.read_parquet(path)
                readable = True
            except (ArrowInvalid, OSError, ValueError):
                pass
        hash_match = file_exists and _sha256(path) == metadata["sha256"]
        row_count_match = readable and len(frame) == metadata["row_count"]
        columns_match = readable and list(frame.columns) == metadata["columns"]
        rows.append(
            {
                "export_name": export_name,
                "snowflake_table": metadata["snowflake_table"],
                "expected_rows": metadata["row_count"],
                "actual_rows": len(frame) if readable else None,
                "file_exists": file_exists,
                "readable": readable,
                "hash_match": hash_match,
                "row_count_match": row_count_match,
                "columns_match": columns_match,
                "status": (
                    "pass"
                    if readable and hash_match and row_count_match and columns_match
                    else "fail"
                ),
            }
        )
    return pd.DataFrame(rows).sort_values("export_name", ignore_index=True)
