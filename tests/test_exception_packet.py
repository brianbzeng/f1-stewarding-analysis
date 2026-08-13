import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from f1stewards.coding_workspace import (
    WORKSPACE_ADJUDICATION_FILENAME,
    WORKSPACE_DOCUMENT_FILENAME,
    WORKSPACE_EXCLUSION_QA_FILENAME,
    WORKSPACE_MANIFEST_FILENAME,
)
from f1stewards.exception_packet import (
    EXCEPTION_MANIFEST_FILENAME,
    INVESTIGATION_FILENAME,
    LINKAGE_FILENAME,
    build_exception_packet_payloads,
    write_exception_packet,
)
from f1stewards.first_pass import FIRST_PASS_AUDIT_FILENAME, FIRST_PASS_MANIFEST_FILENAME


def _write_csv(path: Path, frame: pd.DataFrame) -> bytes:
    frame.to_csv(path, index=False, lineterminator="\n")
    return path.read_bytes()


def _write_first_pass_fixture(parent: Path) -> Path:
    workspace = parent / "full-coding-test"
    workspace.mkdir()
    documents = pd.DataFrame(
        [
            {
                "document_review_id": "document-review-1",
                "document_id": "doc-1",
                "event_id": "2025-test",
                "season": "2025",
                "round_number": "1",
                "event_name": "Test Grand Prix",
                "title": "Test decision",
                "source_url": "https://www.fia.com/test.pdf",
                "workspace_review_order": "1",
                "version_state_suggestion": "live_standalone",
                "parser_review_required": "False",
                "family_conflict_suggestion": "True",
                "session_type_suggestion": "Qualifying",
                "session_scope_suggestion": "secondary_qualifying",
                "offence_family_suggestion": "qualifying_impeding",
                "eligibility_suggestion": "secondary_candidate",
                "review_status": "",
            }
        ]
    )
    adjudications = pd.DataFrame(
        [
            {
                "adjudication_instance_id": "adjudication-seed-1-01",
                "document_id": "doc-1",
                "event_id": "2025-test",
                "source_url": "https://www.fia.com/test.pdf",
                "workspace_review_order": "1",
                "driver_number_suggestion": "1",
                "driver_name_suggestion": "Driver One",
                "participant_driver_numbers_suggestion": "1|2",
                "outcome_family_suggestion": "no_further_action",
                "fact_text": "Fact",
                "infringement_text": "Infringement",
                "decision_text": "Decision",
                "reason_text": "Reason",
                "review_status": "",
            }
        ]
    )
    exclusion_qa = pd.DataFrame(
        [
            {
                "exclusion_qa_id": "exclusion-qa-1",
                "document_id": "doc-1",
                "event_id": "2025-test",
                "source_url": "https://www.fia.com/test.pdf",
                "workspace_review_order": "1",
                "review_status": "",
            }
        ]
    )
    audit = pd.DataFrame(
        [
            {
                "queue_name": "documents",
                "row_id": "document-review-1",
                "event_id": "2025-test",
                "source_url": "https://www.fia.com/test.pdf",
                "first_pass_action": "unresolved",
                "action_basis": "cross-family conflict requires source review",
                "fields_populated": "",
            },
            {
                "queue_name": "adjudications",
                "row_id": "adjudication-seed-1-01",
                "event_id": "2025-test",
                "source_url": "https://www.fia.com/test.pdf",
                "first_pass_action": "unresolved",
                "action_basis": "manual adjudication path: manual_split_or_scope_review",
                "fields_populated": "",
            },
            {
                "queue_name": "exclusion_qa",
                "row_id": "exclusion-qa-1",
                "event_id": "2025-test",
                "source_url": "https://www.fia.com/test.pdf",
                "first_pass_action": "unresolved",
                "action_basis": "source-level exclusion audit cannot be auto-confirmed",
                "fields_populated": "",
            },
        ]
    )
    frames = {
        WORKSPACE_DOCUMENT_FILENAME: documents,
        WORKSPACE_ADJUDICATION_FILENAME: adjudications,
        WORKSPACE_EXCLUSION_QA_FILENAME: exclusion_qa,
        FIRST_PASS_AUDIT_FILENAME: audit,
    }
    outputs = {}
    for filename, frame in frames.items():
        payload = _write_csv(workspace / filename, frame)
        outputs[filename] = {
            "sha256": hashlib.sha256(payload).hexdigest(),
            "row_count": len(frame),
        }
    (workspace / WORKSPACE_MANIFEST_FILENAME).write_text(
        json.dumps({"workspace_id": workspace.name}), encoding="utf-8"
    )
    (workspace / FIRST_PASS_MANIFEST_FILENAME).write_text(
        json.dumps(
            {
                "first_pass_id": "fixture-first-pass",
                "workspace_id": workspace.name,
                "output_workspace_sha256": "fixture-workspace-hash",
                "outputs": outputs,
            }
        ),
        encoding="utf-8",
    )
    return workspace


def test_exception_packet_collapses_cross_queue_rows_to_one_investigation(
    tmp_path: Path,
) -> None:
    workspace = _write_first_pass_fixture(tmp_path)

    output, manifest, created = write_exception_packet(workspace, tmp_path / "packets")

    investigations = pd.read_csv(
        output / INVESTIGATION_FILENAME, dtype=str, keep_default_na=False
    )
    linkage = pd.read_csv(output / LINKAGE_FILENAME, dtype=str, keep_default_na=False)
    row = investigations.iloc[0]
    assert created
    assert len(investigations) == 1
    assert len(linkage) == 3
    assert row["queue_memberships"] == "documents|adjudications|exclusion_qa"
    assert row["linked_queue_rows"] == "3"
    assert row["priority_bucket"] == "analytical_scope_conflict"
    assert row["evidence_status"] == "full_standard_sections"
    assert row["reason_text"] == "Reason"
    assert "single incident family" in row["review_questions"]
    assert "proposed exclusion" in row["review_questions"]
    assert manifest["summary"]["duplicate_queue_rows_eliminated"] == 2
    assert manifest["summary"]["all_three_queue_documents"] == 1
    assert (output / EXCEPTION_MANIFEST_FILENAME).exists()


def test_exception_packet_is_deterministic_and_rejects_tampered_inputs(
    tmp_path: Path,
) -> None:
    workspace = _write_first_pass_fixture(tmp_path)

    first_payloads, first_manifest = build_exception_packet_payloads(workspace)
    second_payloads, second_manifest = build_exception_packet_payloads(workspace)
    output, written_manifest, created = write_exception_packet(
        workspace, tmp_path / "packets"
    )
    repeated_output, repeated_manifest, repeated_created = write_exception_packet(
        workspace, tmp_path / "packets"
    )

    assert first_payloads == second_payloads
    assert first_manifest == second_manifest == written_manifest == repeated_manifest
    assert created and not repeated_created
    assert output == repeated_output

    with (workspace / FIRST_PASS_AUDIT_FILENAME).open("a", encoding="utf-8") as stream:
        stream.write("tampered\n")
    with pytest.raises(ValueError, match="hash mismatch"):
        build_exception_packet_payloads(workspace)
