"""Validated records used at acquisition and parsing boundaries."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


class DocumentClass(StrEnum):
    STEWARD_DECISION = "steward_decision"
    SUMMONS = "summons"
    FINAL_CLASSIFICATION = "final_classification"
    PROVISIONAL_CLASSIFICATION = "provisional_classification"
    CHAMPIONSHIP_POINTS = "championship_points"
    RACE_DIRECTOR_NOTES = "race_director_notes"
    CIRCUIT_MAP = "circuit_map"
    OTHER = "other"


class PilotEvent(BaseModel):
    """One event selected for the feasibility pilot."""

    model_config = ConfigDict(extra="forbid")

    pilot_id: str = Field(pattern=r"^\d{4}-[a-z]{3}$")
    season: int = Field(ge=2018, le=2025)
    race_date: date
    event_timezone: str
    event_name: str
    event_slug: str
    season_slug: str
    archive_url: HttpUrl
    regime: str
    selection_reason: str


class RegulatorySource(BaseModel):
    """One event-linked governing instrument or published guideline."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]+$")
    document_type: str
    title: str
    issuing_body: str = "FIA"
    publication_date: date | None = None
    effective_from: date | None = None
    effective_through: date | None = None
    source_url: HttpUrl
    resolved_url: HttpUrl | None = None
    source_status: str
    applicability_status: str
    event_role: str
    event_ids: list[str] = Field(min_length=1)
    is_guideline: bool = False
    notes: str

    @field_validator("event_ids")
    @classmethod
    def event_ids_must_be_unique(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("event_ids must be unique")
        return value

    @model_validator(mode="after")
    def validate_effective_window(self) -> RegulatorySource:
        if (
            self.effective_from is not None
            and self.effective_through is not None
            and self.effective_through < self.effective_from
        ):
            raise ValueError("effective_through cannot precede effective_from")
        return self


class SourceDocument(BaseModel):
    """Lineage record for one document advertised by an official archive."""

    model_config = ConfigDict(extra="forbid")

    document_id: str
    pilot_id: str
    season: int
    event_name: str
    title: str
    document_url: HttpUrl
    archive_url: HttpUrl
    document_class: DocumentClass
    published_at_raw: str | None = None
    published_at: datetime | None = None
    discovered_at: datetime
    source_domain: str = "fia.com"
    retrieved_at: datetime | None = None
    content_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    local_path: Path | None = None
    http_status: int | None = None
    content_type: str | None = None
    retrieval_error: str | None = None
    is_recalled: bool = False
    supersedes_document_id: str | None = None

    @field_validator("title")
    @classmethod
    def title_must_be_nonempty(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("title cannot be empty")
        return value


class DecisionSections(BaseModel):
    """Loss-minimizing first pass over a steward decision PDF."""

    model_config = ConfigDict(extra="forbid")

    document_id: str
    page_count: int = Field(ge=1)
    raw_text: str
    driver_number: int | None = Field(default=None, ge=1, le=99)
    driver_name: str | None = None
    session_type: str | None = None
    incident_time_raw: str | None = None
    fact_text: str | None = None
    infringement_text: str | None = None
    decision_text: str | None = None
    reason_text: str | None = None
    parser_warnings: list[str] = Field(default_factory=list)
