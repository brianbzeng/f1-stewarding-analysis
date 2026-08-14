from pathlib import Path

import pandas as pd

from f1stewards.study_v2_strict_audit import (
    _evidence_span,
    _fault_matches,
    _grid_match,
    _penalty_guideline_assessment,
    _rule_reference,
    _source_derived_exclusion_basis,
)


def test_evidence_span_keeps_fact_decision_and_reason() -> None:
    row = pd.Series(
        {
            "fact_text": "Cars 1 and 2 collided.",
            "decision_text": "A 10 second time penalty.",
            "reason_text": "Car 1 was predominantly to blame.",
        }
    )

    span = _evidence_span(row)

    assert "Fact: Cars 1 and 2 collided." in span
    assert "Decision: A 10 second time penalty." in span
    assert "Reason: Car 1 was predominantly to blame." in span


def test_rule_reference_extracts_article_and_appendix() -> None:
    row = pd.Series(
        {
            "infringement_text": "Breach of Appendix L Chapter IV Article 2(d).",
            "reason_text": "Article 33.3 also applies.",
        }
    )

    reference = _rule_reference(row)

    assert "Appendix L Chapter IV Article 2" in reference
    assert "Article 33.3" in reference


def test_2025_collision_penalty_baseline_and_mitigation() -> None:
    base = {
        "event_date": "2025-07-01T00:00:00",
        "incident_family_final": "causing_collision",
        "outcome_family_final": "time_penalty",
        "grid_places_final": "",
    }

    assert (
        _penalty_guideline_assessment(pd.Series({**base, "penalty_seconds_final": "10"}))
        == "within_contemporaneous_public_guideline"
    )
    assert (
        _penalty_guideline_assessment(pd.Series({**base, "penalty_seconds_final": "5"}))
        == "within_guideline_with_documented_or_possible_mitigation"
    )


def test_pre_guideline_case_is_not_backcast() -> None:
    row = pd.Series(
        {
            "event_date": "2024-07-01T00:00:00",
            "incident_family_final": "causing_collision",
            "outcome_family_final": "time_penalty",
            "penalty_seconds_final": "10",
            "grid_places_final": "",
        }
    )

    assert _penalty_guideline_assessment(row) == "no_public_contemporaneous_penalty_guideline"


def test_grid_match_accepts_common_fia_word_orders() -> None:
    for decision in (
        "Drop of 3 Grid Positions for the next race.",
        "A 3 Grid Place Drop.",
        "A grid penalty of 3 positions.",
    ):
        row = pd.Series({"grid_places_final": "3", "decision_text": decision})
        assert _grid_match(row)


def test_fault_match_rejects_negated_predominant_fault() -> None:
    row = pd.Series(
        {
            "fault_language_final": "predominantly_to_blame",
            "reason_text": "None of the drivers was predominately at fault.",
            "include_secondary_final": "false",
        }
    )

    assert not _fault_matches(row)


def test_fault_match_accepts_fia_spelling_variants() -> None:
    for reason in (
        "The driver was fully to blame.",
        "The driver was solely responsible.",
    ):
        row = pd.Series(
            {
                "fault_language_final": "wholly_to_blame",
                "reason_text": reason,
                "include_secondary_final": "false",
            }
        )
        assert _fault_matches(row)


def test_exclusion_classifier_uses_session_and_investigated_conduct() -> None:
    practice_collision = pd.Series(
        {
            "raw_text": "Official decision body",
            "content_document_class": "steward_decision",
            "session_type_raw": "Practice 1",
            "session_type_suggestion": "Practice 1",
            "fact_text": "Collision between Car 18 and Car 16.",
            "infringement_text": "Causing a collision.",
            "title": "Incident with Car 16",
        }
    )
    qualifying_collision = practice_collision.copy()
    qualifying_collision["session_type_raw"] = "Qualifying"
    unsafe_release = practice_collision.copy()
    unsafe_release["session_type_raw"] = "Sprint"
    unsafe_release["fact_text"] = "Unsafe release of Car 31 and collision with Car 16."
    unsafe_release["infringement_text"] = "Unsafe release."

    assert _source_derived_exclusion_basis(practice_collision) == "out_of_scope_session"
    assert (
        _source_derived_exclusion_basis(qualifying_collision) == "outside_secondary_offence_scope"
    )
    assert _source_derived_exclusion_basis(unsafe_release) == "outside_offence_scope"


def test_governance_decision_is_not_forcing_off_track() -> None:
    row = pd.Series(
        {
            "raw_text": "Official decision body",
            "content_document_class": "steward_decision",
            "session_type_raw": "Race",
            "session_type_suggestion": "Race",
            "fact_text": "Security protocols were not enforced and spectators accessed the track.",
            "infringement_text": "Failure to take reasonable measures.",
            "title": "Decision - AGPC",
        }
    )

    assert _source_derived_exclusion_basis(row) == "outside_offence_scope"


def test_protocol_and_config_exist() -> None:
    root = Path(__file__).resolve().parents[1]

    assert (root / "config" / "study_v2_strict_model_audit.yml").exists()
    assert (root / "docs" / "study_v2_strict_model_audit_protocol.md").exists()
