import pytest
from pydantic import ValidationError

from f1stewards.manual import CodedAdjudication, ImpactAssessment, IndependentReviewRecord


def base_payload() -> dict:
    return {
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
        "coder_id": "test",
        "review_status": "single_coded_pending_human",
        "coding_notes": "Test record.",
    }


def test_valid_coded_adjudication() -> None:
    record = CodedAdjudication.model_validate(base_payload())
    assert record.penalty_seconds == 10


def test_time_penalty_requires_seconds() -> None:
    payload = base_payload()
    payload["penalty_seconds"] = None
    with pytest.raises(ValidationError, match="require penalty_seconds"):
        CodedAdjudication.model_validate(payload)


def impact_payload() -> dict:
    return {
        "impact_assessment_id": "impact-test",
        "adjudication_id": "adj-test",
        "event_id": "2023-abu",
        "source_document_id": "fia-decision",
        "classification_source_document_id": "fia-classification",
        "driver_number": 11,
        "sanction_type": "time_penalty",
        "penalty_seconds": 5,
        "grid_places": None,
        "sanction_application": "post_race_added",
        "impact_level": "mechanical",
        "official_finish_position": 4,
        "counterfactual_finish_position": 2,
        "positions_gained_without_penalty": 2,
        "official_points": 12,
        "counterfactual_points": 18,
        "points_gained_without_penalty": 6,
        "podium_changed": True,
        "win_changed": False,
        "calculation_method": "same-lap re-ranking",
        "assumptions": "Test assumptions.",
        "review_status": "single_coded_pending_human",
    }


def test_valid_mechanical_impact() -> None:
    record = ImpactAssessment.model_validate(impact_payload())
    assert record.positions_gained_without_penalty == 2


def test_served_penalty_cannot_be_labeled_mechanical() -> None:
    payload = impact_payload()
    payload["sanction_application"] = "served_during_race"
    with pytest.raises(ValidationError, match="post-race-added"):
        ImpactAssessment.model_validate(payload)


def review_payload() -> dict:
    return {
        "review_id": "review-adj-test",
        "target_type": "adjudication",
        "target_id": "adj-test",
        "evidence_urls": "https://www.fia.com/test.pdf",
        "initial_summary": "Test initial code.",
        "review_status": "pending",
        "reviewer_id": None,
        "reviewed_at_utc": None,
        "review_minutes": None,
        "corrected_fields_json": None,
        "reviewer_notes": None,
    }


def test_pending_review_is_valid() -> None:
    record = IndependentReviewRecord.model_validate(review_payload())
    assert record.review_status == "pending"


def test_correction_requires_audit_fields() -> None:
    payload = review_payload()
    payload["review_status"] = "correct"
    with pytest.raises(ValidationError, match="completed review requires"):
        IndependentReviewRecord.model_validate(payload)
