from datetime import date
from pathlib import Path

import pytest

from f1stewards.config import (
    load_analysis_thresholds,
    load_international_sporting_code_issues,
    load_regulatory_sources,
    load_sporting_regulation_issues,
    select_international_sporting_code,
    select_sporting_regulation,
)


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
