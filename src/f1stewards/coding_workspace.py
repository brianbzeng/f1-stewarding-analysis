"""Content-addressed full-corpus coding workspaces with protected source lineage."""

from __future__ import annotations

import hashlib
import io
import json
import re
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from f1stewards.coding_queue import (
    ADJUDICATION_QUEUE_FILENAME,
    ADJUDICATION_SEED_COLUMNS,
    DOCUMENT_QUEUE_FILENAME,
    DOCUMENT_REVIEW_COLUMNS,
    EXCLUSION_QA_COLUMNS,
    EXCLUSION_QA_FILENAME,
    FINAL_ADJUDICATION_FIELDS,
    FINAL_DOCUMENT_FIELDS,
    FINAL_EXCLUSION_QA_FIELDS,
    QUEUE_MANIFEST_FILENAME,
)

WORKSPACE_SCHEMA_VERSION = "full-corpus-coding-workspace-v2"
WORKSPACE_DOCUMENT_FILENAME = "document_review_worklist.csv"
WORKSPACE_ADJUDICATION_FILENAME = "adjudication_coding_worklist.csv"
WORKSPACE_EXCLUSION_QA_FILENAME = "exclusion_qa_worklist.csv"
WORKSPACE_MANIFEST_FILENAME = "workspace_manifest.json"

FULL_CORPUS_REVIEW_STATUSES = {
    "",
    "single_coded_pending_human",
    "model_reviewed_agree",
    "model_reviewed_corrected",
    "source_unavailable_model_review",
    "model_review_unresolved",
    "double_coded",
    "adjudicated",
}
FAULT_LANGUAGE_VALUES = {
    "",
    "wholly_to_blame",
    "predominantly_to_blame",
    "mainly_at_fault",
    "shared_fault",
    "racing_incident",
    "no_conclusion",
    "not_applicable",
}

DOCUMENT_CONTEXT_COLUMNS = [
    "workspace_review_order",
    "workspace_priority_bucket",
    "workspace_priority_basis",
]

ADJUDICATION_CONTEXT_COLUMNS = [
    "adjudication_instance_id",
    "workspace_review_order",
    "workspace_priority_bucket",
    "workspace_priority_basis",
    "timing_session_expected",
    "timing_session_loaded",
    "timing_ingestion_status",
    "timing_classification_rows",
    "timing_lap_rows",
    "timing_message_rows",
    "timing_direct_timestamp_rows",
    "timing_derived_timestamp_rows",
    "timing_missing_timestamp_rows",
    "timing_incident_eligible_rows",
    "timing_pace_eligible_rows",
    "timing_beyond_classified_rows",
    "timing_missing_within_rows",
    "timing_fallback_rows",
    "accused_driver_result_present_suggestion",
    "accused_driver_classified_laps_suggestion",
    "accused_driver_stored_timing_laps",
    "accused_driver_missing_within_rows",
    "accused_driver_beyond_classified_rows",
]

EXCLUSION_QA_CONTEXT_COLUMNS = [
    "workspace_review_order",
    "workspace_priority_bucket",
    "workspace_priority_basis",
]


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _csv_bytes(frame: pd.DataFrame) -> bytes:
    stream = io.StringIO(newline="")
    frame.to_csv(stream, index=False, lineterminator="\n")
    return stream.getvalue().encode("utf-8")


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def _verify_seed_file(seed_directory: Path, name: str, manifest: dict[str, Any]) -> None:
    path = seed_directory / name
    if not path.exists():
        raise ValueError(f"Missing protected seed file: {path}")
    expected = manifest["outputs"][name]
    payload = path.read_bytes()
    if _sha256(payload) != expected["sha256"]:
        raise ValueError(f"Protected seed hash mismatch: {name}")


def load_protected_seed_bundle(
    seed_directory: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Read and hash-verify the three protected seed tables and manifest."""

    manifest_path = seed_directory / QUEUE_MANIFEST_FILENAME
    if not manifest_path.exists():
        raise ValueError(f"Missing protected seed manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for name in (
        DOCUMENT_QUEUE_FILENAME,
        ADJUDICATION_QUEUE_FILENAME,
        EXCLUSION_QA_FILENAME,
    ):
        _verify_seed_file(seed_directory, name, manifest)

    documents = _read_csv(seed_directory / DOCUMENT_QUEUE_FILENAME)
    adjudications = _read_csv(seed_directory / ADJUDICATION_QUEUE_FILENAME)
    exclusion_qa = _read_csv(seed_directory / EXCLUSION_QA_FILENAME)
    expected_columns = (
        (documents, DOCUMENT_REVIEW_COLUMNS, DOCUMENT_QUEUE_FILENAME),
        (adjudications, ADJUDICATION_SEED_COLUMNS, ADJUDICATION_QUEUE_FILENAME),
        (exclusion_qa, EXCLUSION_QA_COLUMNS, EXCLUSION_QA_FILENAME),
    )
    for frame, columns, name in expected_columns:
        if list(frame.columns) != columns:
            raise ValueError(f"Protected seed columns changed: {name}")
        if len(frame) != manifest["outputs"][name]["row_count"]:
            raise ValueError(f"Protected seed row count changed: {name}")
    return documents, adjudications, exclusion_qa, manifest


def load_timing_review_context(
    connection: duckdb.DuckDBPyConnection,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load deterministic session and driver timing quality for coding prioritization."""

    sessions = connection.sql(
        """
        SELECT
            quality.event_id,
            quality.session_type,
            ingestion.status AS timing_ingestion_status,
            ingestion.result_rows AS timing_classification_rows,
            ingestion.lap_rows AS timing_lap_rows,
            ingestion.message_rows AS timing_message_rows,
            ingestion.direct_lap_timestamp_rows AS timing_direct_timestamp_rows,
            ingestion.derived_lap_timestamp_rows AS timing_derived_timestamp_rows,
            ingestion.missing_lap_timestamp_rows AS timing_missing_timestamp_rows,
            quality.incident_timing_eligible_rows AS timing_incident_eligible_rows,
            quality.pace_model_eligible_rows AS timing_pace_eligible_rows,
            quality.stored_beyond_classified_distance AS timing_beyond_classified_rows,
            quality.missing_within_classified_distance AS timing_missing_within_rows,
            quality.fallback_timing_rows AS timing_fallback_rows
        FROM analysis.v_fastf1_session_data_quality AS quality
        JOIN metadata.fastf1_session_ingestion AS ingestion
          USING (event_id, session_type)
        ORDER BY quality.event_id, quality.session_type
        """
    ).df()
    drivers = connection.sql(
        """
        SELECT
            event_id,
            session_type,
            driver_number,
            classified_laps AS accused_driver_classified_laps_suggestion,
            stored_timing_laps AS accused_driver_stored_timing_laps,
            missing_within_classified_distance AS accused_driver_missing_within_rows,
            stored_beyond_classified_distance AS accused_driver_beyond_classified_rows
        FROM analysis.v_fastf1_driver_lap_coverage
        ORDER BY event_id, session_type, driver_number
        """
    ).df()
    return sessions, drivers


def _priority_bucket(eligibility: str, *, parser_review: bool = False) -> tuple[int, str, str]:
    if eligibility == "version_resolution_required":
        return 1, "version_resolution", "Unresolved recalled outcome requires disposition."
    if eligibility in {"version_exclusion_suggestion", "content_exclusion_suggestion"}:
        return 2, "version_or_content", "Resolve version and content-type attrition first."
    if eligibility == "primary_candidate" and parser_review:
        return 3, "primary_parser_review", "Primary candidate requires source-PDF review."
    if eligibility == "primary_candidate":
        return 4, "primary_candidate", "Primary Race/Sprint candidate."
    if eligibility == "secondary_candidate" and parser_review:
        return 5, "secondary_parser_review", "Secondary candidate requires source-PDF review."
    if eligibility == "secondary_candidate":
        return 6, "secondary_candidate", "Secondary qualifying-impeding candidate."
    if eligibility in {"manual_offence_review", "manual_session_review"}:
        return 7, "manual_scope_review", "Machine rules could not make a safe scope suggestion."
    return 8, "proposed_exclusion", "Proposed exclusion remains subject to controlled review."


def _add_review_priority(
    frame: pd.DataFrame,
    *,
    eligibility_column: str = "eligibility_suggestion",
) -> pd.DataFrame:
    prioritized = frame.copy()
    buckets = [
        _priority_bucket(
            str(row[eligibility_column]),
            parser_review=str(row.get("parser_review_required", "")).casefold() == "true",
        )
        for _, row in prioritized.iterrows()
    ]
    prioritized["_priority"] = [item[0] for item in buckets]
    prioritized["workspace_priority_bucket"] = [item[1] for item in buckets]
    prioritized["workspace_priority_basis"] = [item[2] for item in buckets]
    prioritized["_season_sort"] = pd.to_numeric(prioritized["season"], errors="coerce")
    prioritized["_round_sort"] = pd.to_numeric(
        prioritized["round_number"], errors="coerce"
    )
    prioritized = prioritized.sort_values(
        [
            "_priority",
            "_season_sort",
            "_round_sort",
            "event_id",
            prioritized.columns[0],
        ],
        kind="stable",
    ).reset_index(drop=True)
    prioritized["workspace_review_order"] = prioritized.index + 1
    return prioritized.drop(columns=["_priority", "_season_sort", "_round_sort"])


def build_full_corpus_coding_workspace(
    documents: pd.DataFrame,
    adjudications: pd.DataFrame,
    exclusion_qa: pd.DataFrame,
    session_context: pd.DataFrame,
    driver_context: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Create an unedited coding starter with protected timing and review context."""

    document_worklist = _add_review_priority(documents)
    document_protected = [
        column for column in DOCUMENT_REVIEW_COLUMNS if column not in FINAL_DOCUMENT_FIELDS
    ]
    document_worklist = document_worklist[
        document_protected + DOCUMENT_CONTEXT_COLUMNS + FINAL_DOCUMENT_FIELDS
    ]

    adjudication_worklist = _add_review_priority(adjudications)
    adjudication_worklist["adjudication_instance_id"] = (
        adjudication_worklist["adjudication_seed_id"] + "-01"
    )
    adjudication_worklist["timing_session_expected"] = adjudication_worklist[
        "session_type_suggestion"
    ].isin({"Race", "Sprint"})

    session_columns = [
        "event_id",
        "session_type",
        "timing_ingestion_status",
        "timing_classification_rows",
        "timing_lap_rows",
        "timing_message_rows",
        "timing_direct_timestamp_rows",
        "timing_derived_timestamp_rows",
        "timing_missing_timestamp_rows",
        "timing_incident_eligible_rows",
        "timing_pace_eligible_rows",
        "timing_beyond_classified_rows",
        "timing_missing_within_rows",
        "timing_fallback_rows",
    ]
    adjudication_worklist = adjudication_worklist.merge(
        session_context[session_columns],
        left_on=["event_id", "session_type_suggestion"],
        right_on=["event_id", "session_type"],
        how="left",
        validate="many_to_one",
    ).drop(columns="session_type")
    adjudication_worklist["timing_session_loaded"] = adjudication_worklist[
        "timing_ingestion_status"
    ].eq("succeeded")

    driver_join = driver_context.copy()
    driver_join["_driver_number_key"] = pd.to_numeric(
        driver_join["driver_number"], errors="coerce"
    ).astype("Int64").astype("string")
    adjudication_worklist["_driver_number_key"] = pd.to_numeric(
        adjudication_worklist["driver_number_suggestion"], errors="coerce"
    ).astype("Int64").astype("string")
    adjudication_worklist = adjudication_worklist.merge(
        driver_join.drop(columns="driver_number"),
        left_on=["event_id", "session_type_suggestion", "_driver_number_key"],
        right_on=["event_id", "session_type", "_driver_number_key"],
        how="left",
        validate="many_to_one",
    ).drop(columns=["session_type", "_driver_number_key"])
    adjudication_worklist["accused_driver_result_present_suggestion"] = adjudication_worklist[
        "accused_driver_classified_laps_suggestion"
    ].notna()

    count_columns = [
        column
        for column in ADJUDICATION_CONTEXT_COLUMNS
        if column.startswith("timing_") or column.startswith("accused_driver_")
    ]
    boolean_columns = {
        "timing_session_expected",
        "timing_session_loaded",
        "accused_driver_result_present_suggestion",
    }
    for column in count_columns:
        if column in boolean_columns or column == "timing_ingestion_status":
            continue
        adjudication_worklist[column] = adjudication_worklist[column].fillna("")

    adjudication_protected = [
        column for column in ADJUDICATION_SEED_COLUMNS if column not in FINAL_ADJUDICATION_FIELDS
    ]
    adjudication_worklist = adjudication_worklist[
        adjudication_protected + ADJUDICATION_CONTEXT_COLUMNS + FINAL_ADJUDICATION_FIELDS
    ]

    qa_worklist = exclusion_qa.copy()
    qa_worklist["_season_sort"] = pd.to_numeric(qa_worklist["season"], errors="coerce")
    qa_worklist["_rank_sort"] = pd.to_numeric(
        qa_worklist["qa_selection_rank"], errors="coerce"
    )
    qa_worklist = qa_worklist.sort_values(
        ["_season_sort", "qa_stratum_id", "_rank_sort", "exclusion_qa_id"],
        kind="stable",
    ).reset_index(drop=True).drop(columns=["_season_sort", "_rank_sort"])
    qa_worklist["workspace_review_order"] = qa_worklist.index + 1
    qa_worklist["workspace_priority_bucket"] = "stratified_exclusion_qa"
    qa_worklist["workspace_priority_basis"] = (
        "Frozen hash-selected exclusion quality-control sample."
    )
    qa_protected = [
        column for column in EXCLUSION_QA_COLUMNS if column not in FINAL_EXCLUSION_QA_FIELDS
    ]
    qa_worklist = qa_worklist[
        qa_protected + EXCLUSION_QA_CONTEXT_COLUMNS + FINAL_EXCLUSION_QA_FIELDS
    ]
    return document_worklist, adjudication_worklist, qa_worklist


def _logical_context_digest(session_context: pd.DataFrame, driver_context: pd.DataFrame) -> str:
    payload = _csv_bytes(session_context) + b"\n" + _csv_bytes(driver_context)
    return _sha256(payload)


def build_workspace_manifest(
    seed_manifest_bytes: bytes,
    session_context: pd.DataFrame,
    driver_context: pd.DataFrame,
    documents: pd.DataFrame,
    adjudications: pd.DataFrame,
    exclusion_qa: pd.DataFrame,
) -> tuple[str, dict[str, Any], dict[str, bytes]]:
    """Build stable output bytes and their content-addressed workspace manifest."""

    outputs = {
        WORKSPACE_DOCUMENT_FILENAME: _csv_bytes(documents),
        WORKSPACE_ADJUDICATION_FILENAME: _csv_bytes(adjudications),
        WORKSPACE_EXCLUSION_QA_FILENAME: _csv_bytes(exclusion_qa),
    }
    timing_digest = _logical_context_digest(session_context, driver_context)
    content_digest = _sha256(
        b"\n".join(
            name.encode("utf-8") + b":" + _sha256(payload).encode("ascii")
            for name, payload in sorted(outputs.items())
        )
    )
    identity_payload = (
        WORKSPACE_SCHEMA_VERSION.encode("utf-8")
        + b"\n"
        + _sha256(seed_manifest_bytes).encode("ascii")
        + b"\n"
        + timing_digest.encode("ascii")
        + b"\n"
        + content_digest.encode("ascii")
    )
    workspace_id = f"full-coding-{_sha256(identity_payload)[:12]}"
    manifest = {
        "schema_version": WORKSPACE_SCHEMA_VERSION,
        "workspace_id": workspace_id,
        "protected_seed_manifest_sha256": _sha256(seed_manifest_bytes),
        "timing_context_sha256": timing_digest,
        "workspace_content_sha256": content_digest,
        "timing_context_counts": {
            "sessions": int(len(session_context)),
            "drivers": int(len(driver_context)),
        },
        "outputs": {
            name: {"sha256": _sha256(payload), "row_count": int(len(frame))}
            for (name, payload), frame in zip(
                outputs.items(),
                (documents, adjudications, exclusion_qa),
                strict=True,
            )
        },
        "editing_contract": (
            "Suggestion, source, and workspace-context columns are protected. Final coding fields "
            "may be edited; adjudication seeds may be duplicated only with a unique "
            "adjudication_instance_id to represent supported one-to-many splits."
        ),
        "interpretation_boundary": (
            "Timing context prioritizes evidence review and does not establish fault, harm, "
            "consistency, nationality effects, or fairness."
        ),
    }
    manifest_bytes = (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    return workspace_id, manifest, {**outputs, WORKSPACE_MANIFEST_FILENAME: manifest_bytes}


def write_full_corpus_coding_workspace(
    seed_directory: Path,
    output_root: Path,
    session_context: pd.DataFrame,
    driver_context: pd.DataFrame,
) -> tuple[Path, dict[str, Any], bool]:
    """Create or byte-verify one immutable, content-addressed workspace starter."""

    documents, adjudications, exclusion_qa, _ = load_protected_seed_bundle(seed_directory)
    worklists = build_full_corpus_coding_workspace(
        documents,
        adjudications,
        exclusion_qa,
        session_context,
        driver_context,
    )
    workspace_id, manifest, payloads = build_workspace_manifest(
        (seed_directory / QUEUE_MANIFEST_FILENAME).read_bytes(),
        session_context,
        driver_context,
        *worklists,
    )
    output_directory = output_root / workspace_id
    created = not output_directory.exists()
    output_directory.mkdir(parents=True, exist_ok=True)
    for name, payload in payloads.items():
        path = output_directory / name
        if path.exists() and path.read_bytes() != payload:
            raise FileExistsError(f"Workspace starter differs from deterministic rebuild: {path}")
        path.write_bytes(payload)
    return output_directory, manifest, created


def audit_full_corpus_coding_workspace(
    seed_directory: Path,
    workspace_directory: Path,
    session_context: pd.DataFrame,
    driver_context: pd.DataFrame,
) -> pd.DataFrame:
    """Verify an unedited workspace starter against protected seed and timing context."""

    documents, adjudications, exclusion_qa, _ = load_protected_seed_bundle(seed_directory)
    worklists = build_full_corpus_coding_workspace(
        documents,
        adjudications,
        exclusion_qa,
        session_context,
        driver_context,
    )
    workspace_id, _, expected = build_workspace_manifest(
        (seed_directory / QUEUE_MANIFEST_FILENAME).read_bytes(),
        session_context,
        driver_context,
        *worklists,
    )
    if workspace_directory.name != workspace_id:
        raise ValueError(
            f"Workspace directory {workspace_directory.name} does not match {workspace_id}"
        )
    rows = []
    for name, payload in expected.items():
        path = workspace_directory / name
        exists = path.exists()
        actual = path.read_bytes() if exists else b""
        rows.append(
            {
                "control": name,
                "status": "pass" if exists and actual == payload else "fail",
                "expected_sha256": _sha256(payload),
                "actual_sha256": _sha256(actual) if exists else "missing",
            }
        )
    return pd.DataFrame(rows)


def _canonical_strings(frame: pd.DataFrame) -> pd.DataFrame:
    """Round-trip a frame through the workspace CSV representation."""

    return pd.read_csv(
        io.BytesIO(_csv_bytes(frame)),
        dtype=str,
        keep_default_na=False,
    )


def _control(control: str, passed: bool, detail: str) -> dict[str, str]:
    return {"control": control, "status": "pass" if passed else "fail", "detail": detail}


def _read_worklist_for_validation(
    workspace_directory: Path,
    filename: str,
    expected_columns: list[str],
    controls: list[dict[str, str]],
) -> pd.DataFrame | None:
    path = workspace_directory / filename
    if not path.exists():
        controls.append(_control(f"{filename}:exists", False, "File is missing."))
        return None
    controls.append(_control(f"{filename}:exists", True, "File is present."))
    try:
        frame = _read_csv(path)
    except Exception as exc:  # pragma: no cover - parser detail depends on pandas
        controls.append(_control(f"{filename}:readable", False, str(exc)))
        return None
    columns_match = list(frame.columns) == expected_columns
    controls.append(
        _control(
            f"{filename}:columns",
            columns_match,
            "Exact schema and column order retained."
            if columns_match
            else "Schema or column order differs from the starter.",
        )
    )
    return frame if columns_match else None


def _protected_rows_match(
    actual: pd.DataFrame,
    expected: pd.DataFrame,
    *,
    key: str,
    protected_columns: list[str],
) -> tuple[bool, int]:
    expected_lookup = expected.set_index(key)
    mismatches = 0
    for _, row in actual.iterrows():
        row_key = row[key]
        if row_key not in expected_lookup.index:
            mismatches += 1
            continue
        expected_row = expected_lookup.loc[row_key]
        if isinstance(expected_row, pd.DataFrame):
            mismatches += 1
            continue
        mismatches += sum(
            str(row[column]) != str(expected_row[column])
            for column in protected_columns
            if column != key
        )
    return mismatches == 0, mismatches


def validate_edited_full_corpus_coding_workspace(
    seed_directory: Path,
    workspace_directory: Path,
    session_context: pd.DataFrame,
    driver_context: pd.DataFrame,
) -> pd.DataFrame:
    """Validate editable fields and splits while protecting source and timing lineage."""

    documents, adjudications, exclusion_qa, _ = load_protected_seed_bundle(seed_directory)
    expected_worklists = build_full_corpus_coding_workspace(
        documents,
        adjudications,
        exclusion_qa,
        session_context,
        driver_context,
    )
    workspace_id, _, expected_payloads = build_workspace_manifest(
        (seed_directory / QUEUE_MANIFEST_FILENAME).read_bytes(),
        session_context,
        driver_context,
        *expected_worklists,
    )
    expected_documents, expected_adjudications, expected_qa = map(
        _canonical_strings, expected_worklists
    )
    controls: list[dict[str, str]] = []

    controls.append(
        _control(
            "workspace_id",
            workspace_directory.name == workspace_id,
            f"Expected directory name {workspace_id}; observed {workspace_directory.name}.",
        )
    )
    manifest_path = workspace_directory / WORKSPACE_MANIFEST_FILENAME
    manifest_payload = expected_payloads[WORKSPACE_MANIFEST_FILENAME]
    manifest_match = manifest_path.exists() and manifest_path.read_bytes() == manifest_payload
    controls.append(
        _control(
            "workspace_manifest",
            manifest_match,
            "Protected workspace manifest matches deterministic starter."
            if manifest_match
            else "Workspace manifest is missing or changed.",
        )
    )

    document_columns = list(expected_documents.columns)
    actual_documents = _read_worklist_for_validation(
        workspace_directory,
        WORKSPACE_DOCUMENT_FILENAME,
        document_columns,
        controls,
    )
    if actual_documents is not None:
        key = "document_review_id"
        expected_keys = set(expected_documents[key])
        actual_keys = set(actual_documents[key])
        keys_valid = (
            actual_documents[key].is_unique
            and not actual_documents[key].eq("").any()
            and actual_keys == expected_keys
            and len(actual_documents) == len(expected_documents)
        )
        controls.append(
            _control(
                "document_review_worklist:row_identity",
                keys_valid,
                f"Expected {len(expected_documents)} unique protected IDs; observed "
                f"{len(actual_documents)} rows and {actual_documents[key].nunique()} IDs.",
            )
        )
        protected = [column for column in document_columns if column not in FINAL_DOCUMENT_FIELDS]
        matches, mismatch_count = _protected_rows_match(
            actual_documents,
            expected_documents,
            key=key,
            protected_columns=protected,
        )
        controls.append(
            _control(
                "document_review_worklist:protected_lineage",
                keys_valid and matches,
                f"Protected-field mismatches: {mismatch_count}.",
            )
        )

    adjudication_columns = list(expected_adjudications.columns)
    actual_adjudications = _read_worklist_for_validation(
        workspace_directory,
        WORKSPACE_ADJUDICATION_FILENAME,
        adjudication_columns,
        controls,
    )
    if actual_adjudications is not None:
        seed_key = "adjudication_seed_id"
        instance_key = "adjudication_instance_id"
        expected_seeds = set(expected_adjudications[seed_key])
        actual_seeds = set(actual_adjudications[seed_key])
        seed_coverage = expected_seeds == actual_seeds and len(actual_adjudications) >= len(
            expected_adjudications
        )
        controls.append(
            _control(
                "adjudication_coding_worklist:seed_coverage",
                seed_coverage,
                f"Expected {len(expected_seeds)} seed IDs; observed {len(actual_seeds)} across "
                f"{len(actual_adjudications)} instances.",
            )
        )
        instances_unique = (
            actual_adjudications[instance_key].is_unique
            and not actual_adjudications[instance_key].eq("").any()
        )
        instances_well_formed = all(
            bool(re.fullmatch(re.escape(seed_id) + r"-\d{2,}", instance_id))
            for seed_id, instance_id in zip(
                actual_adjudications[seed_key],
                actual_adjudications[instance_key],
                strict=True,
            )
        )
        controls.append(
            _control(
                "adjudication_coding_worklist:instance_identity",
                instances_unique and instances_well_formed,
                "Instance IDs are unique and use <seed-id>-<two-or-more-digit sequence>."
                if instances_unique and instances_well_formed
                else "Instance IDs are duplicated, blank, or not derived from their seed ID.",
            )
        )
        first_instances = {
            f"{seed_id}-01" for seed_id in expected_adjudications[seed_key]
        }
        observed_instances = set(actual_adjudications[instance_key])
        first_instances_retained = first_instances.issubset(observed_instances)
        controls.append(
            _control(
                "adjudication_coding_worklist:starter_instances",
                first_instances_retained,
                "Every protected seed retains its -01 starter instance."
                if first_instances_retained
                else f"Missing -01 starter instances: "
                f"{len(first_instances - observed_instances)}.",
            )
        )
        protected = [
            column
            for column in adjudication_columns
            if column not in FINAL_ADJUDICATION_FIELDS and column != instance_key
        ]
        matches, mismatch_count = _protected_rows_match(
            actual_adjudications,
            expected_adjudications,
            key=seed_key,
            protected_columns=protected,
        )
        controls.append(
            _control(
                "adjudication_coding_worklist:protected_lineage",
                seed_coverage and matches,
                f"Protected-field mismatches: {mismatch_count}.",
            )
        )
        final_ids = actual_adjudications["adjudication_id_final"]
        populated_final_ids = final_ids[final_ids.ne("")]
        controls.append(
            _control(
                "adjudication_coding_worklist:final_id_uniqueness",
                populated_final_ids.is_unique,
                f"Populated final IDs: {len(populated_final_ids)}; unique: "
                f"{populated_final_ids.nunique()}.",
            )
        )
        primary = actual_adjudications["include_primary_final"].str.casefold()
        secondary = actual_adjudications["include_secondary_final"].str.casefold()
        valid_flags = {"", "true", "false"}
        flag_values_valid = set(primary).issubset(valid_flags) and set(secondary).issubset(
            valid_flags
        )
        mutually_exclusive = not ((primary == "true") & (secondary == "true")).any()
        controls.append(
            _control(
                "adjudication_coding_worklist:inclusion_flags",
                flag_values_valid and mutually_exclusive,
                "Inclusion flags are blank/true/false and primary/secondary are mutually exclusive."
                if flag_values_valid and mutually_exclusive
                else "Inclusion flags contain invalid values or select both populations.",
            )
        )
        numeric_fields_valid = True
        for column, integer_only in (
            ("penalty_seconds_final", False),
            ("penalty_points_final", True),
            ("grid_places_final", True),
        ):
            populated = actual_adjudications.loc[
                actual_adjudications[column].ne(""), column
            ]
            numeric = pd.to_numeric(populated, errors="coerce")
            valid = numeric.notna() & numeric.ge(0)
            if integer_only:
                valid &= numeric.mod(1).eq(0)
            numeric_fields_valid &= bool(valid.all())
        fault_language_valid = set(actual_adjudications["fault_language_final"]).issubset(
            FAULT_LANGUAGE_VALUES
        )
        review_status_valid = set(actual_adjudications["review_status"]).issubset(
            FULL_CORPUS_REVIEW_STATUSES
        )
        controls.append(
            _control(
                "adjudication_coding_worklist:corrected_outcome_fields",
                numeric_fields_valid and fault_language_valid and review_status_valid,
                "Corrected sanctions are nonnegative, integer where required, and controlled "
                "fault/review values are valid."
                if numeric_fields_valid and fault_language_valid and review_status_valid
                else "Corrected sanction, fault-language, or review-status values are invalid.",
            )
        )

    qa_columns = list(expected_qa.columns)
    actual_qa = _read_worklist_for_validation(
        workspace_directory,
        WORKSPACE_EXCLUSION_QA_FILENAME,
        qa_columns,
        controls,
    )
    if actual_qa is not None:
        key = "exclusion_qa_id"
        expected_keys = set(expected_qa[key])
        actual_keys = set(actual_qa[key])
        keys_valid = (
            actual_qa[key].is_unique
            and not actual_qa[key].eq("").any()
            and actual_keys == expected_keys
            and len(actual_qa) == len(expected_qa)
        )
        controls.append(
            _control(
                "exclusion_qa_worklist:row_identity",
                keys_valid,
                f"Expected {len(expected_qa)} unique protected IDs; observed {len(actual_qa)} "
                f"rows and {actual_qa[key].nunique()} IDs.",
            )
        )
        protected = [column for column in qa_columns if column not in FINAL_EXCLUSION_QA_FIELDS]
        matches, mismatch_count = _protected_rows_match(
            actual_qa,
            expected_qa,
            key=key,
            protected_columns=protected,
        )
        controls.append(
            _control(
                "exclusion_qa_worklist:protected_lineage",
                keys_valid and matches,
                f"Protected-field mismatches: {mismatch_count}.",
            )
        )

    return pd.DataFrame(controls)
