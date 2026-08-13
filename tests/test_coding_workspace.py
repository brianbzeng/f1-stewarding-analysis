import hashlib
import json
from pathlib import Path

import pandas as pd

from f1stewards.coding_queue import (
    ADJUDICATION_QUEUE_FILENAME,
    ADJUDICATION_SEED_COLUMNS,
    DOCUMENT_QUEUE_FILENAME,
    DOCUMENT_REVIEW_COLUMNS,
    EXCLUSION_QA_COLUMNS,
    EXCLUSION_QA_FILENAME,
    QUEUE_MANIFEST_FILENAME,
)
from f1stewards.coding_workspace import (
    WORKSPACE_ADJUDICATION_FILENAME,
    audit_full_corpus_coding_workspace,
    build_full_corpus_coding_workspace,
    load_protected_seed_bundle,
    validate_edited_full_corpus_coding_workspace,
    write_full_corpus_coding_workspace,
)


def frame_with_rows(columns: list[str], rows: list[dict[str, str]]) -> pd.DataFrame:
    return pd.DataFrame([{column: row.get(column, "") for column in columns} for row in rows])


def sample_seed_frames() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    documents = frame_with_rows(
        DOCUMENT_REVIEW_COLUMNS,
        [
            {
                "document_review_id": "document-primary",
                "document_id": "primary",
                "event_id": "2025-tst",
                "season": "2025",
                "round_number": "1",
                "eligibility_suggestion": "primary_candidate",
                "parser_review_required": "False",
            },
            {
                "document_review_id": "document-recalled",
                "document_id": "recalled",
                "event_id": "2025-tst",
                "season": "2025",
                "round_number": "1",
                "eligibility_suggestion": "version_resolution_required",
                "parser_review_required": "False",
            },
        ],
    )
    adjudications = frame_with_rows(
        ADJUDICATION_SEED_COLUMNS,
        [
            {
                "adjudication_seed_id": "seed-primary",
                "document_id": "primary",
                "event_id": "2025-tst",
                "season": "2025",
                "round_number": "1",
                "session_type_suggestion": "Race",
                "driver_number_suggestion": "22",
                "eligibility_suggestion": "primary_candidate",
                "parser_review_required": "False",
            },
            {
                "adjudication_seed_id": "seed-excluded",
                "document_id": "excluded",
                "event_id": "2025-tst",
                "season": "2025",
                "round_number": "1",
                "session_type_suggestion": "Practice",
                "driver_number_suggestion": "22",
                "eligibility_suggestion": "out_of_scope_suggestion",
                "parser_review_required": "False",
            },
        ],
    )
    exclusion_qa = frame_with_rows(
        EXCLUSION_QA_COLUMNS,
        [
            {
                "exclusion_qa_id": "qa-1",
                "document_id": "excluded",
                "event_id": "2025-tst",
                "season": "2025",
                "round_number": "1",
                "qa_stratum_id": "2025|practice|excluded",
                "qa_selection_rank": "1",
            }
        ],
    )
    return documents, adjudications, exclusion_qa


def sample_timing_context() -> tuple[pd.DataFrame, pd.DataFrame]:
    sessions = pd.DataFrame(
        [
            {
                "event_id": "2025-tst",
                "session_type": "Race",
                "timing_ingestion_status": "succeeded",
                "timing_classification_rows": 20,
                "timing_lap_rows": 1000,
                "timing_message_rows": 50,
                "timing_direct_timestamp_rows": 1000,
                "timing_derived_timestamp_rows": 0,
                "timing_missing_timestamp_rows": 0,
                "timing_incident_eligible_rows": 1000,
                "timing_pace_eligible_rows": 800,
                "timing_beyond_classified_rows": 2,
                "timing_missing_within_rows": 0,
                "timing_fallback_rows": 0,
            }
        ]
    )
    drivers = pd.DataFrame(
        [
            {
                "event_id": "2025-tst",
                "session_type": "Race",
                "driver_number": 22,
                "accused_driver_classified_laps_suggestion": 50,
                "accused_driver_stored_timing_laps": 51,
                "accused_driver_missing_within_rows": 0,
                "accused_driver_beyond_classified_rows": 1,
            }
        ]
    )
    return sessions, drivers


def write_seed_directory(path: Path) -> None:
    documents, adjudications, exclusion_qa = sample_seed_frames()
    payloads = {
        DOCUMENT_QUEUE_FILENAME: documents.to_csv(index=False, lineterminator="\n").encode(),
        ADJUDICATION_QUEUE_FILENAME: adjudications.to_csv(
            index=False, lineterminator="\n"
        ).encode(),
        EXCLUSION_QA_FILENAME: exclusion_qa.to_csv(index=False, lineterminator="\n").encode(),
    }
    path.mkdir(parents=True)
    for name, payload in payloads.items():
        (path / name).write_bytes(payload)
    manifest = {
        "outputs": {
            name: {
                "sha256": hashlib.sha256(payload).hexdigest(),
                "row_count": len(frame),
            }
            for (name, payload), frame in zip(
                payloads.items(),
                (documents, adjudications, exclusion_qa),
                strict=True,
            )
        }
    }
    (path / QUEUE_MANIFEST_FILENAME).write_text(
        json.dumps(manifest, sort_keys=True), encoding="utf-8"
    )


def test_workspace_prioritizes_review_and_joins_timing_context() -> None:
    documents, adjudications, exclusion_qa = sample_seed_frames()
    sessions, drivers = sample_timing_context()
    document_worklist, adjudication_worklist, qa_worklist = (
        build_full_corpus_coding_workspace(
            documents,
            adjudications,
            exclusion_qa,
            sessions,
            drivers,
        )
    )

    assert document_worklist["document_id"].tolist() == ["recalled", "primary"]
    primary = adjudication_worklist.set_index("adjudication_seed_id").loc["seed-primary"]
    assert primary["adjudication_instance_id"] == "seed-primary-01"
    assert bool(primary["timing_session_expected"])
    assert bool(primary["timing_session_loaded"])
    assert primary["timing_lap_rows"] == 1000
    assert bool(primary["accused_driver_result_present_suggestion"])
    assert primary["accused_driver_beyond_classified_rows"] == 1
    excluded = adjudication_worklist.set_index("adjudication_seed_id").loc["seed-excluded"]
    assert not bool(excluded["timing_session_expected"])
    assert not bool(excluded["timing_session_loaded"])
    assert qa_worklist.loc[0, "workspace_priority_bucket"] == "stratified_exclusion_qa"


def test_content_addressed_workspace_writes_repeats_and_audits(tmp_path: Path) -> None:
    seed_directory = tmp_path / "seed"
    output_root = tmp_path / "workspaces"
    write_seed_directory(seed_directory)
    sessions, drivers = sample_timing_context()

    output_directory, manifest, created = write_full_corpus_coding_workspace(
        seed_directory, output_root, sessions, drivers
    )
    repeated_directory, repeated_manifest, repeated_created = (
        write_full_corpus_coding_workspace(seed_directory, output_root, sessions, drivers)
    )

    assert created
    assert not repeated_created
    assert output_directory == repeated_directory
    assert manifest == repeated_manifest
    assert output_directory.name == manifest["workspace_id"]
    audit = audit_full_corpus_coding_workspace(
        seed_directory, output_directory, sessions, drivers
    )
    assert audit["status"].eq("pass").all()

    (output_directory / WORKSPACE_ADJUDICATION_FILENAME).write_text(
        "tampered\n", encoding="utf-8"
    )
    assert not audit_full_corpus_coding_workspace(
        seed_directory, output_directory, sessions, drivers
    )["status"].eq("pass").all()


def test_seed_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    seed_directory = tmp_path / "seed"
    write_seed_directory(seed_directory)
    (seed_directory / DOCUMENT_QUEUE_FILENAME).write_text("tampered\n", encoding="utf-8")

    try:
        load_protected_seed_bundle(seed_directory)
    except ValueError as exc:
        assert "hash mismatch" in str(exc)
    else:
        raise AssertionError("Tampered seed bundle was accepted")


def test_edited_workspace_allows_final_fields_and_supported_splits(tmp_path: Path) -> None:
    seed_directory = tmp_path / "seed"
    output_root = tmp_path / "workspaces"
    write_seed_directory(seed_directory)
    sessions, drivers = sample_timing_context()
    output_directory, _, _ = write_full_corpus_coding_workspace(
        seed_directory, output_root, sessions, drivers
    )
    path = output_directory / WORKSPACE_ADJUDICATION_FILENAME
    worklist = pd.read_csv(path, dtype=str, keep_default_na=False)
    primary = worklist[worklist["adjudication_seed_id"].eq("seed-primary")].iloc[0].copy()
    worklist.loc[
        worklist["adjudication_seed_id"].eq("seed-primary"),
        ["adjudication_id_final", "include_primary_final", "coder_id"],
    ] = ["adj-primary-a", "true", "coder-1"]
    primary["adjudication_instance_id"] = "seed-primary-02"
    primary["adjudication_id_final"] = "adj-primary-b"
    primary["include_primary_final"] = "true"
    primary["coder_id"] = "coder-1"
    worklist = pd.concat([worklist, primary.to_frame().T], ignore_index=True)
    worklist.to_csv(path, index=False, lineterminator="\n")

    validation = validate_edited_full_corpus_coding_workspace(
        seed_directory, output_directory, sessions, drivers
    )
    assert validation["status"].eq("pass").all()

    tampered = pd.read_csv(path, dtype=str, keep_default_na=False)
    tampered.loc[0, "source_url"] = "https://example.invalid/changed"
    tampered.to_csv(path, index=False, lineterminator="\n")
    failed = validate_edited_full_corpus_coding_workspace(
        seed_directory, output_directory, sessions, drivers
    )
    protected = failed.set_index("control").loc[
        "adjudication_coding_worklist:protected_lineage"
    ]
    assert protected["status"] == "fail"


def test_edited_workspace_rejects_invalid_corrected_sanction_fields(
    tmp_path: Path,
) -> None:
    seed_directory = tmp_path / "seed"
    output_root = tmp_path / "workspaces"
    write_seed_directory(seed_directory)
    sessions, drivers = sample_timing_context()
    output_directory, _, _ = write_full_corpus_coding_workspace(
        seed_directory, output_root, sessions, drivers
    )
    path = output_directory / WORKSPACE_ADJUDICATION_FILENAME
    worklist = pd.read_csv(path, dtype=str, keep_default_na=False)
    worklist.loc[0, "penalty_points_final"] = "-1"
    worklist.loc[0, "fault_language_final"] = "unsupported_judgment"
    worklist.to_csv(path, index=False, lineterminator="\n")

    validation = validate_edited_full_corpus_coding_workspace(
        seed_directory, output_directory, sessions, drivers
    ).set_index("control")

    assert (
        validation.loc[
            "adjudication_coding_worklist:corrected_outcome_fields", "status"
        ]
        == "fail"
    )
