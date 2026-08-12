"""Configuration loading with validation."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from f1stewards.models import (
    DocumentClass,
    InternationalSportingCodeIssue,
    PilotEvent,
    RegulatorySource,
    SportingRegulationIssue,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        payload = yaml.safe_load(stream)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a mapping in {path}")
    return payload


def load_pilot_events(path: Path | None = None) -> list[PilotEvent]:
    config_path = path or PROJECT_ROOT / "config" / "pilot_events.yml"
    payload = load_yaml(config_path)
    events = payload.get("pilot_events")
    if not isinstance(events, list):
        raise ValueError(f"Missing pilot_events list in {config_path}")
    return [PilotEvent.model_validate(event) for event in events]


def load_full_collection_settings(path: Path | None = None) -> dict[str, Any]:
    config_path = path or PROJECT_ROOT / "config" / "full_collection.yml"
    payload = load_yaml(config_path)
    settings = payload.get("full_collection")
    if not isinstance(settings, dict):
        raise ValueError(f"Missing full_collection mapping in {config_path}")
    seasons = settings.get("completed_seasons")
    if seasons != list(range(2018, 2026)):
        raise ValueError("Full collection must cover completed seasons 2018 through 2025")
    expected = settings.get("expected_event_counts")
    if not isinstance(expected, dict) or {int(year) for year in expected} != set(seasons):
        raise ValueError("Expected event counts must cover every study season")
    return settings


def load_study_events(path: Path | None = None) -> list[PilotEvent]:
    catalog_path = path or PROJECT_ROOT / "config" / "study_events.csv"
    if not catalog_path.exists():
        raise FileNotFoundError(
            f"Study event catalog not found at {catalog_path}; run build-study-catalog"
        )
    with catalog_path.open(encoding="utf-8-sig", newline="") as stream:
        raw_records = list(csv.DictReader(stream))
    records: list[PilotEvent] = []
    for raw in raw_records:
        record: dict[str, Any] = {
            key: (None if value == "" else value) for key, value in raw.items()
        }
        for key in ("season", "round_number"):
            if record.get(key) is not None:
                record[key] = int(record[key])
        for key in ("has_sprint", "is_pilot"):
            if record.get(key) is not None:
                record[key] = str(record[key]).casefold() == "true"
        records.append(PilotEvent.model_validate(record))
    ids = [event.pilot_id for event in records]
    rounds = [(event.season, event.round_number) for event in records]
    if len(ids) != len(set(ids)):
        raise ValueError(f"Duplicate event id in {catalog_path}")
    if len(rounds) != len(set(rounds)):
        raise ValueError(f"Duplicate season/round in {catalog_path}")
    return records


def load_document_classes(path: Path | None = None) -> dict[str, dict[str, list[str]]]:
    config_path = path or PROJECT_ROOT / "config" / "document_classes.yml"
    payload = load_yaml(config_path)
    classes = payload.get("classes")
    if not isinstance(classes, dict):
        raise ValueError(f"Missing classes mapping in {config_path}")
    return classes


def load_evidence_profiles(path: Path | None = None) -> dict[str, set[DocumentClass]]:
    config_path = path or PROJECT_ROOT / "config" / "evidence_profiles.yml"
    payload = load_yaml(config_path)
    raw_profiles = payload.get("evidence_profiles")
    if not isinstance(raw_profiles, dict) or not raw_profiles:
        raise ValueError(f"Missing evidence_profiles mapping in {config_path}")
    profiles: dict[str, set[DocumentClass]] = {}
    for name, raw_profile in raw_profiles.items():
        if not isinstance(raw_profile, dict):
            raise ValueError(f"Evidence profile {name} must be a mapping")
        raw_classes = raw_profile.get("document_classes")
        if not isinstance(raw_classes, list) or not raw_classes:
            raise ValueError(f"Evidence profile {name} requires document_classes")
        try:
            profiles[str(name)] = {DocumentClass(value) for value in raw_classes}
        except ValueError as exc:
            raise ValueError(f"Evidence profile {name} contains an unknown class") from exc
    return profiles


def load_regulatory_sources(path: Path | None = None) -> list[RegulatorySource]:
    config_path = path or PROJECT_ROOT / "config" / "regulatory_sources.yml"
    payload = load_yaml(config_path)
    sources = payload.get("regulatory_sources")
    if not isinstance(sources, list):
        raise ValueError(f"Missing regulatory_sources list in {config_path}")
    records = [RegulatorySource.model_validate(source) for source in sources]
    source_ids = [record.source_id for record in records]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError(f"Duplicate source_id in {config_path}")
    known_events = {event.pilot_id for event in load_pilot_events()}
    unknown_events = sorted(
        {event_id for record in records for event_id in record.event_ids} - known_events
    )
    if unknown_events:
        raise ValueError(f"Unknown event_ids in {config_path}: {', '.join(unknown_events)}")
    return records


def load_analysis_thresholds(path: Path | None = None) -> dict[str, Any]:
    config_path = path or PROJECT_ROOT / "config" / "analysis_thresholds.yml"
    payload = load_yaml(config_path)
    thresholds = payload.get("analysis_thresholds")
    if not isinstance(thresholds, dict):
        raise ValueError(f"Missing analysis_thresholds mapping in {config_path}")
    required = {
        "pilot_scale",
        "release",
        "consistency",
        "guideline_conformance",
        "nationality",
        "competitive_impact",
        "evidence_explorer",
    }
    missing = required - set(thresholds)
    if missing:
        raise ValueError(f"Missing threshold sections: {', '.join(sorted(missing))}")
    mappable = thresholds["guideline_conformance"].get("minimum_mappable_fraction")
    agreement = thresholds["guideline_conformance"].get("minimum_independent_agreement")
    valid_fractions = all(
        isinstance(value, float | int) and 0 <= value <= 1
        for value in [mappable, agreement]
    )
    if not valid_fractions:
        raise ValueError("Guideline threshold fractions must be between zero and one")
    return thresholds


def load_sporting_regulation_issues(
    path: Path | None = None,
) -> list[SportingRegulationIssue]:
    config_path = path or PROJECT_ROOT / "config" / "f1_sporting_regulation_issues.yml"
    payload = load_yaml(config_path)
    issues = payload.get("sporting_regulation_issues")
    if not isinstance(issues, list):
        raise ValueError(f"Missing sporting_regulation_issues list in {config_path}")
    records = [SportingRegulationIssue.model_validate(issue) for issue in issues]
    ids = [record.source_id for record in records]
    keys = [(record.season, record.precedence) for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError(f"Duplicate source_id in {config_path}")
    if len(keys) != len(set(keys)):
        raise ValueError(f"Duplicate season/precedence in {config_path}")
    covered_seasons = {record.season for record in records}
    if covered_seasons != set(range(2018, 2026)):
        raise ValueError("Sporting regulation catalog must cover every season from 2018 to 2025")
    for season in covered_seasons:
        season_issues = sorted(
            (record for record in records if record.season == season),
            key=lambda record: record.precedence,
        )
        publication_dates = [record.publication_date for record in season_issues]
        if publication_dates != sorted(publication_dates):
            raise ValueError(f"{season} issue precedence must follow publication date")
    return records


def select_sporting_regulation(
    issues: list[SportingRegulationIssue],
    season: int,
    event_date: date,
) -> SportingRegulationIssue:
    candidates = [
        issue
        for issue in issues
        if issue.season == season and issue.publication_date <= event_date
    ]
    if not candidates:
        raise ValueError(f"No {season} Sporting Regulation issue available by {event_date}")
    return max(candidates, key=lambda issue: (issue.publication_date, issue.precedence))


def load_international_sporting_code_issues(
    path: Path | None = None,
) -> list[InternationalSportingCodeIssue]:
    config_path = path or PROJECT_ROOT / "config" / "international_sporting_code_issues.yml"
    payload = load_yaml(config_path)
    issues = payload.get("international_sporting_code_issues")
    if not isinstance(issues, list):
        raise ValueError(f"Missing international_sporting_code_issues list in {config_path}")
    records = [InternationalSportingCodeIssue.model_validate(issue) for issue in issues]
    ids = [record.source_id for record in records]
    keys = [(record.season, record.precedence) for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError(f"Duplicate source_id in {config_path}")
    if len(keys) != len(set(keys)):
        raise ValueError(f"Duplicate season/precedence in {config_path}")
    if {record.season for record in records} != set(range(2018, 2026)):
        raise ValueError("International Sporting Code catalog must cover 2018 through 2025")
    return records


def select_international_sporting_code(
    issues: list[InternationalSportingCodeIssue],
    season: int,
    event_date: date,
) -> InternationalSportingCodeIssue:
    candidates = [
        issue
        for issue in issues
        if issue.season == season
        and issue.effective_from <= event_date <= issue.effective_through
    ]
    if not candidates:
        raise ValueError(f"No {season} International Sporting Code issue covers {event_date}")
    return max(candidates, key=lambda issue: (issue.effective_from, issue.precedence))
