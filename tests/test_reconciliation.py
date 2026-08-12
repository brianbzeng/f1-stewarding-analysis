import hashlib
import json
from datetime import UTC, datetime

import pytest

from f1stewards.config import PROJECT_ROOT
from f1stewards.manual import (
    CodedAdjudication,
    HarmAssessment,
    ImpactAssessment,
    IndependentReviewRecord,
)
from f1stewards.readiness import load_pilot_manual_records
from f1stewards.reconciliation import (
    reconcile_pilot_records,
    serialize_reconciliation_bundle,
    write_reconciliation_bundle,
)

FIXED_REVIEW_TIME = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)
INPUT_HASHES = {
    "coded_adjudications": "a" * 64,
    "cross_event_sanction_effects": "0" * 64,
    "harm_assessments": "d" * 64,
    "impact_assessments": "b" * 64,
    "incident_locations": "e" * 64,
    "incident_relations": "f" * 64,
    "independent_review": "c" * 64,
}


def coded_record() -> CodedAdjudication:
    return CodedAdjudication.model_validate(
        {
            "adjudication_id": "adj-test",
            "incident_id": "inc-test",
            "event_id": "2025-aut",
            "source_document_id": "fia-test",
            "source_url": "https://www.fia.com/test.pdf",
            "accused_driver_number": 22,
            "affected_driver_number": 43,
            "session_type": "Race",
            "lap_number": 31,
            "turn_number": 4,
            "incident_family": "causing_collision",
            "outcome_family": "time_penalty",
            "penalty_seconds": 10,
            "penalty_points": 2,
            "grid_places": None,
            "fault_language": "wholly_to_blame",
            "evidence_video": True,
            "evidence_positioning": False,
            "evidence_telemetry": False,
            "evidence_team_radio": False,
            "guideline_regime": "public_driving_and_penalty_guidelines",
            "guideline_clause": "Penalty_2025_AppL_ChIV_2d",
            "guideline_expected_outcome": "10s_baseline",
            "conformance_status": "conformant",
            "mitigating_factor_written": False,
            "first_lap": False,
            "include_primary": True,
            "coder_id": "initial",
            "review_status": "single_coded_pending_human",
            "coding_notes": "Initial coding.",
        }
    )


def impact_record() -> ImpactAssessment:
    return ImpactAssessment.model_validate(
        {
            "impact_assessment_id": "impact-test",
            "adjudication_id": "adj-test",
            "event_id": "2025-aut",
            "source_document_id": "fia-test",
            "classification_source_document_id": "fia-classification",
            "driver_number": 22,
            "sanction_type": "time_penalty",
            "penalty_seconds": 10,
            "grid_places": None,
            "sanction_application": "post_race_added",
            "impact_level": "mechanical",
            "official_finish_position": 4,
            "counterfactual_finish_position": 3,
            "positions_gained_without_penalty": 1,
            "official_points": 12,
            "counterfactual_points": 15,
            "points_gained_without_penalty": 3,
            "podium_changed": True,
            "win_changed": False,
            "calculation_method": "Same-lap reranking.",
            "assumptions": "No strategy counterfactual.",
            "review_status": "single_coded_pending_human",
        }
    )


def harm_record() -> HarmAssessment:
    return HarmAssessment.model_validate(
        {
            "harm_assessment_id": "harm-test",
            "adjudication_id": "adj-test",
            "incident_id": "inc-test",
            "event_id": "2025-aut",
            "source_document_id": "fia-test",
            "classification_source_document_id": "fia-classification",
            "affected_driver_number": 43,
            "counterparty_driver_number": 22,
            "responsibility_status": "fault_established",
            "harm_evidence_level": "observed",
            "damage_evidence": "no_confirmed_damage",
            "damage_type": "none_identified",
            "repair_stop_required": "no",
            "pit_lap": None,
            "pit_response_status": "no",
            "pit_lane_loss_seconds": None,
            "repair_stationary_seconds": None,
            "retirement_status": "no_retirement",
            "position_before": 12,
            "position_after": 13,
            "net_positions_lost_observed": 1,
            "affected_relative_time_loss_seconds": 2.1,
            "post_incident_clean_laps": 6,
            "persistent_pace_status": "no_detectable_loss",
            "persistent_delta_per_lap_seconds": None,
            "persistent_laps_exposed": None,
            "persistent_loss_seconds_lower": None,
            "persistent_loss_seconds_estimate": None,
            "persistent_loss_seconds_upper": None,
            "net_effect_direction": "harmed",
            "benefit_mechanism": None,
            "evidence_urls": "https://www.fia.com/test.pdf",
            "calculation_method": "Observed timing.",
            "assumptions": "No causal counterfactual.",
            "review_status": "single_coded_pending_human",
        }
    )


def review(
    target_type: str,
    target_id: str,
    status: str = "agree",
    corrections: dict | None = None,
) -> IndependentReviewRecord:
    completed = status != "pending"
    return IndependentReviewRecord.model_validate(
        {
            "review_id": f"review-{target_id}",
            "target_type": target_type,
            "target_id": target_id,
            "evidence_urls": "https://www.fia.com/test.pdf",
            "initial_summary": "Initial summary.",
            "review_status": status,
            "reviewer_id": "human-reviewer" if completed else None,
            "reviewed_at_utc": FIXED_REVIEW_TIME if completed else None,
            "review_minutes": 4.5 if completed else None,
            "corrected_fields_json": json.dumps(corrections) if corrections else None,
            "reviewer_notes": "Evidence supports the correction." if corrections else None,
        }
    )


def complete_reviews(
    adjudication_status: str = "agree",
    corrections: dict | None = None,
) -> list[IndependentReviewRecord]:
    return [
        review("adjudication", "adj-test", adjudication_status, corrections),
        review("impact_assessment", "impact-test"),
        review("harm_assessment", "harm-test"),
    ]


def test_agreement_creates_new_double_coded_versions_and_status_audit() -> None:
    bundle = reconcile_pilot_records(
        [coded_record()], [impact_record()], [harm_record()], [], [], [],
        complete_reviews(), INPUT_HASHES
    )

    assert bundle.adjudications.loc[0, "review_status"] == "double_coded"
    assert bundle.impacts.loc[0, "review_status"] == "double_coded"
    assert bundle.harms.loc[0, "review_status"] == "double_coded"
    assert set(bundle.audit.field_name) == {"review_status"}
    assert bundle.manifest["field_correction_count"] == 0
    assert bundle.manifest["review_decision_counts"] == {"agree": 3}


def test_correction_is_validated_and_preserved_in_field_level_audit() -> None:
    bundle = reconcile_pilot_records(
        [coded_record()],
        [impact_record()],
        [harm_record()],
        [],
        [],
        [],
        complete_reviews("correct", {"lap_number": 32, "coding_notes": "Reviewed."}),
        INPUT_HASHES,
    )

    assert bundle.adjudications.loc[0, "lap_number"] == 32
    changed = bundle.audit[bundle.audit.field_name.ne("review_status")]
    assert set(changed.field_name) == {"lap_number", "coding_notes"}
    assert bundle.manifest["field_correction_count"] == 2


@pytest.mark.parametrize(
    ("corrections", "message"),
    [
        ({"source_url": "https://www.fia.com/other.pdf"}, "protected fields"),
        ({"lap_number": 31}, "unchanged fields"),
        ({"not_a_field": "value"}, "unknown correction fields"),
    ],
)
def test_invalid_correction_patch_is_rejected(corrections: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        reconcile_pilot_records(
                [coded_record()],
                [impact_record()],
                [harm_record()],
                [],
                [],
                [],
                complete_reviews("correct", corrections),
            INPUT_HASHES,
        )


def test_unresolved_review_cannot_be_reconciled() -> None:
    reviews = [
        review("adjudication", "adj-test", "pending"),
        review("impact_assessment", "impact-test"),
        review("harm_assessment", "harm-test"),
    ]

    with pytest.raises(ValueError, match="unresolved review"):
        reconcile_pilot_records(
            [coded_record()], [impact_record()], [harm_record()], [], [], [],
            reviews, INPUT_HASHES
        )


def test_content_addressed_writer_is_idempotent_and_detects_tampering(tmp_path) -> None:
    bundle = reconcile_pilot_records(
        [coded_record()], [impact_record()], [harm_record()], [], [], [],
        complete_reviews(), INPUT_HASHES
    )
    directory, created = write_reconciliation_bundle(bundle, tmp_path)
    second_directory, second_created = write_reconciliation_bundle(bundle, tmp_path)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    serialized = serialize_reconciliation_bundle(bundle)

    assert created is True
    assert second_created is False
    assert second_directory == directory
    assert manifest["output_sha256"]["adjudications.csv"] == hashlib.sha256(
        serialized["adjudications.csv"]
    ).hexdigest()

    (directory / "adjudications.csv").write_text("tampered\n", encoding="utf-8")
    with pytest.raises(FileExistsError, match="differs from validated output"):
        write_reconciliation_bundle(bundle, tmp_path)


def test_actual_pilot_shapes_reconcile_after_synthetic_completed_reviews() -> None:
    manual_root = PROJECT_ROOT / "data" / "manual"
    records = load_pilot_manual_records(
        manual_root / "pilot_coded_adjudications.csv",
        manual_root / "pilot_impact_assessments.csv",
        manual_root / "pilot_harm_assessments.csv",
        manual_root / "pilot_incident_locations.csv",
        manual_root / "pilot_incident_relations.csv",
        manual_root / "pilot_cross_event_sanction_effects.csv",
        manual_root / "pilot_independent_review.csv",
    )
    completed_reviews = [
        IndependentReviewRecord.model_validate(
            {
                **record.model_dump(mode="json"),
                "review_status": "agree",
                "reviewer_id": "synthetic-test-reviewer",
                "reviewed_at_utc": FIXED_REVIEW_TIME,
                "review_minutes": 1.0,
            }
        )
        for record in records.reviews
    ]

    bundle = reconcile_pilot_records(
        records.adjudications,
        records.impacts,
        records.harms,
        records.locations,
        records.relations,
        records.cross_event_effects,
        completed_reviews,
        INPUT_HASHES,
    )

    assert len(bundle.adjudications) == 9
    assert len(bundle.impacts) == 4
    assert len(bundle.harms) == 9
    assert len(bundle.locations) == 1
    assert len(bundle.relations) == 2
    assert len(bundle.cross_event_effects) == 1
    assert len(bundle.audit) == 26
    assert bundle.manifest["review_target_count"] == 26
