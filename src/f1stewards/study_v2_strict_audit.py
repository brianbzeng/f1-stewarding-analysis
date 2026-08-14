"""Source-cited case records for the disclosed Study v2 strict model audit."""

from __future__ import annotations

import hashlib
import io
import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from f1stewards.config import (
    PROJECT_ROOT,
    load_international_sporting_code_issues,
    load_sporting_regulation_issues,
    load_yaml,
    select_international_sporting_code,
    select_sporting_regulation,
)
from f1stewards.first_pass import explicit_fault_language

MODEL_WORKSPACE = (
    PROJECT_ROOT
    / "data"
    / "manual"
    / "full_corpus_model_review"
    / "model-review-3dacc1268f13"
    / "full-coding-e0192ecbd9e4"
)
HUMAN_REVIEW_PACKET = (
    PROJECT_ROOT / "data" / "manual" / "study_v2_review_packets" / "study-v2-review-7cb1b29b5251"
)
DATABASE = PROJECT_ROOT / "data" / "processed" / "f1_stewarding.duckdb"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "data" / "manual" / "study_v2_strict_model_audit"
CONFIG_PATH = PROJECT_ROOT / "config" / "study_v2_strict_model_audit.yml"
CORRECTIONS_PATH = PROJECT_ROOT / "config" / "study_v2_strict_model_corrections.yml"
EXCLUSION_RESOLUTIONS_PATH = PROJECT_ROOT / "config" / "study_v2_strict_exclusion_resolutions.yml"

INCLUDED_SOURCE_FIELDS = [
    "document_id",
    "adjudication_id_final",
    "event_id",
    "season",
    "round_number",
    "event_name",
    "event_date",
    "guideline_regime",
    "title",
    "source_url",
    "published_at",
    "fact_text",
    "infringement_text",
    "decision_text",
    "reason_text",
]

REVIEWED_FIELDS = [
    "accused_driver_number_final",
    "affected_driver_numbers_final",
    "session_type_final",
    "lap_number_final",
    "location_final",
    "incident_family_final",
    "outcome_family_final",
    "penalty_seconds_final",
    "penalty_points_final",
    "grid_places_final",
    "fault_language_final",
]
REVIEW_FIELD_BY_SHORT = {field.removesuffix("_final"): field for field in REVIEWED_FIELDS}
CHECK_BY_REVIEW_FIELD = {
    "accused_driver_number": "accused_driver",
    "affected_driver_numbers": "affected_drivers",
    "incident_family": "family",
    "outcome_family": "outcome",
    "penalty_seconds": "penalty_seconds",
    "grid_places": "grid_places",
    "fault_language": "fault_language",
}

PENALTY_GUIDELINE_URL = (
    "https://www.fia.com/sites/default/files/"
    "2025_f1_guidelines_penalty_points_overview_-_14_may_clean_0.pdf"
)
DRIVING_GUIDELINE_URL = (
    "https://www.fia.com/sites/default/files/"
    "f1_driving_standards_guidelines_version_4.1_feb_20_2025.pdf"
)


@dataclass(frozen=True)
class StrictAuditBuild:
    run_id: str
    output_dir: Path
    included_decisions: int
    exclusion_sources: int
    pending_adversarial: int


def _clean(value: object) -> str:
    if pd.isna(value):
        return ""
    return " ".join(str(value).split())


def _bool(value: object) -> bool:
    return str(value).strip().casefold() == "true"


def _csv_bytes(frame: pd.DataFrame) -> bytes:
    stream = io.StringIO(newline="")
    frame.to_csv(stream, index=False, lineterminator="\n")
    return stream.getvalue().encode("utf-8")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _source_evidence(database: Path) -> pd.DataFrame:
    with duckdb.connect(str(database), read_only=True) as connection:
        return connection.execute(
            """
            SELECT
                s.document_id,
                s.content_sha256,
                t.page_count,
                t.raw_text,
                t.fact_text,
                t.infringement_text,
                t.decision_text,
                t.reason_text
            FROM raw.source_documents AS s
            LEFT JOIN raw.document_text AS t USING (document_id)
            """
        ).fetchdf()


def _driver_aliases(database: Path) -> dict[tuple[str, str], set[str]]:
    with duckdb.connect(str(database), read_only=True) as connection:
        identities = connection.execute(
            """
            SELECT DISTINCT
                event_id,
                CAST(driver_number AS VARCHAR) AS driver_number,
                observed_driver_name,
                abbreviation
            FROM analysis.v_fastf1_driver_identity
            WHERE event_id IS NOT NULL AND driver_number IS NOT NULL
            """
        ).fetchdf()
    aliases: dict[tuple[str, str], set[str]] = {}
    for row in identities.itertuples(index=False):
        key = (str(row.event_id), str(row.driver_number))
        values = aliases.setdefault(key, set())
        full_name = _clean(row.observed_driver_name)
        abbreviation = _clean(row.abbreviation)
        if full_name:
            values.add(full_name)
            values.add(full_name.split()[-1])
        if abbreviation:
            values.add(abbreviation)
    return aliases


def _load_corrections(path: Path = CORRECTIONS_PATH) -> dict[str, dict[str, Any]]:
    payload = load_yaml(path)["strict_model_corrections"]
    corrections: dict[str, dict[str, Any]] = {}
    for record in payload["records"]:
        document_id = str(record["document_id"])
        if document_id in corrections:
            raise ValueError(f"Duplicate strict model correction: {document_id}")
        unknown = set(record["changes"]) - set(REVIEW_FIELD_BY_SHORT)
        if unknown:
            raise ValueError(f"Unknown correction fields for {document_id}: {sorted(unknown)}")
        unknown_checks = set(record.get("resolved_checks", [])) - set(
            CHECK_BY_REVIEW_FIELD.values()
        )
        if unknown_checks:
            raise ValueError(f"Unknown resolved checks for {document_id}: {sorted(unknown_checks)}")
        if (
            not str(record.get("evidence", "")).strip()
            or not str(record.get("rationale", "")).strip()
        ):
            raise ValueError(f"Correction lacks evidence or rationale: {document_id}")
        corrections[document_id] = record
    return corrections


def _load_exclusion_resolutions(
    path: Path = EXCLUSION_RESOLUTIONS_PATH,
) -> dict[str, dict[str, Any]]:
    payload = load_yaml(path)["strict_model_exclusion_resolutions"]
    resolutions: dict[str, dict[str, Any]] = {}
    for record in payload["records"]:
        document_id = str(record["document_id"])
        if document_id in resolutions:
            raise ValueError(f"Duplicate exclusion resolution: {document_id}")
        if not str(record.get("supporting_source_url", "")).startswith("https://"):
            raise ValueError(f"Exclusion resolution lacks an exact source URL: {document_id}")
        if (
            not str(record.get("evidence", "")).strip()
            or not str(record.get("rationale", "")).strip()
        ):
            raise ValueError(f"Exclusion resolution lacks evidence or rationale: {document_id}")
        resolutions[document_id] = record
    return resolutions


def _evidence_span(row: pd.Series) -> str:
    parts: list[str] = []
    for label, field, limit in (
        ("Fact", "fact_text", 220),
        ("Decision", "decision_text", 220),
        ("Reason", "reason_text", 360),
    ):
        value = _clean(row.get(field, ""))
        if value:
            parts.append(f"{label}: {value[:limit]}")
    return " | ".join(parts)


def _rule_reference(row: pd.Series) -> str:
    source = " ".join(_clean(row.get(field, "")) for field in ("infringement_text", "reason_text"))
    patterns = re.findall(
        r"(?:Article|Art\.?|Appendix)\s+[A-Z0-9][A-Za-z0-9.() /-]{0,45}",
        source,
        flags=re.IGNORECASE,
    )
    unique: list[str] = []
    for item in patterns:
        cleaned = item.strip(" .,:;-\n")
        if cleaned and cleaned not in unique:
            unique.append(cleaned)
    return " | ".join(unique[:4])


def _contains_car(source: str, number: str) -> bool:
    if not number:
        return True
    return bool(
        re.search(
            rf"\b(?:car|driver|no\.?|number)?\s*{re.escape(number)}\b",
            source,
            flags=re.IGNORECASE,
        )
    )


def _contains_driver(
    source: str,
    number: str,
    event_id: str,
    aliases: dict[tuple[str, str], set[str]],
) -> bool:
    if _contains_car(source, number):
        return True
    return any(
        re.search(rf"\b{re.escape(alias)}\b", source, flags=re.IGNORECASE)
        for alias in aliases.get((event_id, number), set())
    )


def _outcome_matches(row: pd.Series) -> bool:
    decision = _clean(row["decision_text"]).casefold()
    outcome = _clean(row["outcome_family_final"])
    patterns = {
        "time_penalty": r"(?:time penalty|\b\d+\s*(?:second|sec|s)\b)",
        "grid_penalty": r"grid (?:place|position)|drop of \d+ grid",
        "drive_through": r"drive[- ]through",
        "stop_go": r"stop[- ]and[- ]go|stop and go",
        "reprimand": r"reprimand",
        "warning": r"warning",
        "no_further_action": r"no further action|no penalty|racing incident",
    }
    pattern = patterns.get(outcome)
    return bool(pattern and re.search(pattern, decision, flags=re.IGNORECASE))


def _seconds_match(row: pd.Series) -> bool:
    seconds = _clean(row["penalty_seconds_final"])
    if not seconds:
        return True
    decision = _clean(row["decision_text"])
    number = str(int(float(seconds)))
    words = {"5": "five", "10": "ten", "20": "twenty", "30": "thirty"}
    return bool(
        re.search(rf"\b{number}\s*(?:seconds?|secs?|s)\b", decision, flags=re.IGNORECASE)
        or (number in words and re.search(rf"\b{words[number]}\b", decision, flags=re.IGNORECASE))
    )


def _grid_match(row: pd.Series) -> bool:
    places = _clean(row["grid_places_final"])
    if not places:
        return True
    decision = _clean(row["decision_text"])
    number = str(int(float(places)))
    words = {"3": "three", "5": "five", "10": "ten"}
    numeric_patterns = (
        rf"\b{number}\s*(?:grid\s*)?(?:place|position)s?\b",
        rf"\b(?:drop|penalty)\b.{0, 40}\b{number}\b.{0, 40}\bgrid\b",
        rf"\bgrid\b.{0, 40}\b{number}\b.{0, 40}\b(?:place|position|drop|penalty)s?\b",
    )
    word = words.get(number)
    word_patterns = (
        (
            rf"\b{word}\s*(?:grid\s*)?(?:place|position)s?\b",
            rf"\b(?:drop|penalty)\b.{0, 40}\b{word}\b.{0, 40}\bgrid\b",
        )
        if word
        else ()
    )
    return bool(
        any(re.search(pattern, decision, flags=re.IGNORECASE) for pattern in numeric_patterns)
        or any(re.search(pattern, decision, flags=re.IGNORECASE) for pattern in word_patterns)
    )


def _family_matches(row: pd.Series) -> bool:
    source = " ".join(
        _clean(row[field]).casefold() for field in ("fact_text", "infringement_text", "reason_text")
    )
    patterns = {
        "causing_collision": (
            r"collid|collision|contact|incident (?:between|with)|hit (?:the back of )?car"
        ),
        "qualifying_impeding": (
            r"imped|affected by|preventing other cars|following car(?:s|\(s\))?.{0,60}"
            r"not able to overtake"
        ),
        "gaining_advantage_off_track": r"lasting advantage|left the track|off the track",
        "forcing_off_track": (
            r"forc(?:e|ed|ing).*(?:off|track)|crowd|driv(?:e|en|ing) car.{0,30}off the road|"
            r"forced onto the kerb"
        ),
        "unsafe_rejoin": r"rejoin|re-join|returned to the track",
        "multiple_defensive_moves": r"more than one change|multiple.*move|change.*direction",
        "moving_under_braking": r"braking zone|under braking|deceleration phase",
    }
    return bool(re.search(patterns.get(_clean(row["incident_family_final"]), r"$^"), source))


def _fault_matches(row: pd.Series) -> bool:
    fault = _clean(row["fault_language_final"])
    secondary = _bool(row.get("include_secondary_final", False))
    non_fault_families = {
        "gaining_advantage_off_track",
        "moving_under_braking",
        "multiple_defensive_moves",
        "qualifying_impeding",
    }
    if secondary or _clean(row.get("incident_family_final", "")) in non_fault_families:
        return fault == "not_applicable"
    source_fault = explicit_fault_language(row.get("reason_text", ""), secondary=secondary)
    if source_fault:
        return fault == source_fault
    return fault == ("not_applicable" if secondary else "no_conclusion")


def _public_evidence_assessment(row: pd.Series) -> str:
    reason = _clean(row["reason_text"])
    source = reason.casefold()
    if len(reason) < 80:
        return "limited_public_reasoning"
    if re.search(r"video|cctv|onboard|on-board|telemetry|gps", source):
        return "fia_reasoning_documented_visual_or_telemetry_basis_not_independently_verified"
    return "fia_reasoning_documented"


def _penalty_guideline_assessment(row: pd.Series) -> str:
    event_date = date.fromisoformat(str(row["event_date"])[:10])
    if event_date < date(2025, 5, 14):
        return "no_public_contemporaneous_penalty_guideline"
    outcome = _clean(row["outcome_family_final"])
    family = _clean(row["incident_family_final"])
    if outcome == "no_further_action":
        return "not_applicable_no_breach_finding"
    seconds = _clean(row["penalty_seconds_final"])
    seconds_value = int(float(seconds)) if seconds else None
    grid = _clean(row["grid_places_final"])
    grid_value = int(float(grid)) if grid else None

    if family in {"causing_collision", "forcing_off_track", "gaining_advantage_off_track"}:
        if outcome == "time_penalty" and seconds_value == 10:
            return "within_contemporaneous_public_guideline"
        if outcome == "time_penalty" and seconds_value == 5:
            return "within_guideline_with_documented_or_possible_mitigation"
        if outcome in {"drive_through", "stop_go"}:
            return "substitution_or_escalation_requires_context"
        if outcome == "grid_penalty":
            return "substitution_or_escalation_requires_context"
        if family == "causing_collision" and outcome == "reprimand":
            return "within_no_immediate_consequence_range_requires_context"
        return "potential_public_guideline_tension"
    if family == "unsafe_rejoin":
        if outcome == "time_penalty" and seconds_value in {5, 10}:
            return "within_contemporaneous_public_guideline"
        if outcome in {"drive_through", "grid_penalty"}:
            return "substitution_or_escalation_requires_context"
        return "potential_public_guideline_tension"
    if family == "qualifying_impeding":
        if outcome == "grid_penalty" and grid_value in {3, 5}:
            return "within_contemporaneous_public_guideline"
        return "potential_public_guideline_tension"
    if family == "multiple_defensive_moves":
        if outcome == "time_penalty" and seconds_value is not None and seconds_value >= 5:
            return "within_contemporaneous_public_guideline"
        if outcome == "drive_through":
            return "within_contemporaneous_public_guideline"
        return "potential_public_guideline_tension"
    if family == "moving_under_braking":
        if outcome in {"warning", "reprimand", "drive_through"}:
            return "within_contemporaneous_public_guideline"
        if outcome == "time_penalty" and seconds_value is not None and seconds_value >= 5:
            return "within_contemporaneous_public_guideline"
        return "potential_public_guideline_tension"
    return "public_guideline_family_mapping_unavailable"


def _source_derived_exclusion_basis(row: pd.Series) -> str:
    """Classify exclusion from official source fields without using the final exclusion label."""

    raw_text = _clean(row.get("raw_text", ""))
    if not raw_text:
        return "source_unavailable"
    if _clean(row.get("content_document_class", "")) != "steward_decision":
        return "nondecision_source_body"

    session = _clean(row.get("session_type_raw", "")) or _clean(
        row.get("session_type_suggestion", "")
    )
    session_key = session.casefold()
    if re.search(r"\b(?:practice|p1|p2|p3|test)\b", session_key):
        return "out_of_scope_session"

    structured_source = " ".join(
        _clean(row.get(field, "")) for field in ("fact_text", "infringement_text")
    )
    if not structured_source:
        structured_source = _clean(row.get("title", ""))
    source = structured_source.casefold()
    impeding = bool(re.search(r"\bimped", source))
    if "qual" in session_key:
        return "in_scope_secondary_candidate" if impeding else "outside_secondary_offence_scope"

    if "unsafe release" in source or "pit lane release" in source:
        primary_candidate = False
    else:
        collision = bool(
            re.search(r"\bcollid|\bcollision|\bcontact(?:ed)?\b", source)
            and not re.search(r"\bnear collision\b", source)
        )
        forcing = bool(re.search(r"\bforc(?:e|ed|ing).{0,80}(?:off|track|road)", source))
        advantage = bool(re.search(r"lasting advantage|gain(?:ed|ing)? an advantage", source))
        unsafe_rejoin = bool(
            re.search(
                r"re-?join(?:ed|ing)?.{0,60}unsafe|unsafe(?:ly)? re-?join",
                source,
            )
        )
        defensive = bool(
            re.search(
                r"more than one change|multiple defensive|moving under braking|braking zone",
                source,
            )
        )
        primary_candidate = collision or forcing or advantage or unsafe_rejoin or defensive

    if "race" in session_key or "sprint" in session_key:
        return "in_scope_primary_candidate" if primary_candidate else "outside_offence_scope"
    if primary_candidate or impeding:
        return "scope_unresolved_missing_session"
    return "outside_offence_scope"


def _successor_document_id(row: pd.Series) -> str:
    linked = _clean(row.get("successor_document_id", ""))
    if linked:
        return linked
    notes = _clean(row.get("review_notes", ""))
    match = re.search(r"Superseded by (fia-[a-z0-9-]+)", notes, flags=re.IGNORECASE)
    return match.group(1) if match else ""


def _rule_sources(
    row: pd.Series, sporting_issues: list[Any], code_issues: list[Any]
) -> dict[str, str]:
    event_date = date.fromisoformat(str(row["event_date"])[:10])
    season = int(row["season"])
    sporting = select_sporting_regulation(sporting_issues, season, event_date)
    code = select_international_sporting_code(code_issues, season, event_date)
    return {
        "sporting_source_id": sporting.source_id,
        "sporting_source_title": sporting.title,
        "sporting_source_url": str(sporting.document_url or sporting.archive_url),
        "sporting_source_status": sporting.selection_status,
        "isc_source_id": code.source_id,
        "isc_source_title": code.title,
        "isc_source_url": str(code.document_url or code.archive_url),
        "isc_source_status": code.selection_status,
        "driving_guideline_url": DRIVING_GUIDELINE_URL if event_date >= date(2025, 2, 20) else "",
        "penalty_guideline_url": PENALTY_GUIDELINE_URL if event_date >= date(2025, 5, 14) else "",
    }


def _included_record(
    row: pd.Series,
    sporting_issues: list[Any],
    code_issues: list[Any],
    driver_aliases: dict[tuple[str, str], set[str]],
    correction: dict[str, Any] | None = None,
) -> dict[str, Any]:
    reviewed = row.copy()
    correction = correction or {}
    changes = correction.get("changes", {})
    resolved_checks = set(correction.get("resolved_checks", []))
    parent_values: dict[str, str] = {}
    for short_field, reviewed_value in changes.items():
        final_field = REVIEW_FIELD_BY_SHORT[short_field]
        parent_values[short_field] = _clean(row[final_field])
        reviewed[final_field] = str(reviewed_value)
    source = " ".join(
        _clean(reviewed[field]) for field in ("title", "fact_text", "decision_text", "reason_text")
    )
    affected = [
        value for value in _clean(reviewed["affected_driver_numbers_final"]).split("|") if value
    ]
    checks = {
        "source_url": _clean(reviewed["source_url"]).startswith("https://"),
        "evidence_span": bool(_evidence_span(reviewed)),
        "accused_driver": _contains_driver(
            source,
            _clean(reviewed["accused_driver_number_final"]),
            _clean(reviewed["event_id"]),
            driver_aliases,
        ),
        "affected_drivers": all(
            _contains_driver(
                source,
                number,
                _clean(reviewed["event_id"]),
                driver_aliases,
            )
            for number in affected
        ),
        "family": _family_matches(reviewed),
        "outcome": _outcome_matches(reviewed),
        "penalty_seconds": _seconds_match(reviewed),
        "grid_places": _grid_match(reviewed),
        "fault_language": _fault_matches(reviewed),
    }
    correction_evidence = _clean(correction.get("evidence", ""))
    if correction:
        full_source = _clean(
            " ".join(
                _clean(reviewed.get(field, ""))
                for field in (
                    "title",
                    "fact_text",
                    "infringement_text",
                    "decision_text",
                    "reason_text",
                )
            )
        )
        if correction_evidence.casefold() not in full_source.casefold():
            raise ValueError(
                f"Correction evidence is not present in cited source text: {row['document_id']}"
            )
        resolved_checks.update(
            CHECK_BY_REVIEW_FIELD[field] for field in changes if field in CHECK_BY_REVIEW_FIELD
        )
        for check in resolved_checks:
            checks[check] = True
    exceptions = [name for name, passed in checks.items() if not passed]
    assessment = _public_evidence_assessment(reviewed)
    sanction_assessment = _penalty_guideline_assessment(reviewed)
    risk_flags = [
        flag
        for flag, active in (
            ("parser_review", _bool(row["parser_review_required"])),
            ("family_conflict", _bool(row["family_conflict_suggestion"])),
            ("multi_party", _bool(row["multi_party_suggestion"])),
            ("limited_reasoning", assessment == "limited_public_reasoning"),
            (
                "guideline_tension",
                sanction_assessment == "potential_public_guideline_tension",
            ),
            ("source_check_exception", bool(exceptions)),
        )
        if active
    ]
    unresolved_flags = [
        flag
        for flag in risk_flags
        if flag in {"limited_reasoning", "guideline_tension", "source_check_exception"}
    ]
    scope = "primary" if _bool(reviewed["include_primary_final"]) else "secondary"
    correction_fields = "|".join(sorted(changes))
    correction_note = ""
    if changes:
        correction_note = (
            f" Model correction ({correction_fields}): {correction['rationale']} "
            f"Evidence: {correction['evidence']}"
        )
    record: dict[str, Any] = {
        "audit_record_id": f"strict-model-{reviewed['adjudication_id_final']}",
        "review_scope": scope,
        **{field: _clean(reviewed.get(field, "")) for field in INCLUDED_SOURCE_FIELDS},
        "fia_decision_citation_url": _clean(reviewed["source_url"]),
        "fia_decision_evidence_span": _evidence_span(reviewed),
        "version_successor_document_id": "",
        "version_successor_citation_url": "",
        "supporting_context_source_title": "",
        "supporting_context_citation_url": "",
        "supporting_context_evidence": "",
        "supporting_context_rationale": "",
        "parent_exclusion_reason": "",
        "source_derived_exclusion_basis": "not_applicable_included_decision",
        "exclusion_source_review_status": "not_applicable",
        "written_rule_reference": _rule_reference(reviewed),
        **_rule_sources(reviewed, sporting_issues, code_issues),
        **{
            f"reviewed_{field.removesuffix('_final')}": _clean(reviewed[field])
            for field in REVIEWED_FIELDS
        },
        "model_correction_fields": correction_fields,
        "model_correction_parent_values": json.dumps(parent_values, sort_keys=True)
        if parent_values
        else "",
        "model_correction_evidence": str(correction.get("evidence", "")),
        "model_correction_rationale": str(correction.get("rationale", "")),
        "model_resolution_checks": "|".join(sorted(resolved_checks)),
        "public_evidence_assessment": assessment,
        "penalty_guideline_assessment": sanction_assessment,
        "visual_review_status": "targeted_review_required"
        if risk_flags
        else "not_required_for_source_coding",
        "source_check_exceptions": "|".join(exceptions),
        "adversarial_risk_flags": "|".join(risk_flags),
        "adversarial_review_reasons": "|".join(unresolved_flags),
        "multi_party_review_status": (
            "source_participants_checked"
            if _bool(reviewed["multi_party_suggestion"])
            else "not_applicable"
        ),
        "family_conflict_review_status": (
            "source_priority_confirmed"
            if _bool(reviewed["family_conflict_suggestion"]) and checks["family"]
            else (
                "unresolved" if _bool(reviewed["family_conflict_suggestion"]) else "not_applicable"
            )
        ),
        "parser_review_status": (
            "source_text_checked"
            if _bool(reviewed["parser_review_required"]) and not exceptions
            else ("unresolved" if _bool(reviewed["parser_review_required"]) else "not_applicable")
        ),
        "strict_model_review_status": (
            "pending_adversarial_review"
            if unresolved_flags
            else (
                "model_corrected_from_cited_source"
                if changes
                else "model_confirmed_from_cited_source"
            )
        ),
        "review_confidence": "medium" if risk_flags else "high",
        "reviewer_model": "gpt-5.6-sol",
        "review_disclosure": "model_led_source_review_not_independent_human_annotation",
        "parent_review_status": _clean(reviewed["review_status"]),
        "review_notes": (
            "FIA finding and sanction were checked against the cited decision. Public-evidence "
            "assessment remains separate from fault and consequence." + correction_note
        ),
    }
    return record


def _exclusion_record(
    row: pd.Series,
    sporting_issues: list[Any],
    code_issues: list[Any],
    documents_by_id: dict[str, pd.Series],
    resolution: dict[str, Any] | None = None,
) -> dict[str, Any]:
    evidence = _clean(row.get("raw_text", ""))
    evidence_span = evidence[:600] or f"Archive title: {_clean(row['title'])}"
    source_url = _clean(row["source_url"])
    parent_reason = _clean(row.get("exclusion_reason_final", ""))
    resolution = resolution or {}
    successor_id = _clean(resolution.get("successor_document_id", "")) or _successor_document_id(
        row
    )
    successor = documents_by_id.get(successor_id)
    successor_url = _clean(successor.get("source_url", "")) if successor is not None else ""
    if parent_reason.startswith("superseded_") and successor_url.startswith("https://"):
        derived_basis = "version_predecessor_pair_review"
        exclusion_review_status = "version_pair_confirmed"
    else:
        derived_basis = _source_derived_exclusion_basis(row)
        exclusion_review_status = (
            "source_unavailable"
            if derived_basis == "source_unavailable"
            else (
                "source_scope_conflict"
                if derived_basis.startswith("in_scope_")
                or derived_basis == "scope_unresolved_missing_session"
                else "source_confirmed_exclusion"
            )
        )
    supporting_url = _clean(resolution.get("supporting_source_url", ""))
    if exclusion_review_status == "source_scope_conflict" and resolution:
        derived_basis = _clean(resolution["reviewed_basis"])
        exclusion_review_status = "source_confirmed_exclusion_with_supporting_source"
    citation_missing = not source_url.startswith("https://") or not evidence_span
    scope_conflict = exclusion_review_status == "source_scope_conflict"
    unresolved = citation_missing or scope_conflict
    public_evidence_unavailable = exclusion_review_status == "source_unavailable"
    adversarial_reason = (
        "missing_citation_or_evidence"
        if citation_missing
        else ("source_scope_conflict" if scope_conflict else "")
    )
    return {
        "audit_record_id": f"strict-model-exclusion-{row['document_id']}",
        "review_scope": "exclusion_qa",
        "document_id": _clean(row["document_id"]),
        "adjudication_id_final": "",
        "event_id": _clean(row["event_id"]),
        "season": _clean(row["season"]),
        "round_number": _clean(row["round_number"]),
        "event_name": _clean(row["event_name"]),
        "event_date": _clean(row["event_date"]),
        "guideline_regime": _clean(row.get("guideline_regime", "")),
        "title": _clean(row["title"]),
        "source_url": source_url,
        "published_at": _clean(row["published_at"]),
        "fact_text": _clean(row.get("fact_text", "")),
        "infringement_text": _clean(row.get("infringement_text", "")),
        "decision_text": _clean(row.get("decision_text", "")),
        "reason_text": _clean(row.get("reason_text", "")),
        "fia_decision_citation_url": source_url,
        "fia_decision_evidence_span": evidence_span,
        "version_successor_document_id": successor_id,
        "version_successor_citation_url": successor_url,
        "supporting_context_source_title": _clean(resolution.get("supporting_source_title", "")),
        "supporting_context_citation_url": supporting_url,
        "supporting_context_evidence": _clean(resolution.get("evidence", "")),
        "supporting_context_rationale": _clean(resolution.get("rationale", "")),
        "parent_exclusion_reason": parent_reason,
        "source_derived_exclusion_basis": derived_basis,
        "exclusion_source_review_status": exclusion_review_status,
        "written_rule_reference": _rule_reference(row),
        **_rule_sources(row, sporting_issues, code_issues),
        **{f"reviewed_{field.removesuffix('_final')}": "" for field in REVIEWED_FIELDS},
        "model_correction_fields": "",
        "model_correction_parent_values": "",
        "model_correction_evidence": "",
        "model_correction_rationale": "",
        "model_resolution_checks": "",
        "public_evidence_assessment": (
            "source_unavailable_archive_metadata_only"
            if public_evidence_unavailable
            else "not_applicable_scope_and_version_review"
        ),
        "penalty_guideline_assessment": "not_applicable_exclusion_qa",
        "visual_review_status": "not_required_for_scope_review",
        "source_check_exceptions": adversarial_reason,
        "adversarial_risk_flags": (
            adversarial_reason or ("source_unavailable" if public_evidence_unavailable else "")
        ),
        "adversarial_review_reasons": adversarial_reason,
        "multi_party_review_status": "not_applicable",
        "family_conflict_review_status": "not_applicable",
        "parser_review_status": "not_applicable",
        "strict_model_review_status": (
            "pending_adversarial_review"
            if unresolved
            else (
                "model_unresolved_public_evidence"
                if public_evidence_unavailable
                else "model_confirmed_from_cited_source"
            )
        ),
        "review_confidence": (
            "low"
            if unresolved or public_evidence_unavailable
            else ("medium" if exclusion_review_status == "version_pair_confirmed" else "high")
        ),
        "reviewer_model": "gpt-5.6-sol",
        "review_disclosure": "model_led_source_review_not_independent_human_annotation",
        "parent_review_status": _clean(row.get("review_status", "")),
        "review_notes": (
            "The exclusion was independently reclassified from official source body, session, "
            "offence wording, or a cited version-successor pair before comparison with the parent "
            "disposition. No conduct or sanction inference is made for exclusion-QA records."
            + (
                f" Supporting-source resolution: {resolution['rationale']} "
                f"Evidence: {resolution['evidence']}"
                if resolution
                else ""
            )
        ),
    }


def build_strict_model_audit(
    *,
    workspace: Path = MODEL_WORKSPACE,
    review_packet: Path = HUMAN_REVIEW_PACKET,
    database: Path = DATABASE,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
) -> StrictAuditBuild:
    """Build the source-cited audit and fail if the frozen population changes."""

    settings = load_yaml(CONFIG_PATH)["strict_model_audit"]
    adjudications = pd.read_csv(
        workspace / "adjudication_coding_worklist.csv", keep_default_na=False, low_memory=False
    )
    documents = pd.read_csv(
        workspace / "document_review_worklist.csv", keep_default_na=False, low_memory=False
    )
    included = adjudications.loc[
        adjudications["include_primary_final"].map(_bool)
        | adjudications["include_secondary_final"].map(_bool)
    ].copy()
    reviewer_a = pd.read_csv(
        review_packet / "reviewer_a_source_reviews.csv", keep_default_na=False, low_memory=False
    )
    reviewer_b = pd.read_csv(
        review_packet / "reviewer_b_source_reviews.csv", keep_default_na=False, low_memory=False
    )
    review_union_ids = set(reviewer_a["document_id"]) | set(reviewer_b["document_id"])
    included_ids = set(included["document_id"])
    exclusion_ids = sorted(review_union_ids - included_ids)
    evidence = _source_evidence(database)
    exclusions = documents.loc[documents["document_id"].isin(exclusion_ids)].merge(
        evidence, on="document_id", how="left", validate="one_to_one"
    )
    expected = settings["population"]
    primary_count = int(included["include_primary_final"].map(_bool).sum())
    secondary_count = int(included["include_secondary_final"].map(_bool).sum())
    if (
        primary_count != expected["expected_primary_decisions"]
        or secondary_count != expected["expected_secondary_decisions"]
        or len(exclusions) != expected["expected_exclusion_sources"]
        or len(included) + len(exclusions) != expected["expected_unique_sources"]
    ):
        raise ValueError("Strict model-audit population does not match the frozen contract")

    sporting_issues = load_sporting_regulation_issues()
    code_issues = load_international_sporting_code_issues()
    driver_aliases = _driver_aliases(database)
    corrections = _load_corrections()
    exclusion_resolutions = _load_exclusion_resolutions()
    unknown_corrections = set(corrections) - set(included["document_id"])
    if unknown_corrections:
        raise ValueError(
            f"Correction ledger contains documents outside the included population: "
            f"{sorted(unknown_corrections)}"
        )
    unknown_resolutions = set(exclusion_resolutions) - set(exclusions["document_id"])
    if unknown_resolutions:
        raise ValueError(
            "Exclusion resolution ledger contains documents outside the audit sample: "
            f"{sorted(unknown_resolutions)}"
        )
    records = [
        _included_record(
            row,
            sporting_issues,
            code_issues,
            driver_aliases,
            corrections.get(str(row["document_id"])),
        )
        for _, row in included.iterrows()
    ]
    documents_by_id = {str(row["document_id"]): row for _, row in documents.iterrows()}
    records.extend(
        _exclusion_record(row, sporting_issues, code_issues, documents_by_id)
        if str(row["document_id"]) not in exclusion_resolutions
        else _exclusion_record(
            row,
            sporting_issues,
            code_issues,
            documents_by_id,
            exclusion_resolutions[str(row["document_id"])],
        )
        for _, row in exclusions.iterrows()
    )
    audit = pd.DataFrame(records).sort_values(["review_scope", "season", "event_id", "document_id"])
    reviewed_included = audit.loc[audit["review_scope"].isin({"primary", "secondary"})].copy()
    reviewed_by_id = reviewed_included.set_index("adjudication_id_final")
    analysis_input = adjudications.set_index("adjudication_id_final", drop=False).copy()
    shared_ids = analysis_input.index.intersection(reviewed_by_id.index)
    for final_field in REVIEWED_FIELDS:
        reviewed_field = f"reviewed_{final_field.removesuffix('_final')}"
        analysis_input.loc[shared_ids, final_field] = reviewed_by_id.loc[
            shared_ids, reviewed_field
        ].to_numpy()
    analysis_input["strict_model_audit_status"] = ""
    analysis_input["strict_model_audit_run_id"] = ""
    analysis_input.loc[shared_ids, "strict_model_audit_status"] = reviewed_by_id.loc[
        shared_ids, "strict_model_review_status"
    ].to_numpy()
    analysis_input = analysis_input.reset_index(drop=True)

    source_packet_columns = [
        column
        for column in audit.columns
        if not column.startswith("reviewed_")
        and column
        not in {
            "parent_review_status",
            "strict_model_review_status",
            "review_confidence",
            "review_notes",
        }
    ]
    source_packet = audit[source_packet_columns].copy()
    payload_hash = _sha256(_csv_bytes(audit))
    run_id = f"strict-model-audit-{payload_hash[:12]}"
    output_dir = output_root / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    analysis_input.loc[
        analysis_input["adjudication_id_final"].isin(shared_ids), "strict_model_audit_run_id"
    ] = run_id
    audit.to_csv(output_dir / "strict_model_case_audit.csv", index=False, lineterminator="\n")
    analysis_input.to_csv(
        output_dir / "adjudication_coding_worklist.csv", index=False, lineterminator="\n"
    )
    source_packet.to_csv(output_dir / "source_only_packet.csv", index=False, lineterminator="\n")
    exceptions = audit.loc[audit["adversarial_review_reasons"].ne("")].copy()
    exceptions.to_csv(output_dir / "adversarial_review_queue.csv", index=False, lineterminator="\n")
    summary = (
        audit.groupby(["review_scope", "strict_model_review_status"], dropna=False, sort=True)
        .size()
        .rename("records")
        .reset_index()
    )
    summary.to_csv(output_dir / "audit_summary.csv", index=False, lineterminator="\n")
    manifest = {
        "schema_version": settings["schema_version"],
        "run_id": run_id,
        "frozen_at": str(settings["frozen_at"]),
        "reviewer_model": settings["reviewer_model"],
        "disclosure": settings["disclosure"],
        "parent_model_review_run": settings["parent_model_review_run"],
        "parent_human_review_packet": settings["parent_human_review_packet"],
        "primary_decisions": primary_count,
        "secondary_decisions": secondary_count,
        "included_decisions": len(included),
        "exclusion_sources": len(exclusions),
        "unique_sources": len(audit),
        "records_with_fia_citation": int(audit["fia_decision_citation_url"].ne("").sum()),
        "included_with_evidence_span": int(
            audit.loc[
                audit["review_scope"].isin({"primary", "secondary"}), "fia_decision_evidence_span"
            ]
            .ne("")
            .sum()
        ),
        "pending_adversarial": len(exceptions),
        "model_status_counts": {
            str(key): int(value)
            for key, value in audit["strict_model_review_status"].value_counts().items()
        },
        "corrected_included_rows": int(audit["model_correction_fields"].ne("").sum()),
        "corrected_field_counts": {
            field: int(
                audit["model_correction_fields"]
                .str.split("|")
                .map(lambda values, correction_field=field: correction_field in values)
                .sum()
            )
            for field in ("affected_driver_numbers", "fault_language")
        },
        "exclusion_source_review_counts": {
            str(key): int(value)
            for key, value in audit.loc[
                audit["review_scope"].eq("exclusion_qa"), "exclusion_source_review_status"
            ]
            .value_counts()
            .items()
        },
        "rule_comparison_citations": int(
            (
                audit["review_scope"].isin({"primary", "secondary"})
                & ~audit["penalty_guideline_assessment"].isin(
                    {
                        "no_public_contemporaneous_penalty_guideline",
                        "not_applicable_no_breach_finding",
                        "not_applicable_exclusion_qa",
                    }
                )
                & audit["penalty_guideline_url"].ne("")
            ).sum()
        ),
        "version_successor_citations": int(audit["version_successor_citation_url"].ne("").sum()),
        "supporting_context_citations": int(audit["supporting_context_citation_url"].ne("").sum()),
        "analysis_adapter_scope": "418 included decisions only; excluded rows retain parent fields",
        "analysis_adapter_included_rows": int(
            analysis_input["strict_model_audit_run_id"].eq(run_id).sum()
        ),
        "terminal_model_reviews": int(
            audit["strict_model_review_status"].str.startswith("model_").sum()
        ),
        "human_review_ledgers_modified": False,
        "outputs": {
            "strict_model_case_audit.csv": _sha256(_csv_bytes(audit)),
            "adjudication_coding_worklist.csv": _sha256(_csv_bytes(analysis_input)),
            "source_only_packet.csv": _sha256(_csv_bytes(source_packet)),
            "adversarial_review_queue.csv": _sha256(_csv_bytes(exceptions)),
            "audit_summary.csv": _sha256(_csv_bytes(summary)),
        },
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    validate_strict_model_audit(output_dir, allow_pending=True)
    return StrictAuditBuild(
        run_id=run_id,
        output_dir=output_dir,
        included_decisions=len(included),
        exclusion_sources=len(exclusions),
        pending_adversarial=len(exceptions),
    )


def validate_strict_model_audit(output_dir: Path, *, allow_pending: bool = False) -> pd.DataFrame:
    """Validate population, citations, hashes, disclosure, and terminal statuses."""

    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    audit = pd.read_csv(
        output_dir / "strict_model_case_audit.csv", keep_default_na=False, low_memory=False
    )
    analysis_input = pd.read_csv(
        output_dir / "adjudication_coding_worklist.csv",
        keep_default_na=False,
        low_memory=False,
    )
    included = audit["review_scope"].isin({"primary", "secondary"})
    exclusions = audit["review_scope"].eq("exclusion_qa")
    rule_comparison = ~audit["penalty_guideline_assessment"].isin(
        {
            "no_public_contemporaneous_penalty_guideline",
            "not_applicable_no_breach_finding",
            "not_applicable_exclusion_qa",
        }
    )
    terminal = audit["strict_model_review_status"].isin(
        {
            "model_confirmed_from_cited_source",
            "model_corrected_from_cited_source",
            "model_unresolved_public_evidence",
        }
    )
    corrected = audit["strict_model_review_status"].eq("model_corrected_from_cited_source")
    version_pairs = audit["exclusion_source_review_status"].eq("version_pair_confirmed")
    supporting_resolutions = audit["exclusion_source_review_status"].eq(
        "source_confirmed_exclusion_with_supporting_source"
    )
    controls = [
        ("row_identity", len(audit) == 920 and audit["audit_record_id"].is_unique),
        (
            "scope_counts",
            audit["review_scope"].value_counts().to_dict()
            == {"exclusion_qa": 502, "primary": 346, "secondary": 72},
        ),
        (
            "fia_citation_complete",
            audit["fia_decision_citation_url"].str.startswith("https://").all(),
        ),
        (
            "included_evidence_span_complete",
            audit.loc[included, "fia_decision_evidence_span"].ne("").all(),
        ),
        (
            "corrected_lineage_complete",
            int(corrected.sum()) == 32
            and audit.loc[
                corrected,
                [
                    "model_correction_fields",
                    "model_correction_parent_values",
                    "model_correction_evidence",
                    "model_correction_rationale",
                ],
            ]
            .ne("")
            .all()
            .all(),
        ),
        (
            "analysis_adapter_complete",
            int(analysis_input["strict_model_audit_run_id"].eq(manifest["run_id"]).sum()) == 418
            and manifest["outputs"]["adjudication_coding_worklist.csv"]
            == _sha256(_csv_bytes(analysis_input)),
        ),
        (
            "exclusion_source_review_complete",
            int(exclusions.sum()) == 502
            and audit.loc[exclusions, "source_derived_exclusion_basis"].ne("").all()
            and not audit.loc[exclusions, "exclusion_source_review_status"]
            .eq("source_scope_conflict")
            .any(),
        ),
        (
            "version_pair_citations_complete",
            int(version_pairs.sum()) == 32
            and audit.loc[version_pairs, "version_successor_citation_url"]
            .str.startswith("https://")
            .all(),
        ),
        (
            "supporting_resolution_citations_complete",
            int(supporting_resolutions.sum()) == 2
            and audit.loc[supporting_resolutions, "supporting_context_citation_url"]
            .str.startswith("https://")
            .all(),
        ),
        (
            "rule_citation_complete",
            audit.loc[rule_comparison, "penalty_guideline_url"].str.startswith("https://").all(),
        ),
        (
            "model_disclosure_complete",
            audit["review_disclosure"]
            .eq("model_led_source_review_not_independent_human_annotation")
            .all(),
        ),
        (
            "terminal_statuses",
            bool(terminal.all()) if not allow_pending else True,
        ),
        (
            "bounded_unavailable_sources",
            int(audit["strict_model_review_status"].eq("model_unresolved_public_evidence").sum())
            == 4,
        ),
        (
            "manifest_hash",
            manifest["outputs"]["strict_model_case_audit.csv"] == _sha256(_csv_bytes(audit)),
        ),
        ("human_ledger_preserved", manifest["human_review_ledgers_modified"] is False),
    ]
    result = pd.DataFrame(
        {
            "control": [control for control, _ in controls],
            "status": ["pass" if passed else "fail" for _, passed in controls],
        }
    )
    if result["status"].eq("fail").any():
        failed = ", ".join(result.loc[result["status"].eq("fail"), "control"])
        raise ValueError(f"Strict model-audit validation failed: {failed}")
    return result
