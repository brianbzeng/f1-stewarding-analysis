from pathlib import Path

import pandas as pd

from f1stewards.catalog import build_study_event_catalog, write_study_event_catalog
from f1stewards.config import load_study_events


def _schedule_row(
    *,
    round_number: int,
    event_name: str,
    event_date: str,
    race_date: str,
    event_format: str = "conventional",
    sprint_name: str = "Practice 3",
) -> dict[str, object]:
    return {
        "RoundNumber": round_number,
        "EventName": event_name,
        "EventDate": pd.Timestamp(event_date),
        "EventFormat": event_format,
        "Session1": "Practice 1",
        "Session1Date": pd.Timestamp(event_date, tz="UTC"),
        "Session2": "Qualifying",
        "Session2Date": pd.Timestamp(event_date, tz="UTC"),
        "Session3": sprint_name,
        "Session3Date": pd.Timestamp(event_date, tz="UTC"),
        "Session4": "Qualifying",
        "Session4Date": pd.Timestamp(event_date, tz="UTC"),
        "Session5": "Race",
        "Session5Date": pd.Timestamp(race_date),
    }


def test_catalog_builds_modern_and_legacy_archive_contracts(tmp_path: Path) -> None:
    schedules = {
        2018: pd.DataFrame(
            [
                _schedule_row(
                    round_number=10,
                    event_name="British Grand Prix",
                    event_date="2018-07-08",
                    race_date="2018-07-08 14:10:00+01:00",
                )
            ]
        ),
        2025: pd.DataFrame(
            [
                _schedule_row(
                    round_number=11,
                    event_name="Austrian Grand Prix",
                    event_date="2025-06-29",
                    race_date="2025-06-29 15:00:00+02:00",
                    event_format="sprint",
                    sprint_name="Sprint",
                )
            ]
        ),
    }
    settings = {
        "completed_seasons": [2018, 2025],
        "expected_event_counts": {2018: 1, 2025: 1},
        "season_slugs": {2025: "season-2025-2071"},
        "regimes": {2018: "pre", 2025: "public"},
        "event_codes": {"British Grand Prix": "gbr", "Austrian Grand Prix": "aut"},
        "archive_event_overrides": {},
        "archive_url_overrides": {
            "2018-gbr": (
                "https://www.fia.com/events/fia-formula-one-world-championship/"
                "season-2018/eventtiming-information-8"
            )
        },
        "pilot_event_ids": ["2025-aut"],
        "schedule_source_url": "https://github.com/theOehrly/Fast-F1",
        "modern_archive_url_template": (
            "https://www.fia.com/documents/championships/"
            "fia-formula-one-world-championship-14/event/{event_slug}/season/{season_slug}"
        ),
        "legacy_event_url_template": (
            "https://www.fia.com/championship/events/fia-formula-one-world-championship/"
            "season-2018/{event_slug}"
        ),
    }

    events = build_study_event_catalog(schedules, settings)

    assert [event.pilot_id for event in events] == ["2018-gbr", "2025-aut"]
    assert events[0].archive_system == "legacy_event_timing"
    assert str(events[0].archive_url).endswith("/season-2018/eventtiming-information-8")
    assert events[0].event_timezone == "+01:00"
    assert events[1].archive_system == "document_archive"
    assert str(events[1].archive_url).endswith(
        "/event/Austrian%20Grand%20Prix/season/season-2025-2071"
    )
    assert events[1].has_sprint is True
    assert events[1].is_pilot is True

    catalog_path = tmp_path / "study_events.csv"
    digest = write_study_event_catalog(events, catalog_path)
    loaded = load_study_events(catalog_path)
    assert len(digest) == 64
    assert loaded == events


def test_catalog_rejects_unexpected_schedule_count() -> None:
    settings = {
        "completed_seasons": [2025],
        "expected_event_counts": {2025: 2},
        "season_slugs": {2025: "season-2025-2071"},
        "regimes": {2025: "public"},
        "event_codes": {},
        "pilot_event_ids": [],
        "schedule_source_url": "https://github.com/theOehrly/Fast-F1",
        "modern_archive_url_template": "https://www.fia.com/{event_slug}/{season_slug}",
        "legacy_event_url_template": "https://www.fia.com/{event_slug}",
    }

    try:
        build_study_event_catalog({2025: pd.DataFrame({"RoundNumber": []})}, settings)
    except ValueError as exc:
        assert "expected 2" in str(exc)
    else:
        raise AssertionError("unexpected schedule count must fail")


def test_catalog_rejects_unknown_archive_url_override() -> None:
    schedule = pd.DataFrame(
        [
            _schedule_row(
                round_number=11,
                event_name="Austrian Grand Prix",
                event_date="2025-06-29",
                race_date="2025-06-29 15:00:00+02:00",
            )
        ]
    )
    settings = {
        "completed_seasons": [2025],
        "expected_event_counts": {2025: 1},
        "season_slugs": {2025: "season-2025-2071"},
        "regimes": {2025: "public"},
        "event_codes": {"Austrian Grand Prix": "aut"},
        "archive_url_overrides": {"2025-mco": "https://www.fia.com/not-this-event"},
        "pilot_event_ids": [],
        "schedule_source_url": "https://github.com/theOehrly/Fast-F1",
        "modern_archive_url_template": "https://www.fia.com/{event_slug}/{season_slug}",
        "legacy_event_url_template": "https://www.fia.com/{event_slug}",
    }

    try:
        build_study_event_catalog({2025: schedule}, settings)
    except ValueError as exc:
        assert "unknown event ids" in str(exc)
    else:
        raise AssertionError("unknown archive URL override must fail")
