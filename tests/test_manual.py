import pytest
from pydantic import ValidationError

from f1stewards.manual import (
    CodedAdjudication,
    CrossEventSanctionEffect,
    HarmAssessment,
    ImpactAssessment,
    IncidentLocation,
    IncidentRelation,
    IndependentReviewRecord,
)


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


def harm_payload() -> dict:
    return {
        "harm_assessment_id": "harm-test",
        "adjudication_id": "adj-test",
        "incident_id": "inc-test",
        "event_id": "2019-aut",
        "source_document_id": "fia-decision",
        "classification_source_document_id": "fia-classification",
        "affected_driver_number": 16,
        "counterparty_driver_number": 33,
        "responsibility_status": "shared_or_racing_incident",
        "harm_evidence_level": "observed",
        "damage_evidence": "no_confirmed_damage",
        "damage_type": "none_identified",
        "repair_stop_required": "no",
        "pit_lap": None,
        "pit_response_status": "no",
        "pit_lane_loss_seconds": None,
        "repair_stationary_seconds": None,
        "retirement_status": "no_retirement",
        "position_before": 1,
        "position_after": 2,
        "net_positions_lost_observed": 1,
        "affected_relative_time_loss_seconds": 1.683,
        "post_incident_clean_laps": 1,
        "persistent_pace_status": "no_detectable_loss",
        "persistent_delta_per_lap_seconds": None,
        "persistent_laps_exposed": None,
        "persistent_loss_seconds_lower": None,
        "persistent_loss_seconds_estimate": None,
        "persistent_loss_seconds_upper": None,
        "net_effect_direction": "harmed",
        "benefit_mechanism": None,
        "evidence_urls": "https://www.fia.com/test.pdf",
        "calculation_method": "official decision plus lap timing",
        "assumptions": "Observed effects are not a no-contact counterfactual.",
        "review_status": "single_coded_pending_human",
    }


def test_valid_observed_harm_without_confirmed_damage() -> None:
    record = HarmAssessment.model_validate(harm_payload())
    assert record.net_positions_lost_observed == 1


def test_repair_stop_requires_pit_evidence() -> None:
    payload = harm_payload()
    payload["repair_stop_required"] = "yes"
    with pytest.raises(ValidationError, match="require a pit lap"):
        HarmAssessment.model_validate(payload)


def test_modeled_persistent_loss_requires_complete_arithmetic() -> None:
    payload = harm_payload()
    payload["harm_evidence_level"] = "modeled"
    payload["persistent_pace_status"] = "modeled_loss"
    with pytest.raises(ValidationError, match="complete modeled estimate"):
        HarmAssessment.model_validate(payload)


def test_harm_can_use_an_explicit_multi_lap_position_window() -> None:
    payload = harm_payload()
    payload["position_window_start_lap"] = 47
    payload["position_window_end_lap"] = 48
    record = HarmAssessment.model_validate(payload)
    assert record.position_window_end_lap == 48


def test_turn_range_requires_increasing_bounds() -> None:
    payload = {
        "location_id": "location-test",
        "incident_id": "inc-test",
        "event_id": "2025-aut",
        "source_document_id": "fia-test",
        "session_type": "Race",
        "lap_number": 54,
        "location_type": "turn_range",
        "turn_start_number": 4,
        "turn_end_number": 3,
        "location_text": "between Turns 3 and 4",
        "evidence_urls": "https://www.fia.com/test.pdf",
        "coding_notes": "Official turn range.",
        "coder_id": "test",
        "review_status": "single_coded_pending_human",
    }
    with pytest.raises(ValidationError, match="end after"):
        IncidentLocation.model_validate(payload)


def test_context_edge_can_preserve_mitigation_without_assigning_fault() -> None:
    record = IncidentRelation.model_validate(
        {
            "relation_id": "relation-test",
            "incident_id": "inc-test",
            "event_id": "2025-aut",
            "source_document_id": "fia-test",
            "sequence": 1,
            "source_driver_number": 22,
            "target_driver_number": 43,
            "relation_type": "visibility_obstruction",
            "relation_scope": "mitigating_context",
            "fault_attributed": False,
            "evidence_level": "official_explicit",
            "evidence_urls": "https://www.fia.com/test.pdf",
            "coding_notes": "Mitigation is not blame.",
            "coder_id": "test",
            "review_status": "single_coded_pending_human",
        }
    )
    assert record.fault_attributed is False


def test_cross_event_grid_effect_requires_exact_position_arithmetic() -> None:
    payload = {
        "cross_event_effect_id": "cross-event-test",
        "adjudication_id": "adj-test",
        "origin_event_id": "2025-aut",
        "application_event_id": "2025-gbr",
        "source_document_id": "fia-test",
        "driver_number": 12,
        "sanction_type": "grid_penalty",
        "nominal_grid_places": 3,
        "qualifying_position": 7,
        "starting_grid_position": 9,
        "realized_grid_places_lost": 3,
        "grid_effect_level": "mechanical",
        "official_finish_position": None,
        "race_status": "retired",
        "official_points": 0,
        "finish_effect_level": "not_estimable",
        "counterfactual_finish_position": None,
        "counterfactual_points": None,
        "application_grid_url": "https://www.fia.com/grid.pdf",
        "application_classification_url": "https://www.fia.com/classification.pdf",
        "evidence_urls": "https://www.fia.com/test.pdf",
        "calculation_method": "Grid arithmetic.",
        "assumptions": "Finish not estimated.",
        "review_status": "single_coded_pending_human",
    }
    with pytest.raises(ValidationError, match="does not match"):
        CrossEventSanctionEffect.model_validate(payload)


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
