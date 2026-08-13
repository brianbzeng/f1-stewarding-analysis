from datetime import date
from pathlib import Path

import pytest

from f1stewards.config import (
    load_analysis_thresholds,
    load_document_lineage,
    load_evidence_profiles,
    load_full_collection_settings,
    load_full_corpus_coding_settings,
    load_international_sporting_code_issues,
    load_regulatory_sources,
    load_retrieval_exceptions,
    load_sporting_regulation_issues,
    select_international_sporting_code,
    select_sporting_regulation,
)
from f1stewards.models import DocumentClass


def test_regulatory_sources_validate_and_cover_each_pilot() -> None:
    sources = load_regulatory_sources()
    covered = {event_id for source in sources for event_id in source.event_ids}

    assert covered == {"2019-aut", "2023-abu", "2025-aut"}
    assert sum(source.is_guideline for source in sources) == 2


def test_regulatory_sources_reject_unknown_event(tmp_path: Path) -> None:
    path = tmp_path / "sources.yml"
    path.write_text(
        """
regulatory_sources:
  - source_id: test-source
    document_type: test
    title: Test
    source_url: https://www.fia.com/test.pdf
    source_status: test
    applicability_status: contextual_only
    event_role: contextual
    event_ids: [2099-zzz]
    notes: Test
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Unknown event_ids"):
        load_regulatory_sources(path)


def test_analysis_thresholds_cover_all_planned_components() -> None:
    thresholds = load_analysis_thresholds()

    assert thresholds["pilot_scale"]["minimum_core_text_fraction"] == 0.95
    assert thresholds["consistency"]["validation_group"] == "event_id"
    assert thresholds["guideline_conformance"]["minimum_mappable_fraction"] == 0.8
    assert thresholds["competitive_impact"]["mechanical_same_lap_only"] is True
    assert thresholds["victim_harm"]["minimum_clean_laps_each_side"] == 5
    assert thresholds["victim_harm"]["prohibit_cross_unit_composite_score"] is True
    assert (
        thresholds["competitive_impact"]["next_event_grid_start_effect_tier"]
        == "mechanical"
    )
    assert (
        thresholds["competitive_impact"]["next_event_finish_effect_default_tier"]
        == "not_estimable"
    )
    assert thresholds["incident_context"]["fault_attribution_is_edge_specific"] is True


def test_full_collection_settings_cover_completed_study_seasons() -> None:
    settings = load_full_collection_settings()

    assert settings["completed_seasons"] == list(range(2018, 2026))
    assert sum(settings["expected_event_counts"].values()) == 173
    assert settings["season_slugs"][2025] == "season-2025-2071"
    assert settings["pilot_event_ids"] == ["2019-aut", "2023-abu", "2025-aut"]


def test_full_corpus_coding_settings_match_frozen_primary_scope() -> None:
    settings = load_full_corpus_coding_settings()

    assert settings["schema_version"] == "full_corpus_coding_v2"
    assert settings["primary_sessions"] == ["Race", "Sprint"]
    assert set(settings["primary_incident_patterns"]) == {
        "causing_collision",
        "forcing_off_track",
        "gaining_advantage_off_track",
        "unsafe_rejoin",
        "moving_under_braking",
        "multiple_defensive_moves",
    }
    assert "qualifying_impeding" in settings["secondary_incident_patterns"]
    assert settings["exclusion_quality_control"]["target_fraction"] == 0.1


def test_evidence_profiles_bound_retrieval_scope() -> None:
    profiles = load_evidence_profiles()

    assert profiles["decisions"] == {DocumentClass.STEWARD_DECISION}
    assert DocumentClass.SUMMONS in profiles["adjudications"]
    assert DocumentClass.OTHER not in profiles["full_recognized"]


def test_retrieval_exception_register_is_explicit(tmp_path: Path) -> None:
    path = tmp_path / "retrieval_exceptions.yml"
    path.write_text(
        """
retrieval_exceptions:
  - event_id: 2020-rus
    document_url: https://www.fia.com/broken.pdf
    source_availability_status: verified_unavailable
    verified_at: 2026-08-12
    note: Official link returns HTTP 404.
""".strip(),
        encoding="utf-8",
    )
    exceptions = load_retrieval_exceptions(path)
    exception = exceptions["https://www.fia.com/broken.pdf"]

    assert exception["event_id"] == "2020-rus"
    assert exception["source_availability_status"] == "verified_unavailable"
    assert "HTTP 404" in exception["note"]


def test_official_retrieval_exception_register_is_currently_empty() -> None:
    assert load_retrieval_exceptions() == {}


def test_document_lineage_register_has_unique_verified_links() -> None:
    links = load_document_lineage()

    assert len(links) == 15
    assert len({link["predecessor_document_id"] for link in links.values()}) == 15
    assert links["fia-2024-mex-9398d22e8e7e"]["event_id"] == "2024-mex"


def test_sporting_regulation_catalog_covers_2018_through_2025() -> None:
    issues = load_sporting_regulation_issues()

    assert len(issues) == 65
    assert {issue.season for issue in issues} == set(range(2018, 2026))
    assert sum(issue.document_url is not None for issue in issues) == 3


@pytest.mark.parametrize(
    ("season", "event_date", "expected_source_id"),
    [
        (2019, date(2019, 6, 30), "fia-f1sr-2019-03"),
        (2023, date(2023, 11, 26), "fia-f1sr-2023-07"),
        (2025, date(2025, 6, 29), "fia-f1sr-2025-05"),
        (2024, date(2024, 5, 1), "fia-f1sr-2024-06-v2"),
    ],
)
def test_sporting_regulation_selection_uses_event_date_and_precedence(
    season: int,
    event_date: date,
    expected_source_id: str,
) -> None:
    selected = select_sporting_regulation(
        load_sporting_regulation_issues(), season, event_date
    )

    assert selected.source_id == expected_source_id


def test_sporting_regulation_selection_rejects_date_before_catalog() -> None:
    with pytest.raises(ValueError, match="No 2018 Sporting Regulation issue"):
        select_sporting_regulation(
            load_sporting_regulation_issues(), 2018, date(2017, 1, 1)
        )


def test_international_sporting_code_catalog_covers_study_period() -> None:
    issues = load_international_sporting_code_issues()

    assert len(issues) == 9
    assert {issue.season for issue in issues} == set(range(2018, 2026))
    assert sum(issue.document_url is not None for issue in issues) == 8


@pytest.mark.parametrize(
    ("season", "event_date", "expected_source_id"),
    [
        (2019, date(2019, 6, 30), "fia-isc-2019-01"),
        (2020, date(2020, 3, 1), "fia-isc-2020-01"),
        (2020, date(2020, 7, 5), "fia-isc-2020-02"),
        (2023, date(2023, 11, 26), "fia-isc-2023-01"),
        (2025, date(2025, 6, 29), "fia-isc-2025-01"),
    ],
)
def test_international_sporting_code_selection_uses_effective_window(
    season: int,
    event_date: date,
    expected_source_id: str,
) -> None:
    selected = select_international_sporting_code(
        load_international_sporting_code_issues(), season, event_date
    )

    assert selected.source_id == expected_source_id
