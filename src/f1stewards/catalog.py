"""Frozen 2018-2025 event catalog derived from FastF1 schedules and FIA archive rules."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import quote

import pandas as pd

from f1stewards.models import PilotEvent

CATALOG_COLUMNS = [
    "pilot_id",
    "season",
    "round_number",
    "race_date",
    "event_timezone",
    "event_name",
    "country",
    "location",
    "event_slug",
    "season_slug",
    "archive_url",
    "archive_system",
    "event_format",
    "has_sprint",
    "regime",
    "is_pilot",
    "catalog_source_url",
    "selection_reason",
]


def _race_timezone_offset(row: pd.Series) -> str:
    for session_number in range(1, 6):
        if str(row.get(f"Session{session_number}", "")).casefold() != "race":
            continue
        value = pd.Timestamp(row[f"Session{session_number}Date"])
        offset = value.utcoffset()
        if offset is None:
            break
        total_minutes = int(offset.total_seconds() // 60)
        sign = "+" if total_minutes >= 0 else "-"
        hours, minutes = divmod(abs(total_minutes), 60)
        return f"{sign}{hours:02d}:{minutes:02d}"
    raise ValueError(f"No timezone-aware Race session found for {row.get('EventName')}")


def _legacy_slug(event_name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", event_name.casefold()).strip("-")


def build_study_event_catalog(
    schedules: Mapping[int, pd.DataFrame], settings: Mapping[str, object]
) -> list[PilotEvent]:
    """Build and validate the complete event catalog without performing network access."""

    seasons = [int(value) for value in settings["completed_seasons"]]
    expected_counts = {
        int(year): int(count)
        for year, count in dict(settings["expected_event_counts"]).items()
    }
    season_slugs = {int(year): value for year, value in dict(settings["season_slugs"]).items()}
    regimes = {int(year): value for year, value in dict(settings["regimes"]).items()}
    event_codes = dict(settings["event_codes"])
    overrides = dict(settings.get("archive_event_overrides", {}))
    url_overrides = dict(settings.get("archive_url_overrides", {}))
    pilot_ids = set(settings["pilot_event_ids"])
    source_url = str(settings["schedule_source_url"])
    modern_template = str(settings["modern_archive_url_template"])
    legacy_template = str(settings["legacy_event_url_template"])

    records: list[PilotEvent] = []
    for season in seasons:
        if season not in schedules:
            raise ValueError(f"Missing schedule for {season}")
        schedule = schedules[season].copy()
        schedule["RoundNumber"] = pd.to_numeric(schedule["RoundNumber"], errors="raise")
        schedule = schedule[schedule["RoundNumber"] > 0].sort_values("RoundNumber")
        if len(schedule) != expected_counts[season]:
            raise ValueError(
                f"{season} schedule has {len(schedule)} events; expected {expected_counts[season]}"
            )
        for _, row in schedule.iterrows():
            event_name = str(row["EventName"])
            if event_name not in event_codes:
                raise ValueError(f"No stable event code configured for {event_name}")
            event_id = f"{season}-{event_codes[event_name]}"
            archive_name = overrides.get(f"{season}|{event_name}", event_name)
            if season == 2018:
                archive_system = "legacy_event_timing"
                event_slug = _legacy_slug(archive_name)
                season_slug = None
                archive_url = legacy_template.format(event_slug=event_slug)
            else:
                archive_system = "document_archive"
                event_slug = quote(archive_name, safe="")
                season_slug = str(season_slugs[season])
                archive_url = modern_template.format(
                    event_slug=event_slug, season_slug=season_slug
                )
            archive_url = str(url_overrides.get(event_id, archive_url))
            sessions = {str(row.get(f"Session{number}", "")) for number in range(1, 6)}
            records.append(
                PilotEvent(
                    pilot_id=event_id,
                    season=season,
                    round_number=int(row["RoundNumber"]),
                    race_date=pd.Timestamp(row["EventDate"]).date(),
                    event_timezone=_race_timezone_offset(row),
                    event_name=event_name,
                    country=str(row.get("Country", "")) or None,
                    location=str(row.get("Location", "")) or None,
                    event_slug=event_slug,
                    season_slug=season_slug,
                    archive_url=archive_url,
                    archive_system=archive_system,
                    event_format=str(row["EventFormat"]),
                    has_sprint=any("sprint" in session.casefold() for session in sessions),
                    regime=str(regimes[season]),
                    is_pilot=event_id in pilot_ids,
                    catalog_source_url=source_url,
                    selection_reason=(
                        "Feasibility pilot event retained in the full study catalog."
                        if event_id in pilot_ids
                        else "Completed Race/Sprint event in the predefined 2018-2025 population."
                    ),
                )
            )

    ids = [record.pilot_id for record in records]
    season_rounds = [(record.season, record.round_number) for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError("Stable event-code mapping produced duplicate event ids")
    if len(season_rounds) != len(set(season_rounds)):
        raise ValueError("Catalog contains duplicate season/round pairs")
    missing_pilots = pilot_ids - set(ids)
    if missing_pilots:
        missing = ", ".join(sorted(missing_pilots))
        raise ValueError(f"Pilot ids missing from full catalog: {missing}")
    unknown_url_overrides = set(url_overrides) - set(ids)
    if unknown_url_overrides:
        unknown = ", ".join(sorted(unknown_url_overrides))
        raise ValueError(f"Archive URL overrides reference unknown event ids: {unknown}")
    return records


def write_study_event_catalog(events: list[PilotEvent], path: Path) -> str:
    """Write the deterministic CSV contract and return its SHA-256 digest."""

    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame([event.model_dump(mode="json") for event in events])
    frame = frame[CATALOG_COLUMNS].sort_values(["season", "round_number"])
    frame.to_csv(path, index=False, lineterminator="\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()
