import json
from pathlib import Path

from f1stewards.review_explorer import QUEUE_SPECS, REVIEW_LEDGER_SCHEMA_VERSION

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PARSER_TRIAGE_LEDGER = (
    PROJECT_ROOT / "data" / "manual" / "review_ledgers" / "parser_format_triage_v1.json"
)
SCOPE_CONFLICT_LEDGER = (
    PROJECT_ROOT / "data" / "manual" / "review_ledgers" / "analytical_scope_conflicts_v1.json"
)


def _assert_pending_human_ledger(ledger: dict, expected_rows: int) -> None:
    assert ledger["schema_version"] == REVIEW_LEDGER_SCHEMA_VERSION
    assert len(ledger["source_workspace_sha256"]) == 64
    assert "independent review" in ledger["review_basis"]
    assert set(ledger["changes"]) == {"documents", "adjudications"}
    assert len(ledger["changes"]["documents"]) == expected_rows
    assert len(ledger["changes"]["adjudications"]) == expected_rows
    for queue_name, changes in ledger["changes"].items():
        ids = [change["row_id"] for change in changes]
        assert len(ids) == len(set(ids))
        for change in changes:
            assert set(change["fields"]) <= set(QUEUE_SPECS[queue_name]["editable_fields"])
            assert change["fields"]["review_status"] == "single_coded_pending_human"


def test_parser_format_triage_ledger_preserves_pending_human_boundary() -> None:
    ledger = json.loads(PARSER_TRIAGE_LEDGER.read_text(encoding="utf-8"))

    _assert_pending_human_ledger(ledger, 17)

    documents = ledger["changes"]["documents"]
    adjudications = ledger["changes"]["adjudications"]
    assert sum(change["fields"]["eligibility_final"] == "include" for change in documents) == 1
    assert sum(change["fields"]["include_primary_final"] == "true" for change in adjudications) == 1
    hungarian = next(
        change for change in adjudications if "fia-2025-hun-f1ff0743742b" in change["row_id"]
    )
    assert hungarian["fields"]["lap_number_final"] == "29"
    assert hungarian["fields"]["location_final"] == "Turn 4"
    assert hungarian["fields"]["outcome_family_final"] == "no_further_action"


def test_scope_conflict_ledger_records_secondary_scope_and_version_control() -> None:
    ledger = json.loads(SCOPE_CONFLICT_LEDGER.read_text(encoding="utf-8"))
    _assert_pending_human_ledger(ledger, 18)

    documents = ledger["changes"]["documents"]
    adjudications = ledger["changes"]["adjudications"]
    assert sum(change["fields"]["eligibility_final"] == "include" for change in documents) == 8
    assert (
        sum(change["fields"]["include_secondary_final"] == "true" for change in adjudications) == 8
    )
    assert not any(change["fields"]["include_primary_final"] == "true" for change in adjudications)
    predecessor = next(
        change for change in documents if "fia-2019-ita-b42dad90f42f" in change["row_id"]
    )
    assert predecessor["fields"]["version_status_final"] == "superseded"
    assert predecessor["fields"]["exclusion_reason_final"] == ("superseded_corrected_predecessor")
