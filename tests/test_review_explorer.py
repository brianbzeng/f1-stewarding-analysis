import json
from pathlib import Path

import pandas as pd
import pytest

from f1stewards.review_explorer import (
    QA_EVIDENCE_FIELDS,
    QUEUE_SPECS,
    REVIEW_LEDGER_SCHEMA_VERSION,
    apply_review_ledger,
    build_review_explorer_payload,
    enrich_exclusion_qa_evidence,
    render_review_explorer_html,
    validate_review_explorer_payload,
    workspace_input_sha256,
)


def _queue_frame(queue_name: str) -> pd.DataFrame:
    spec = QUEUE_SPECS[queue_name]
    columns = [
        column
        for column in spec["display_fields"]
        if column not in spec.get("derived_fields", [])
    ]
    row = {column: "" for column in columns}
    row.update(
        {
            spec["id_field"]: f"{queue_name}-1",
            "workspace_review_order": "1",
            "workspace_priority_bucket": "primary_candidate",
            "season": "2025",
            "event_name": "Test Grand Prix",
            "title": "Official decision",
            "source_url": "https://www.fia.com/test-decision.pdf",
            "review_status": "",
        }
    )
    if queue_name == "documents":
        row.update(
            {
                "eligibility_suggestion": "primary_candidate",
                "eligibility_basis": "Race decision matched the study scope.",
            }
        )
    elif queue_name == "adjudications":
        row.update(
            {
                "adjudication_seed_id": "seed-1",
                "document_id": "document-1",
                "driver_number_suggestion": "1",
                "driver_name_suggestion": "Driver One",
                "offence_family_suggestion": "causing_collision",
                "outcome_family_suggestion": "time_penalty",
                "eligibility_suggestion": "primary_candidate",
                "reason_text": "Reason with </script><script>alert(1)</script> text.",
            }
        )
    else:
        row.update(
            {
                "document_id": "document-1",
                "qa_stratum_id": "2025|excluded|test",
                "eligibility_basis": "Proposed exclusion.",
            }
        )
    return pd.DataFrame([row], columns=columns)


def _write_workspace(parent: Path) -> Path:
    workspace = parent / "full-coding-test"
    workspace.mkdir()
    manifest = {
        "workspace_id": workspace.name,
        "schema_version": "full-corpus-coding-workspace-v2",
        "protected_seed_manifest_sha256": "seed-hash",
        "timing_context_sha256": "timing-hash",
        "workspace_content_sha256": "starter-hash",
        "interpretation_boundary": "Suggestions are not analytical findings.",
    }
    (workspace / "workspace_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    for queue_name, spec in QUEUE_SPECS.items():
        _queue_frame(queue_name).to_csv(
            workspace / spec["filename"], index=False, lineterminator="\n"
        )
    return workspace


def test_payload_covers_all_queues_and_preserves_blocked_release(tmp_path: Path) -> None:
    workspace = _write_workspace(tmp_path)
    validation = pd.DataFrame(
        [{"control": "protected_lineage", "status": "pass", "detail": "retained"}]
    )

    payload = build_review_explorer_payload(
        workspace,
        validation=validation,
        git_commit="abc1234",
    )

    assert payload["metadata"]["review_target_count"] == 3
    assert payload["metadata"]["review_complete_count"] == 0
    assert payload["metadata"]["release_status"] == "blocked_pending_human_review"
    assert payload["metadata"]["current_workspace_sha256"] == workspace_input_sha256(
        workspace
    )
    assert set(payload["queues"]) == {"documents", "adjudications", "exclusion_qa"}
    assert payload["validation_controls"][0]["status"] == "pass"
    assert payload["queues"]["exclusion_qa"][0]["reason_text"].startswith(
        "Reason with"
    )


def test_rendered_console_has_review_workflow_and_safe_embedded_json(
    tmp_path: Path,
) -> None:
    payload = build_review_explorer_payload(_write_workspace(tmp_path))

    output = render_review_explorer_html(payload)

    assert "Document dispositions" in output
    assert "Adjudication coding" in output
    assert "Exclusion QA" in output
    assert "Export draft ledger" in output
    assert "apply-full-corpus-review-ledger" in output
    assert 'role="tablist"' in output
    assert 'aria-live="polite"' in output
    assert "\\u003c/script\\u003e\\u003cscript\\u003ealert(1)" in output
    assert "Reason with </script><script>alert(1)" not in output


def test_payload_rejects_nationality_fields(tmp_path: Path) -> None:
    payload = build_review_explorer_payload(_write_workspace(tmp_path))
    payload["queues"]["documents"][0]["driver_nationality"] = "Test"

    with pytest.raises(ValueError, match="Nationality fields"):
        validate_review_explorer_payload(payload)


def test_qa_evidence_enrichment_accepts_consistent_splits_and_rejects_disagreement() -> None:
    qa = pd.DataFrame([{"exclusion_qa_id": "qa-1", "document_id": "doc-1"}])
    base = {field: "" for field in QA_EVIDENCE_FIELDS}
    base["reason_text"] = "Protected reason"
    adjudications = pd.DataFrame(
        [
            {
                "document_id": "doc-1",
                "adjudication_instance_id": "seed-01",
                **base,
            },
            {
                "document_id": "doc-1",
                "adjudication_instance_id": "seed-02",
                **base,
            },
        ]
    )

    enriched = enrich_exclusion_qa_evidence(qa, adjudications)
    assert enriched.loc[0, "reason_text"] == "Protected reason"

    adjudications.loc[1, "reason_text"] = "Different reason"
    with pytest.raises(ValueError, match="disagree"):
        enrich_exclusion_qa_evidence(qa, adjudications)


def _write_ledger(
    path: Path,
    workspace: Path,
    changes: dict,
    *,
    digest: str | None = None,
) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": REVIEW_LEDGER_SCHEMA_VERSION,
                "workspace_id": workspace.name,
                "source_workspace_sha256": digest or workspace_input_sha256(workspace),
                "changes": changes,
            }
        ),
        encoding="utf-8",
    )


def test_apply_ledger_changes_only_editable_fields_in_separate_workspace(
    tmp_path: Path,
) -> None:
    workspace = _write_workspace(tmp_path)
    ledger = tmp_path / "ledger.json"
    _write_ledger(
        ledger,
        workspace,
        {
            "adjudications": [
                {
                    "row_id": "adjudications-1",
                    "fields": {
                        "coder_id": "reviewer-a",
                        "review_status": "single_coded_pending_human",
                    },
                }
            ]
        },
    )

    output, applied = apply_review_ledger(workspace, ledger, tmp_path / "edited")

    source = pd.read_csv(
        workspace / QUEUE_SPECS["adjudications"]["filename"],
        dtype=str,
        keep_default_na=False,
    )
    edited = pd.read_csv(
        output / QUEUE_SPECS["adjudications"]["filename"],
        dtype=str,
        keep_default_na=False,
    )
    assert output != workspace
    assert source.loc[0, "review_status"] == ""
    assert edited.loc[0, "review_status"] == "single_coded_pending_human"
    assert edited.loc[0, "coder_id"] == "reviewer-a"
    assert edited.loc[0, "title"] == source.loc[0, "title"]
    assert applied["adjudications"] == 2


def test_apply_ledger_rejects_stale_or_protected_edits(tmp_path: Path) -> None:
    workspace = _write_workspace(tmp_path)
    stale = tmp_path / "stale.json"
    _write_ledger(stale, workspace, {}, digest="not-current")
    with pytest.raises(ValueError, match="stale"):
        apply_review_ledger(workspace, stale, tmp_path / "stale-output")

    protected = tmp_path / "protected.json"
    _write_ledger(
        protected,
        workspace,
        {
            "documents": [
                {"row_id": "documents-1", "fields": {"title": "Changed"}}
            ]
        },
    )
    with pytest.raises(ValueError, match="protected-field"):
        apply_review_ledger(workspace, protected, tmp_path / "protected-output")
    assert not (tmp_path / "protected-output" / workspace.name).exists()
