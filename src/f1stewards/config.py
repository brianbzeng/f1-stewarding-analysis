"""Configuration loading with validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from f1stewards.models import PilotEvent, RegulatorySource

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


def load_document_classes(path: Path | None = None) -> dict[str, dict[str, list[str]]]:
    config_path = path or PROJECT_ROOT / "config" / "document_classes.yml"
    payload = load_yaml(config_path)
    classes = payload.get("classes")
    if not isinstance(classes, dict):
        raise ValueError(f"Missing classes mapping in {config_path}")
    return classes


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
