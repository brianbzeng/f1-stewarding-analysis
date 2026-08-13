import json
from pathlib import Path

import pandas as pd
import pytest

from f1stewards.coding_queue import FINAL_ADJUDICATION_FIELDS, FINAL_DOCUMENT_FIELDS
from f1stewards.coding_workspace import (
    WORKSPACE_ADJUDICATION_FILENAME,
    WORKSPACE_DOCUMENT_FILENAME,
    WORKSPACE_EXCLUSION_QA_FILENAME,
    WORKSPACE_MANIFEST_FILENAME,
)
from f1stewards.first_pass import (
    FIRST_PASS_AUDIT_FILENAME,
    FIRST_PASS_MANIFEST_FILENAME,
    build_first_pass_payloads,
    explicit_fault_language,
    write_first_pass_workspace,
)


def _frame(rows: list[dict[str, str]], required: list[str]) -> pd.DataFrame:
    columns = list(dict.fromkeys([*required, *(key for row in rows for key in row)]))
    return pd.DataFrame(
        [{column: row.get(column, "") for column in columns} for row in rows],
        columns=columns,
    )


def _write_workspace(parent: Path) -> Path:
    workspace = parent / "full-coding-test"
    workspace.mkdir()
    (workspace / WORKSPACE_MANIFEST_FILENAME).write_text(
        json.dumps(
            {
                "workspace_id": workspace.name,
                "schema_version": "full-corpus-coding-workspace-v2",
            }
        ),
        encoding="utf-8",
    )
    documents = _frame(
        [
            {
                "document_review_id": "doc-safe",
                "event_id": "2025-test",
                "source_url": "https://www.fia.com/safe.pdf",
                "eligibility_suggestion": "primary_candidate",
                "parser_review_required": "False",
                "family_conflict_suggestion": "False",
                "version_state_suggestion": "live_standalone",
                "session_scope_suggestion": "primary_race_sprint",
                "offence_family_suggestion": "causing_collision",
                "offence_family_group_suggestion": "primary",
            },
            {
                "document_review_id": "doc-conflict",
                "event_id": "2025-test",
                "source_url": "https://www.fia.com/conflict.pdf",
                "eligibility_suggestion": "secondary_candidate",
                "parser_review_required": "False",
                "family_conflict_suggestion": "True",
                "version_state_suggestion": "live_standalone",
                "session_scope_suggestion": "secondary_qualifying",
                "offence_family_suggestion": "qualifying_impeding",
                "offence_family_group_suggestion": "secondary",
            },
            {
                "document_review_id": "doc-parser-exclusion",
                "event_id": "2025-test",
                "source_url": "https://www.fia.com/parser-exclusion.pdf",
                "eligibility_suggestion": "out_of_scope_suggestion",
                "parser_review_required": "True",
                "family_conflict_suggestion": "False",
                "version_state_suggestion": "live_standalone",
                "session_scope_suggestion": "primary_race_sprint",
                "offence_family_suggestion": "lap_time_or_delta_procedure",
                "offence_family_group_suggestion": "excluded",
            },
        ],
        [
            "document_review_id",
            "event_id",
            "source_url",
            "eligibility_suggestion",
            "parser_review_required",
            "family_conflict_suggestion",
            "version_state_suggestion",
            "session_scope_suggestion",
            "offence_family_suggestion",
            "offence_family_group_suggestion",
            *FINAL_DOCUMENT_FIELDS,
        ],
    )
    adjudications = _frame(
        [
            {
                "adjudication_instance_id": "seed-safe-01",
                "event_id": "2025-test",
                "source_url": "https://www.fia.com/safe.pdf",
                "candidate_action_suggestion": "review_primary_adjudication",
                "parser_review_required": "False",
                "family_conflict_suggestion": "False",
                "driver_number_suggestion": "44",
                "affected_driver_numbers_suggestion": "1",
                "session_type_suggestion": "Race",
                "lap_numbers_suggestion": "12",
                "turn_numbers_suggestion": "3|4",
                "offence_family_suggestion": "causing_collision",
                "offence_family_group_suggestion": "primary",
                "outcome_family_suggestion": "time_penalty",
                "penalty_seconds_suggestion": "10",
                "penalty_points_suggestion": "2",
                "reason_text": "The driver of Car 44 was wholly to blame.",
            },
            {
                "adjudication_instance_id": "seed-manual-01",
                "event_id": "2025-test",
                "source_url": "https://www.fia.com/manual.pdf",
                "candidate_action_suggestion": "manual_split_or_scope_review",
                "parser_review_required": "True",
                "family_conflict_suggestion": "False",
            },
            {
                "adjudication_instance_id": "seed-parser-exclusion-01",
                "event_id": "2025-test",
                "source_url": "https://www.fia.com/parser-exclusion.pdf",
                "candidate_action_suggestion": "manual_split_or_scope_review",
                "parser_review_required": "True",
                "family_conflict_suggestion": "False",
                "eligibility_suggestion": "out_of_scope_suggestion",
                "session_type_suggestion": "Race",
                "session_scope_suggestion": "primary_race_sprint",
                "offence_family_suggestion": "lap_time_or_delta_procedure",
                "offence_family_group_suggestion": "excluded",
                "outcome_family_suggestion": "other",
            },
        ],
        [
            "adjudication_instance_id",
            "event_id",
            "source_url",
            "candidate_action_suggestion",
            "parser_review_required",
            "family_conflict_suggestion",
            "driver_number_suggestion",
            "affected_driver_numbers_suggestion",
            "session_type_suggestion",
            "session_scope_suggestion",
            "lap_numbers_suggestion",
            "turn_numbers_suggestion",
            "offence_family_suggestion",
            "offence_family_group_suggestion",
            "outcome_family_suggestion",
            "penalty_seconds_suggestion",
            "penalty_points_suggestion",
            "grid_places_suggestion",
            "reason_text",
            *FINAL_ADJUDICATION_FIELDS,
        ],
    )
    exclusion_qa = pd.DataFrame(
        [
            {
                "exclusion_qa_id": "qa-1",
                "event_id": "2025-test",
                "source_url": "https://www.fia.com/qa.pdf",
                "qa_disposition": "",
                "reviewer_id": "",
                "review_status": "",
            }
        ]
    )
    documents.to_csv(workspace / WORKSPACE_DOCUMENT_FILENAME, index=False, lineterminator="\n")
    adjudications.to_csv(
        workspace / WORKSPACE_ADJUDICATION_FILENAME, index=False, lineterminator="\n"
    )
    exclusion_qa.to_csv(
        workspace / WORKSPACE_EXCLUSION_QA_FILENAME, index=False, lineterminator="\n"
    )
    return workspace


def test_first_pass_prefills_safe_rows_and_preserves_exceptions(tmp_path: Path) -> None:
    workspace = _write_workspace(tmp_path)

    output, manifest, created = write_first_pass_workspace(workspace, tmp_path / "first-pass")

    documents = pd.read_csv(
        output / WORKSPACE_DOCUMENT_FILENAME, dtype=str, keep_default_na=False
    ).set_index("document_review_id")
    adjudications = pd.read_csv(
        output / WORKSPACE_ADJUDICATION_FILENAME, dtype=str, keep_default_na=False
    ).set_index("adjudication_instance_id")
    qa = pd.read_csv(output / WORKSPACE_EXCLUSION_QA_FILENAME, dtype=str, keep_default_na=False)
    assert created
    assert documents.loc["doc-safe", "eligibility_final"] == "include"
    assert documents.loc["doc-safe", "review_status"] == "single_coded_pending_human"
    assert documents.loc["doc-conflict", "review_status"] == ""
    assert documents.loc["doc-parser-exclusion", "eligibility_final"] == "exclude"
    assert (
        documents.loc["doc-parser-exclusion", "exclusion_reason_final"]
        == "excluded_offence_family:lap_time_or_delta_procedure"
    )
    assert adjudications.loc["seed-safe-01", "include_primary_final"] == "true"
    assert adjudications.loc["seed-safe-01", "incident_id_final"].startswith("incident-src-")
    assert adjudications.loc["seed-safe-01", "fault_language_final"] == "wholly_to_blame"
    assert adjudications.loc["seed-safe-01", "location_final"] == "Turns 3-4"
    assert adjudications.loc["seed-manual-01", "review_status"] == ""
    assert adjudications.loc["seed-parser-exclusion-01", "include_primary_final"] == "false"
    assert adjudications.loc["seed-parser-exclusion-01", "review_status"] == (
        "single_coded_pending_human"
    )
    assert qa.loc[0, "qa_disposition"] == ""
    assert manifest["summary"]["documents"] == {
        "prefilled_rows": 2,
        "unresolved_rows": 1,
    }
    assert manifest["summary"]["adjudications"]["prefilled_rows"] == 2
    assert manifest["summary"]["exclusion_qa"]["prefilled_rows"] == 0
    assert not manifest["controls"]["analytical_release_authorized"]
    assert manifest["controls"]["parser_warning_inclusion_rows_prefilled"] == {
        "documents": 0,
        "adjudications": 0,
    }
    assert manifest["controls"]["parser_warning_exclusion_rows_prefilled"] == {
        "documents": 1,
        "adjudications": 1,
    }
    assert (output / FIRST_PASS_AUDIT_FILENAME).exists()
    assert (output / FIRST_PASS_MANIFEST_FILENAME).exists()


def test_first_pass_is_deterministic_and_idempotent(tmp_path: Path) -> None:
    workspace = _write_workspace(tmp_path)

    first_payloads, first_manifest = build_first_pass_payloads(workspace)
    second_payloads, second_manifest = build_first_pass_payloads(workspace)
    output, written_manifest, created = write_first_pass_workspace(
        workspace, tmp_path / "first-pass"
    )
    repeated_output, repeated_manifest, repeated_created = write_first_pass_workspace(
        workspace, tmp_path / "first-pass"
    )

    assert first_payloads == second_payloads
    assert first_manifest == second_manifest == written_manifest == repeated_manifest
    assert created and not repeated_created
    assert output == repeated_output


def test_first_pass_never_overwrites_preexisting_editable_values(tmp_path: Path) -> None:
    workspace = _write_workspace(tmp_path)
    path = workspace / WORKSPACE_DOCUMENT_FILENAME
    documents = pd.read_csv(path, dtype=str, keep_default_na=False)
    documents.loc[documents["document_review_id"].eq("doc-safe"), FINAL_DOCUMENT_FIELDS] = [
        "effective",
        "primary",
        "causing_collision",
        "include",
        "",
        "human-coder",
        "adjudicated",
        "Existing reviewed value.",
    ]
    documents.to_csv(path, index=False, lineterminator="\n")

    output, _, _ = write_first_pass_workspace(workspace, tmp_path / "first-pass")
    result = pd.read_csv(
        output / WORKSPACE_DOCUMENT_FILENAME, dtype=str, keep_default_na=False
    ).set_index("document_review_id")
    audit = pd.read_csv(
        output / FIRST_PASS_AUDIT_FILENAME, dtype=str, keep_default_na=False
    ).set_index("row_id")

    assert result.loc["doc-safe", "reviewer_id"] == "human-coder"
    assert result.loc["doc-safe", "review_status"] == "adjudicated"
    assert audit.loc["doc-safe", "first_pass_action"] == "unresolved"
    assert "pre-existing" in audit.loc["doc-safe", "action_basis"]


@pytest.mark.parametrize(
    ("reason", "secondary", "expected"),
    [
        ("No driver was wholly or predominantly to blame.", False, "no_conclusion"),
        ("Neither driver was predominantly to blame.", False, "no_conclusion"),
        ("The collision was not through the fault of either driver.", False, "no_conclusion"),
        ("The Stewards considered this a racing incident.", False, "racing_incident"),
        (
            "This was a racing incident and no driver was predominantly to blame.",
            False,
            "racing_incident",
        ),
        ("Both drivers contributed to the collision.", False, "shared_fault"),
        ("The driver was wholly to blame.", False, "wholly_to_blame"),
        ("The driver was fully at fault.", False, "wholly_to_blame"),
        ("The driver was solely responsible.", False, "wholly_to_blame"),
        ("The driver was predominately to blame.", False, "predominantly_to_blame"),
        ("The driver was predominantly at fault.", False, "predominantly_to_blame"),
        ("The driver was mainly at fault.", False, "mainly_at_fault"),
        ("The car impeded another driver.", True, "not_applicable"),
        ("The evidence was reviewed.", False, ""),
    ],
)
def test_explicit_fault_language_is_conservative(
    reason: str, secondary: bool, expected: str
) -> None:
    assert explicit_fault_language(reason, secondary=secondary) == expected
