"""Configuration loading with validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from f1stewards.models import PilotEvent

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
