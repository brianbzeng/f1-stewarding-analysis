from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from f1stewards.coding_queue import (
    ADJUDICATION_QUEUE_FILENAME,
    DOCUMENT_QUEUE_FILENAME,
    EXCLUSION_QA_FILENAME,
    QUEUE_MANIFEST_FILENAME,
    audit_full_corpus_seed_bundle,
    build_exclusion_qa_sample,
    build_full_corpus_coding_queues,
    infer_session_type,
    normalize_session_type,
    write_full_corpus_seed_bundle,
)
from f1stewards.config import PROJECT_ROOT, load_full_corpus_coding_settings


def outcome_row(
    document_id: str,
    *,
    session_type: str | None = "Race",
    title: str = "Infringement - Car 27 - Causing a collision with Car 4",
    fact_text: str | None = "Car 27 caused a collision with Car 4 at Turn 3.",
    infringement_text: str | None = "Breach of Appendix L Chapter IV Article 2 d).",
    decision_text: str | None = "10 second time penalty. 2 penalty points.",
    reason_text: str | None = "Video evidence was examined on lap 12.",
    driver_number: int | None = 27,
    driver_name: str | None = "Test Driver",
    is_recalled: bool = False,
    supersedes_document_id: str | None = None,
    successor_document_id: str | None = None,
    successor_count: int = 0,
    content_document_class: str | None = "steward_decision",
    parser_warnings_json: str | None = "[]",
) -> dict:
    return {
        "document_id": document_id,
        "event_id": "2025-tst",
        "season": 2025,
        "round_number": 1,
        "event_name": "Test Grand Prix",
        "event_date": date(2025, 1, 1),
        "guideline_regime": "public_driving_and_penalty_guidelines",
        "title": title,
        "source_url": f"https://www.fia.com/{document_id}.pdf",
        "published_at": pd.Timestamp("2025-01-01T12:00:00Z"),
        "archive_document_class": "steward_decision",
        "content_document_class": content_document_class,
        "content_classification_basis": "standard_decision_template",
        "source_availability_status": "advertised",
        "is_recalled": is_recalled,
        "supersedes_document_id": supersedes_document_id,
        "successor_document_id": successor_document_id,
        "successor_count": successor_count,
        "parser_version": "decision_parser_v4",
        "parser_warnings_json": parser_warnings_json,
        "driver_number": driver_number,
        "driver_name": driver_name,
        "session_type": session_type,
        "incident_time_raw": "12:30",
        "fact_text": fact_text,
        "infringement_text": infringement_text,
        "decision_text": decision_text,
        "reason_text": reason_text,
    }


def sample_population() -> pd.DataFrame:
    return pd.DataFrame(
        [
            outcome_row(
                "primary",
                fact_text=(
                    "Car 27 caused a collision with Car 4; Car 81 took avoiding action at Turn 3."
                ),
            ),
            outcome_row(
                "secondary",
                session_type="Qualifying",
                title="Decision - Car 27 - Alleged impeding of Car 4",
                fact_text="Car 27 allegedly impeded Car 4.",
                decision_text="Drop of 3 grid positions.",
            ),
            outcome_row(
                "recalled-linked",
                is_recalled=True,
                successor_document_id="primary",
                successor_count=1,
                content_document_class=None,
                session_type=None,
                driver_number=None,
                driver_name=None,
                fact_text=None,
                infringement_text=None,
                decision_text=None,
                reason_text=None,
                parser_warnings_json=None,
            ),
            outcome_row(
                "recalled-unresolved",
                is_recalled=True,
                successor_count=0,
                content_document_class=None,
                session_type=None,
                driver_number=None,
                driver_name=None,
                fact_text=None,
                infringement_text=None,
                decision_text=None,
                reason_text=None,
                parser_warnings_json=None,
            ),
            outcome_row(
                "summons-content",
                content_document_class="summons",
                title="Decision - Summons - Car 27",
            ),
            outcome_row(
                "unsafe-release",
                title="Infringement - Car 27 - Unsafe release",
                fact_text="Car 27 was released in an unsafe condition from its pit stop.",
                decision_text="5 second time penalty.",
            ),
            outcome_row(
                "conflicting",
                title="Decision - Car 27 - Unsafe release and collision with Car 4",
                fact_text="Car 27 caused a collision during an unsafe release.",
                decision_text="5 second time penalty.",
            ),
            outcome_row(
                "ambiguous",
                title="Decision - Car 27 - Incident with Car 4 at Turn 3",
                fact_text="Incident between Car 27 and Car 4.",
                decision_text="No further action.",
            ),
        ]
    )


def test_session_normalization_preserves_primary_and_non_primary_distinction() -> None:
    assert normalize_session_type("Race – 2019 Russian Grand Prix") == "Race"
    assert normalize_session_type("Race (temporarily stopped)") == "Race"
    assert normalize_session_type("Race (Reconnaissance Laps)") == "Pre-session"
    assert normalize_session_type("Sprint Qualifying", 2021) == "Sprint"
    assert normalize_session_type("Sprint Qualifying", 2024) == "Sprint Qualifying"
    assert normalize_session_type(None) == "Unknown"


def test_session_inference_requires_explicit_source_language() -> None:
    sprint = pd.Series(
        outcome_row(
            "sprint-session",
            session_type=None,
            decision_text="10 seconds added to elapsed Sprint time.",
        )
    )
    practice = pd.Series(
        outcome_row(
            "practice-session",
            session_type=None,
            reason_text="The alleged impeding occurred during Practice 2 at Turn 17.",
        )
    )
    ambiguous = pd.Series(
        outcome_row(
            "ambiguous-session",
            session_type=None,
            reason_text="The Race Director reviewed the incident before the Race.",
        )
    )

    assert infer_session_type(sprint) == "Sprint"
    assert infer_session_type(practice) == "Practice"
    assert infer_session_type(ambiguous) == "Unknown"


def test_reason_text_can_identify_incident_without_triggering_damage_exclusions() -> None:
    population = pd.DataFrame(
        [
            outcome_row(
                "reason-contact",
                title="Decision - Car 27 - Incident with Car 4",
                fact_text="Incident between Car 27 and Car 4.",
                reason_text=(
                    "Car 27 made contact with Car 4 and damaged the front wing of Car 4."
                ),
            )
        ]
    )
    documents, _ = build_full_corpus_coding_queues(
        population, load_full_corpus_coding_settings()
    )

    row = documents.iloc[0]
    assert row["offence_family_suggestion"] == "causing_collision"
    assert row["eligibility_suggestion"] == "primary_candidate"


def test_observed_out_of_scope_session_precedes_family_conflict() -> None:
    population = pd.DataFrame(
        [
            outcome_row(
                "practice-conflict",
                session_type="Practice 2",
                title="Decision - Car 27 - Leaving the track at a track limit",
                fact_text="Car 27 was leaving the track and gaining an advantage at a track limit.",
            )
        ]
    )
    documents, candidates = build_full_corpus_coding_queues(
        population, load_full_corpus_coding_settings()
    )

    row = documents.iloc[0]
    assert bool(row["family_conflict_suggestion"])
    assert row["eligibility_suggestion"] == "out_of_scope_suggestion"
    assert candidates.iloc[0]["candidate_action_suggestion"] == "review_exclusion"


def test_pit_stop_unsafe_release_wording_is_excluded() -> None:
    population = pd.DataFrame(
        [
            outcome_row(
                "pit-stop-release",
                title="Decision - Car 27 - Unsafe pit stop release",
                fact_text="Car 27 was released from a pit stop in an unsafe condition.",
            )
        ]
    )
    documents, candidates = build_full_corpus_coding_queues(
        population, load_full_corpus_coding_settings()
    )

    row = documents.iloc[0]
    assert row["offence_family_suggestion"] == "pit_lane_procedure"
    assert row["eligibility_suggestion"] == "out_of_scope_suggestion"
    assert candidates.iloc[0]["candidate_action_suggestion"] == "review_exclusion"


def test_qualifying_impeding_is_secondary_even_with_procedural_context() -> None:
    population = pd.DataFrame(
        [
            outcome_row(
                "pit-exit-impeding",
                session_type="Qualifying",
                title="Decision - Car 27 - Alleged impeding at Pit Exit",
                fact_text="Car 27 impeded Car 4 while stopped at the pit exit.",
            )
        ]
    )
    documents, candidates = build_full_corpus_coding_queues(
        population, load_full_corpus_coding_settings()
    )

    row = documents.iloc[0]
    assert bool(row["family_conflict_suggestion"])
    assert row["eligibility_suggestion"] == "secondary_candidate"
    assert candidates.iloc[0]["candidate_action_suggestion"] == (
        "review_secondary_adjudication"
    )


def test_non_impeding_qualifying_incident_is_out_of_scope() -> None:
    population = pd.DataFrame(
        [
            outcome_row(
                "qualifying-track-limits",
                session_type="Qualifying",
                title="Decision - Car 27 - Track limits",
                fact_text="Car 27 left the track and gained a lasting advantage.",
            )
        ]
    )
    documents, _ = build_full_corpus_coding_queues(
        population, load_full_corpus_coding_settings()
    )

    assert documents.iloc[0]["eligibility_suggestion"] == "out_of_scope_suggestion"


def test_negated_reason_does_not_create_qualifying_impeding_candidate() -> None:
    population = pd.DataFrame(
        [
            outcome_row(
                "no-impeding",
                session_type="Qualifying",
                title="Decision - Car 27 - Turn 2 incident",
                fact_text="Incident between Car 27 and Car 4.",
                reason_text="The Stewards determined that Car 27 did not impede Car 4.",
            )
        ]
    )
    documents, _ = build_full_corpus_coding_queues(
        population, load_full_corpus_coding_settings()
    )

    row = documents.iloc[0]
    assert row["offence_family_suggestion"] == "unclassified"
    assert row["eligibility_suggestion"] == "out_of_scope_suggestion"


def test_full_corpus_queues_preserve_versions_and_only_seed_live_decisions() -> None:
    settings = load_full_corpus_coding_settings()
    documents, candidates = build_full_corpus_coding_queues(sample_population(), settings)

    assert len(documents) == 8
    assert len(candidates) == 5
    indexed = documents.set_index("document_id")
    assert indexed.loc["primary", "eligibility_suggestion"] == "primary_candidate"
    assert indexed.loc["secondary", "eligibility_suggestion"] == "secondary_candidate"
    assert (
        indexed.loc["recalled-linked", "version_state_suggestion"]
        == "recalled_linked_predecessor"
    )
    assert (
        indexed.loc["recalled-unresolved", "eligibility_suggestion"]
        == "version_resolution_required"
    )
    assert (
        indexed.loc["summons-content", "eligibility_suggestion"]
        == "content_exclusion_suggestion"
    )
    assert (
        indexed.loc["unsafe-release", "offence_family_suggestion"]
        == "pit_lane_procedure"
    )
    assert indexed.loc["conflicting", "eligibility_suggestion"] == "manual_offence_review"
    assert indexed.loc["ambiguous", "eligibility_suggestion"] == "manual_offence_review"
    assert not {"recalled-linked", "recalled-unresolved", "summons-content"} & set(
        candidates["document_id"]
    )

    primary = candidates.set_index("document_id").loc["primary"]
    assert primary["driver_number_basis_suggestion"] == "parsed_decision_heading"
    assert primary["participant_driver_numbers_suggestion"] == "27|4|81"
    assert primary["affected_driver_numbers_suggestion"] == "4|81"
    assert bool(primary["multi_party_suggestion"])
    assert primary["penalty_seconds_suggestion"] == 10
    assert primary["penalty_points_suggestion"] == 2

    qa = build_exclusion_qa_sample(documents, settings)
    assert qa["document_id"].tolist() == ["unsafe-release"]
    assert qa["qa_stratum_size"].tolist() == [1]
    assert qa["qa_selection_rank"].tolist() == [1]
    assert qa["qa_disposition"].eq("").all()


def test_official_title_driver_number_is_a_traceable_fallback() -> None:
    population = pd.DataFrame(
        [
            outcome_row(
                "title-driver",
                title="Doc 47 - Infringement - Car 81 - Causing a collision",
                driver_number=None,
                driver_name=None,
            )
        ]
    )
    _, candidates = build_full_corpus_coding_queues(
        population, load_full_corpus_coding_settings()
    )

    candidate = candidates.iloc[0]
    assert candidate["driver_number_suggestion"] == 81
    assert (
        candidate["driver_number_basis_suggestion"]
        == "official_title_first_car_reference"
    )
    assert candidate["candidate_action_suggestion"] == "review_primary_adjudication"


def test_seed_bundle_is_deterministic_protected_and_auditable(tmp_path: Path) -> None:
    population = sample_population()
    settings = load_full_corpus_coding_settings()
    settings_path = PROJECT_ROOT / "config" / "full_corpus_coding.yml"
    documents, candidates = build_full_corpus_coding_queues(population, settings)
    exclusion_qa = build_exclusion_qa_sample(documents, settings)

    manifest, first_status = write_full_corpus_seed_bundle(
        population,
        documents,
        candidates,
        exclusion_qa,
        tmp_path,
        settings,
        settings_path,
    )
    repeated_manifest, second_status = write_full_corpus_seed_bundle(
        population,
        documents,
        candidates,
        exclusion_qa,
        tmp_path,
        settings,
        settings_path,
    )

    assert manifest == repeated_manifest
    assert set(first_status.values()) == {"written"}
    assert set(second_status.values()) == {"unchanged"}
    assert manifest["source_counts"]["archive_outcome_labels"] == 8
    assert (tmp_path / DOCUMENT_QUEUE_FILENAME).exists()
    assert (tmp_path / ADJUDICATION_QUEUE_FILENAME).exists()
    assert (tmp_path / EXCLUSION_QA_FILENAME).exists()
    assert (tmp_path / QUEUE_MANIFEST_FILENAME).exists()
    assert audit_full_corpus_seed_bundle(
        population,
        documents,
        candidates,
        exclusion_qa,
        tmp_path,
        settings,
        settings_path,
    )["status"].eq("pass").all()

    (tmp_path / DOCUMENT_QUEUE_FILENAME).write_text("tampered\n", encoding="utf-8")
    with pytest.raises(FileExistsError, match="differs from the generated seed"):
        write_full_corpus_seed_bundle(
            population,
            documents,
            candidates,
            exclusion_qa,
            tmp_path,
            settings,
            settings_path,
        )
    audit = audit_full_corpus_seed_bundle(
        population,
        documents,
        candidates,
        exclusion_qa,
        tmp_path,
        settings,
        settings_path,
    )
    assert audit.set_index("control").loc[DOCUMENT_QUEUE_FILENAME, "status"] == "fail"
