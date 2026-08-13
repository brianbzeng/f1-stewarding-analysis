"""Deterministic, provenance-first queues for full-corpus manual coding."""

from __future__ import annotations

import hashlib
import io
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

DOCUMENT_QUEUE_FILENAME = "document_review_queue.csv"
ADJUDICATION_QUEUE_FILENAME = "adjudication_seed_queue.csv"
EXCLUSION_QA_FILENAME = "exclusion_qa_sample.csv"
QUEUE_MANIFEST_FILENAME = "manifest.json"

DOCUMENT_REVIEW_COLUMNS = [
    "document_review_id",
    "document_id",
    "event_id",
    "season",
    "round_number",
    "event_name",
    "event_date",
    "guideline_regime",
    "title",
    "source_url",
    "published_at",
    "archive_document_class",
    "content_document_class",
    "content_classification_basis",
    "source_availability_status",
    "is_recalled",
    "supersedes_document_id",
    "successor_document_id",
    "version_state_suggestion",
    "is_effective_version_suggestion",
    "content_status_suggestion",
    "parser_version",
    "parser_warning_count",
    "parser_warnings_json",
    "parser_review_required",
    "session_type_raw",
    "session_type_suggestion",
    "session_scope_suggestion",
    "offence_family_suggestion",
    "offence_family_group_suggestion",
    "all_matching_families_suggestion",
    "multiple_family_matches",
    "family_conflict_suggestion",
    "eligibility_suggestion",
    "eligibility_basis",
    "version_status_final",
    "session_scope_final",
    "offence_family_final",
    "eligibility_final",
    "exclusion_reason_final",
    "reviewer_id",
    "review_status",
    "review_notes",
]

ADJUDICATION_SEED_COLUMNS = [
    "adjudication_seed_id",
    "document_id",
    "event_id",
    "season",
    "round_number",
    "event_name",
    "event_date",
    "guideline_regime",
    "title",
    "source_url",
    "published_at",
    "supersedes_document_id",
    "version_state_suggestion",
    "parser_review_required",
    "driver_number_suggestion",
    "driver_number_basis_suggestion",
    "driver_name_suggestion",
    "participant_driver_numbers_suggestion",
    "affected_driver_numbers_suggestion",
    "multi_party_suggestion",
    "session_type_raw",
    "session_type_suggestion",
    "session_scope_suggestion",
    "incident_time_raw",
    "lap_numbers_suggestion",
    "turn_numbers_suggestion",
    "offence_family_suggestion",
    "offence_family_group_suggestion",
    "all_matching_families_suggestion",
    "multiple_family_matches",
    "family_conflict_suggestion",
    "outcome_family_suggestion",
    "penalty_seconds_suggestion",
    "penalty_points_suggestion",
    "grid_places_suggestion",
    "eligibility_suggestion",
    "eligibility_basis",
    "candidate_action_suggestion",
    "fact_text",
    "infringement_text",
    "decision_text",
    "reason_text",
    "adjudication_id_final",
    "incident_id_final",
    "accused_driver_number_final",
    "affected_driver_numbers_final",
    "session_type_final",
    "lap_number_final",
    "location_final",
    "incident_family_final",
    "outcome_family_final",
    "include_primary_final",
    "include_secondary_final",
    "exclusion_reason_final",
    "coder_id",
    "review_status",
    "coding_notes",
]

EXCLUSION_QA_COLUMNS = [
    "exclusion_qa_id",
    "document_id",
    "event_id",
    "season",
    "round_number",
    "event_name",
    "title",
    "source_url",
    "version_state_suggestion",
    "parser_review_required",
    "session_type_suggestion",
    "session_scope_suggestion",
    "offence_family_suggestion",
    "offence_family_group_suggestion",
    "eligibility_basis",
    "qa_stratum_id",
    "qa_stratum_size",
    "qa_selection_rank",
    "qa_selection_sha256",
    "qa_disposition",
    "corrected_session_scope",
    "corrected_offence_family",
    "reviewer_id",
    "review_status",
    "review_notes",
]

FINAL_DOCUMENT_FIELDS = [
    "version_status_final",
    "session_scope_final",
    "offence_family_final",
    "eligibility_final",
    "exclusion_reason_final",
    "reviewer_id",
    "review_status",
    "review_notes",
]

FINAL_ADJUDICATION_FIELDS = [
    "adjudication_id_final",
    "incident_id_final",
    "accused_driver_number_final",
    "affected_driver_numbers_final",
    "session_type_final",
    "lap_number_final",
    "location_final",
    "incident_family_final",
    "outcome_family_final",
    "include_primary_final",
    "include_secondary_final",
    "exclusion_reason_final",
    "coder_id",
    "review_status",
    "coding_notes",
]

FINAL_EXCLUSION_QA_FIELDS = [
    "qa_disposition",
    "corrected_session_scope",
    "corrected_offence_family",
    "reviewer_id",
    "review_status",
    "review_notes",
]


def load_outcome_document_population(
    connection: duckdb.DuckDBPyConnection,
    source_document_class: str = "steward_decision",
) -> pd.DataFrame:
    """Load every archive outcome label, including unavailable recalled versions."""

    return connection.execute(
        """
        WITH successor_links AS (
            SELECT supersedes_document_id AS predecessor_document_id,
                   min(document_id) AS successor_document_id,
                   count(*) AS successor_count
            FROM raw.source_documents
            WHERE supersedes_document_id IS NOT NULL
            GROUP BY supersedes_document_id
        )
        SELECT
            d.document_id,
            d.event_id,
            e.season,
            e.round_number,
            e.event_name,
            e.event_date,
            e.guideline_regime,
            d.title,
            d.document_url AS source_url,
            d.published_at,
            d.document_class AS archive_document_class,
            t.content_document_class,
            t.content_classification_basis,
            d.source_availability_status,
            d.is_recalled,
            d.supersedes_document_id,
            links.successor_document_id,
            coalesce(links.successor_count, 0) AS successor_count,
            t.parser_version,
            cast(t.parser_warnings_json AS VARCHAR) AS parser_warnings_json,
            t.driver_number,
            t.driver_name,
            t.session_type,
            t.incident_time_raw,
            t.fact_text,
            t.infringement_text,
            t.decision_text,
            t.reason_text
        FROM raw.source_documents AS d
        JOIN metadata.events AS e USING (event_id)
        LEFT JOIN raw.document_text AS t USING (document_id)
        LEFT JOIN successor_links AS links
          ON links.predecessor_document_id = d.document_id
        WHERE d.document_class = ?
        ORDER BY e.season, e.round_number, d.published_at, d.title, d.document_id
        """,
        [source_document_class],
    ).df()


def _missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _text(value: Any) -> str:
    return "" if _missing(value) else str(value)


def _one_line(value: Any) -> str:
    return " ".join(_text(value).split())


def _iso(value: Any) -> str:
    if _missing(value):
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _parse_warnings(value: Any) -> list[str]:
    if _missing(value) or not _text(value).strip():
        return []
    try:
        parsed = json.loads(_text(value))
    except json.JSONDecodeError:
        return ["unparseable_parser_warnings"]
    if not isinstance(parsed, list):
        return ["unparseable_parser_warnings"]
    return [str(item) for item in parsed]


def normalize_session_type(value: Any, season: Any = None) -> str:
    """Normalize observed FIA session labels without guessing from the sanction."""

    raw = _one_line(value)
    if not raw:
        return "Unknown"
    normalized = raw.casefold().replace("–", "-").replace("—", "-")
    if normalized == "sprint":
        return "Sprint"
    if normalized.startswith("race") and "reconnaissance" not in normalized:
        return "Race"
    if normalized == "qualifying":
        return "Qualifying"
    if normalized == "sprint qualifying" and not _missing(season) and int(season) <= 2022:
        return "Sprint"
    if normalized == "sprint qualifying":
        return "Sprint Qualifying"
    if normalized == "sprint shootout":
        return "Sprint Shootout"
    if normalized.startswith("practice") or normalized in {"p1", "p2", "p3"}:
        return "Practice"
    if "reconnaissance" in normalized or normalized in {
        "pre-race",
        "before the race",
        "pre-sprint",
    }:
        return "Pre-session"
    return "Other"


def _session_scope(session: str, settings: dict[str, Any]) -> str:
    if session in settings["primary_sessions"]:
        return "primary_race_sprint"
    if session in settings["secondary_sessions"]:
        return "secondary_qualifying"
    if session == "Unknown":
        return "unknown"
    return "out_of_scope_session"


def _classification_text(row: pd.Series) -> str:
    values = (
        row.get("title"),
        row.get("fact_text"),
        row.get("infringement_text"),
    )
    return _one_line(" ".join(_text(value) for value in values)).casefold()


def _family_matches(
    text: str, settings: dict[str, Any]
) -> list[tuple[str, str]]:
    matches: list[tuple[str, str]] = []
    groups = (
        ("primary", settings["primary_incident_patterns"]),
        ("secondary", settings["secondary_incident_patterns"]),
        ("excluded", settings["excluded_offence_patterns"]),
    )
    for group_name, families in groups:
        for family, patterns in families.items():
            if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns):
                matches.append((family, group_name))
    return matches


def _selected_family(matches: list[tuple[str, str]]) -> tuple[str, str]:
    if not matches:
        return "unclassified", "unclassified"
    return matches[0]


def _family_conflict(matches: list[tuple[str, str]]) -> bool:
    """Flag scope-relevant conflicts while allowing multiple exclusion labels."""

    if len(matches) <= 1:
        return False
    groups = {group for _, group in matches}
    in_scope_families = {family for family, group in matches if group != "excluded"}
    return len(groups) > 1 or len(in_scope_families) > 1


def _version_state(row: pd.Series) -> str:
    recalled = bool(row.get("is_recalled"))
    successor = _text(row.get("successor_document_id"))
    predecessor = _text(row.get("supersedes_document_id"))
    if recalled and successor:
        return "recalled_linked_predecessor"
    if recalled:
        return "recalled_unresolved"
    if predecessor:
        return "corrected_successor"
    return "live_standalone"


def _content_status(row: pd.Series) -> str:
    content_class = _text(row.get("content_document_class"))
    if not content_class:
        return "unparsed_archive_label"
    if content_class == "steward_decision":
        return "content_confirmed_decision"
    return f"content_mismatch_{content_class}"


def _eligibility(
    *,
    version_state: str,
    content_status: str,
    session_scope: str,
    family: str,
    family_group: str,
    family_conflict: bool,
) -> tuple[str, str]:
    if version_state == "recalled_linked_predecessor":
        return "version_exclusion_suggestion", "Recalled version has a verified live successor."
    if version_state == "recalled_unresolved":
        return (
            "version_resolution_required",
            "Recalled archive label has no recoverable successor and requires explicit "
            "disposition.",
        )
    if content_status != "content_confirmed_decision":
        return (
            "content_exclusion_suggestion",
            "Archive outcome label content-types as a non-decision or has no parsed decision body.",
        )
    if family_conflict:
        return (
            "manual_offence_review",
            "Source text matched multiple offence families; no automatic scope decision was made.",
        )
    if session_scope == "primary_race_sprint" and family_group == "primary":
        return "primary_candidate", f"Race/Sprint document matched primary family {family}."
    if session_scope == "secondary_qualifying" and family_group == "secondary":
        return "secondary_candidate", f"Qualifying document matched secondary family {family}."
    if family_group == "excluded":
        return (
            "out_of_scope_suggestion",
            f"Document matched predefined excluded offence family {family}.",
        )
    if session_scope == "out_of_scope_session":
        return "out_of_scope_suggestion", "Observed session is outside the frozen study scope."
    if session_scope == "unknown":
        return "manual_session_review", "No reliable session label was parsed from the document."
    if family_group in {"primary", "secondary"}:
        return (
            "out_of_scope_suggestion",
            "Incident family was recognized but the observed session is outside that population.",
        )
    return (
        "manual_offence_review",
        "Session may be in scope but no frozen incident-family rule matched the source text.",
    )


def _extract_driver_numbers(row: pd.Series) -> list[int]:
    text = " ".join(
        _text(row.get(field))
        for field in ("title", "fact_text", "infringement_text", "reason_text")
    )
    numbers: list[int] = []
    driver_number = row.get("driver_number")
    if not _missing(driver_number):
        numbers.append(int(driver_number))
    for match in re.finditer(r"\bcars?\s*(\d{1,2})\b", text, flags=re.IGNORECASE):
        number = int(match.group(1))
        if 1 <= number <= 99 and number not in numbers:
            numbers.append(number)
    return numbers


def _accused_driver_suggestion(row: pd.Series) -> tuple[int | str, str]:
    """Prefer the parsed subject, then an explicit first Car number in the FIA title."""

    driver_number = row.get("driver_number")
    if not _missing(driver_number):
        return int(driver_number), "parsed_decision_heading"
    title_match = re.search(r"\bcar\s*(\d{1,2})\b", _text(row.get("title")), re.IGNORECASE)
    if title_match:
        return int(title_match.group(1)), "official_title_first_car_reference"
    return "", "unavailable"


def _numbers(pattern: str, text: str) -> list[int]:
    values: list[int] = []
    for match in re.finditer(pattern, text, flags=re.IGNORECASE):
        value = int(match.group(1))
        if value not in values:
            values.append(value)
    return values


def _number_text(values: list[int]) -> str:
    return "|".join(str(value) for value in values)


def _outcome_suggestion(decision_text: Any) -> tuple[str, float | str, int | str, int | str]:
    decision = _one_line(decision_text).casefold()
    if not decision:
        return "review_required", "", "", ""

    if "no further action" in decision or "no action" in decision:
        outcome = "no_further_action"
    elif re.search(r"\bdisqualif", decision):
        outcome = "disqualification"
    elif re.search(r"\bstop[- ]and[- ]go\b", decision):
        outcome = "stop_go"
    elif re.search(r"\bdrive[- ]through\b", decision):
        outcome = "drive_through"
    elif re.search(r"\bgrid\s+(?:position\s+)?penalt|\bdrop\s+of\s+\d+\s+grid", decision):
        outcome = "grid_penalty"
    elif re.search(r"\b\d+(?:\.\d+)?[- ]?second(?:s)?\s+time\s+penalty\b", decision):
        outcome = "time_penalty"
    elif "reprimand" in decision:
        outcome = "reprimand"
    elif "warning" in decision:
        outcome = "warning"
    elif re.search(r"\bfine\b|\b€\s*\d|\beur\s*\d", decision):
        outcome = "fine"
    else:
        outcome = "other"

    seconds_match = re.search(
        r"\b(\d+(?:\.\d+)?)\s*[- ]?second(?:s)?\s+time\s+penalty\b", decision
    )
    seconds: float | str = float(seconds_match.group(1)) if seconds_match else ""
    if isinstance(seconds, float) and seconds.is_integer():
        seconds = int(seconds)
    points_match = re.search(r"\b(\d+)\s+penalty\s+point", decision)
    points: int | str = int(points_match.group(1)) if points_match else ""
    grid_match = re.search(
        r"(?:drop\s+of\s+|a\s+)(\d+)\s+(?:place|position)?s?\s*(?:grid|at\s+the\s+next)",
        decision,
    )
    grid_places: int | str = int(grid_match.group(1)) if grid_match else ""
    return outcome, seconds, points, grid_places


def _candidate_action(eligibility: str, parser_review_required: bool, driver_number: Any) -> str:
    if parser_review_required or _missing(driver_number):
        return "manual_split_or_scope_review"
    if eligibility == "primary_candidate":
        return "review_primary_adjudication"
    if eligibility == "secondary_candidate":
        return "review_secondary_adjudication"
    if eligibility in {"manual_session_review", "manual_offence_review"}:
        return "manual_scope_review"
    return "review_exclusion"


def build_full_corpus_coding_queues(
    population: pd.DataFrame,
    settings: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build document-version and live-decision seed queues from one frozen population."""

    required = {
        "document_id",
        "event_id",
        "season",
        "round_number",
        "event_name",
        "event_date",
        "guideline_regime",
        "title",
        "source_url",
        "published_at",
        "archive_document_class",
        "content_document_class",
        "content_classification_basis",
        "source_availability_status",
        "is_recalled",
        "supersedes_document_id",
        "successor_document_id",
        "successor_count",
        "parser_version",
        "parser_warnings_json",
        "driver_number",
        "driver_name",
        "session_type",
        "incident_time_raw",
        "fact_text",
        "infringement_text",
        "decision_text",
        "reason_text",
    }
    if missing := required - set(population.columns):
        raise ValueError(f"Outcome population is missing: {', '.join(sorted(missing))}")
    if population["document_id"].duplicated().any():
        raise ValueError("Outcome population contains duplicate document IDs")
    if (population["successor_count"] > 1).any():
        raise ValueError("A recalled outcome version has multiple configured successors")

    document_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    for _, row in population.iterrows():
        version_state = _version_state(row)
        content_status = _content_status(row)
        warnings = _parse_warnings(row.get("parser_warnings_json"))
        parser_review_required = bool(warnings)
        session = normalize_session_type(row.get("session_type"), row.get("season"))
        session_scope = _session_scope(session, settings)
        matches = _family_matches(_classification_text(row), settings)
        family, family_group = _selected_family(matches)
        matching_families = [match[0] for match in matches]
        family_conflict = _family_conflict(matches)
        eligibility, eligibility_basis = _eligibility(
            version_state=version_state,
            content_status=content_status,
            session_scope=session_scope,
            family=family,
            family_group=family_group,
            family_conflict=family_conflict,
        )
        effective_version = not bool(row.get("is_recalled")) and (
            content_status == "content_confirmed_decision"
        )

        document_payload = {
            "document_review_id": f"document-review-{row['document_id']}",
            "document_id": row["document_id"],
            "event_id": row["event_id"],
            "season": int(row["season"]),
            "round_number": int(row["round_number"]),
            "event_name": row["event_name"],
            "event_date": _iso(row["event_date"]),
            "guideline_regime": row["guideline_regime"],
            "title": _one_line(row["title"]),
            "source_url": _text(row["source_url"]),
            "published_at": _iso(row["published_at"]),
            "archive_document_class": row["archive_document_class"],
            "content_document_class": _text(row["content_document_class"]),
            "content_classification_basis": _text(row["content_classification_basis"]),
            "source_availability_status": row["source_availability_status"],
            "is_recalled": bool(row["is_recalled"]),
            "supersedes_document_id": _text(row["supersedes_document_id"]),
            "successor_document_id": _text(row["successor_document_id"]),
            "version_state_suggestion": version_state,
            "is_effective_version_suggestion": effective_version,
            "content_status_suggestion": content_status,
            "parser_version": _text(row["parser_version"]),
            "parser_warning_count": len(warnings),
            "parser_warnings_json": json.dumps(warnings, ensure_ascii=False),
            "parser_review_required": parser_review_required,
            "session_type_raw": _one_line(row["session_type"]),
            "session_type_suggestion": session,
            "session_scope_suggestion": session_scope,
            "offence_family_suggestion": family,
            "offence_family_group_suggestion": family_group,
            "all_matching_families_suggestion": "|".join(matching_families),
            "multiple_family_matches": len(matching_families) > 1,
            "family_conflict_suggestion": family_conflict,
            "eligibility_suggestion": eligibility,
            "eligibility_basis": eligibility_basis,
            **{field: "" for field in FINAL_DOCUMENT_FIELDS},
        }
        document_rows.append(document_payload)

        if not effective_version:
            continue
        participants = _extract_driver_numbers(row)
        accused, accused_basis = _accused_driver_suggestion(row)
        affected = [number for number in participants if number != accused]
        source_text = " ".join(
            _text(row.get(field)) for field in ("fact_text", "infringement_text", "reason_text")
        )
        lap_numbers = _numbers(r"\blap\s*(\d{1,3})\b", source_text)
        turn_numbers = _numbers(r"\bturns?\s*(\d{1,2})\b", source_text)
        outcome, seconds, points, grid_places = _outcome_suggestion(row.get("decision_text"))
        candidate_payload = {
            "adjudication_seed_id": f"adjudication-seed-{row['document_id']}",
            "document_id": row["document_id"],
            "event_id": row["event_id"],
            "season": int(row["season"]),
            "round_number": int(row["round_number"]),
            "event_name": row["event_name"],
            "event_date": _iso(row["event_date"]),
            "guideline_regime": row["guideline_regime"],
            "title": _one_line(row["title"]),
            "source_url": _text(row["source_url"]),
            "published_at": _iso(row["published_at"]),
            "supersedes_document_id": _text(row["supersedes_document_id"]),
            "version_state_suggestion": version_state,
            "parser_review_required": parser_review_required,
            "driver_number_suggestion": accused,
            "driver_number_basis_suggestion": accused_basis,
            "driver_name_suggestion": _one_line(row.get("driver_name")),
            "participant_driver_numbers_suggestion": _number_text(participants),
            "affected_driver_numbers_suggestion": _number_text(affected),
            "multi_party_suggestion": len(participants) >= 3,
            "session_type_raw": _one_line(row.get("session_type")),
            "session_type_suggestion": session,
            "session_scope_suggestion": session_scope,
            "incident_time_raw": _one_line(row.get("incident_time_raw")),
            "lap_numbers_suggestion": _number_text(lap_numbers),
            "turn_numbers_suggestion": _number_text(turn_numbers),
            "offence_family_suggestion": family,
            "offence_family_group_suggestion": family_group,
            "all_matching_families_suggestion": "|".join(matching_families),
            "multiple_family_matches": len(matching_families) > 1,
            "family_conflict_suggestion": family_conflict,
            "outcome_family_suggestion": outcome,
            "penalty_seconds_suggestion": seconds,
            "penalty_points_suggestion": points,
            "grid_places_suggestion": grid_places,
            "eligibility_suggestion": eligibility,
            "eligibility_basis": eligibility_basis,
            "candidate_action_suggestion": _candidate_action(
                eligibility, parser_review_required, accused
            ),
            "fact_text": _one_line(row.get("fact_text")),
            "infringement_text": _one_line(row.get("infringement_text")),
            "decision_text": _one_line(row.get("decision_text")),
            "reason_text": _one_line(row.get("reason_text")),
            **{field: "" for field in FINAL_ADJUDICATION_FIELDS},
        }
        candidate_rows.append(candidate_payload)

    documents = pd.DataFrame(document_rows, columns=DOCUMENT_REVIEW_COLUMNS)
    candidates = pd.DataFrame(candidate_rows, columns=ADJUDICATION_SEED_COLUMNS)
    expected_candidates = set(
        population.loc[
            ~population["is_recalled"].astype(bool)
            & population["content_document_class"].eq("steward_decision"),
            "document_id",
        ]
    )
    if len(documents) != len(population) or documents["document_id"].duplicated().any():
        raise ValueError("Document review queue does not preserve the source denominator")
    if set(candidates["document_id"]) != expected_candidates:
        raise ValueError("Adjudication seed does not match live content-confirmed decisions")
    if not documents[FINAL_DOCUMENT_FIELDS].eq("").all().all():
        raise ValueError("Generated document-review final fields must be blank")
    if not candidates[FINAL_ADJUDICATION_FIELDS].eq("").all().all():
        raise ValueError("Generated adjudication final fields must be blank")
    return documents, candidates


def build_exclusion_qa_sample(
    documents: pd.DataFrame,
    settings: dict[str, Any],
) -> pd.DataFrame:
    """Select a deterministic stratified audit sample of proposed scope exclusions."""

    qa_settings = settings["exclusion_quality_control"]
    excluded = documents.loc[
        documents["eligibility_suggestion"].eq("out_of_scope_suggestion")
    ].copy()
    if excluded.empty:
        return pd.DataFrame(columns=EXCLUSION_QA_COLUMNS)
    excluded["qa_stratum_id"] = (
        excluded["season"].astype(str)
        + "|"
        + excluded["session_scope_suggestion"].astype(str)
        + "|"
        + excluded["offence_family_suggestion"].astype(str)
    )
    excluded["qa_selection_sha256"] = excluded["document_id"].map(
        lambda document_id: hashlib.sha256(
            f"{qa_settings['hash_salt']}|{document_id}".encode()
        ).hexdigest()
    )

    rows: list[dict[str, Any]] = []
    for stratum_id, group in excluded.groupby("qa_stratum_id", sort=True):
        stratum_size = len(group)
        target = math.ceil(stratum_size * qa_settings["target_fraction"])
        sample_size = min(
            stratum_size,
            qa_settings["maximum_per_stratum"],
            max(qa_settings["minimum_per_stratum"], target),
        )
        selected = group.sort_values(
            ["qa_selection_sha256", "document_id"], kind="stable"
        ).head(sample_size)
        for rank, (_, row) in enumerate(selected.iterrows(), start=1):
            rows.append(
                {
                    "exclusion_qa_id": f"exclusion-qa-{row['document_id']}",
                    "document_id": row["document_id"],
                    "event_id": row["event_id"],
                    "season": row["season"],
                    "round_number": row["round_number"],
                    "event_name": row["event_name"],
                    "title": row["title"],
                    "source_url": row["source_url"],
                    "version_state_suggestion": row["version_state_suggestion"],
                    "parser_review_required": row["parser_review_required"],
                    "session_type_suggestion": row["session_type_suggestion"],
                    "session_scope_suggestion": row["session_scope_suggestion"],
                    "offence_family_suggestion": row["offence_family_suggestion"],
                    "offence_family_group_suggestion": row[
                        "offence_family_group_suggestion"
                    ],
                    "eligibility_basis": row["eligibility_basis"],
                    "qa_stratum_id": stratum_id,
                    "qa_stratum_size": stratum_size,
                    "qa_selection_rank": rank,
                    "qa_selection_sha256": row["qa_selection_sha256"],
                    **{field: "" for field in FINAL_EXCLUSION_QA_FIELDS},
                }
            )
    sample = pd.DataFrame(rows, columns=EXCLUSION_QA_COLUMNS).sort_values(
        ["season", "qa_stratum_id", "qa_selection_rank", "document_id"],
        kind="stable",
        ignore_index=True,
    )
    if sample["document_id"].duplicated().any():
        raise ValueError("Exclusion QA sample contains duplicate documents")
    if not set(sample["document_id"]).issubset(set(excluded["document_id"])):
        raise ValueError("Exclusion QA sample contains a non-exclusion document")
    if not sample[FINAL_EXCLUSION_QA_FIELDS].eq("").all().all():
        raise ValueError("Generated exclusion QA final fields must be blank")
    return sample


def _csv_bytes(frame: pd.DataFrame) -> bytes:
    stream = io.StringIO(newline="")
    frame.to_csv(stream, index=False, lineterminator="\n")
    return stream.getvalue().encode("utf-8")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _logical_population_digest(population: pd.DataFrame) -> str:
    columns = [
        "document_id",
        "event_id",
        "title",
        "source_url",
        "archive_document_class",
        "content_document_class",
        "is_recalled",
        "supersedes_document_id",
        "successor_document_id",
        "parser_version",
        "parser_warnings_json",
    ]
    records: list[dict[str, Any]] = []
    for record in population[columns].to_dict(orient="records"):
        records.append({key: _text(value) for key, value in record.items()})
    payload = json.dumps(records, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return _sha256(payload.encode("utf-8"))


def build_queue_manifest(
    population: pd.DataFrame,
    documents: pd.DataFrame,
    candidates: pd.DataFrame,
    exclusion_qa: pd.DataFrame,
    document_bytes: bytes,
    candidate_bytes: bytes,
    exclusion_qa_bytes: bytes,
    settings: dict[str, Any],
    settings_sha256: str,
) -> dict[str, Any]:
    """Create a deterministic manifest for the unedited seed bundle."""

    return {
        "schema_version": settings["schema_version"],
        "source_population_sha256": _logical_population_digest(population),
        "settings_sha256": settings_sha256,
        "source_counts": {
            "archive_outcome_labels": int(len(population)),
            "recalled_outcome_labels": int(population["is_recalled"].sum()),
            "content_confirmed_decisions": int(
                population["content_document_class"].eq("steward_decision").sum()
            ),
            "live_content_confirmed_decisions": int(len(candidates)),
            "corrected_successors": int(
                documents["version_state_suggestion"].eq("corrected_successor").sum()
            ),
            "recalled_linked_predecessors": int(
                documents["version_state_suggestion"]
                .eq("recalled_linked_predecessor")
                .sum()
            ),
            "recalled_unresolved": int(
                documents["version_state_suggestion"].eq("recalled_unresolved").sum()
            ),
            "parser_review_required": int(documents["parser_review_required"].sum()),
        },
        "outputs": {
            DOCUMENT_QUEUE_FILENAME: {
                "sha256": _sha256(document_bytes),
                "row_count": int(len(documents)),
            },
            ADJUDICATION_QUEUE_FILENAME: {
                "sha256": _sha256(candidate_bytes),
                "row_count": int(len(candidates)),
            },
            EXCLUSION_QA_FILENAME: {
                "sha256": _sha256(exclusion_qa_bytes),
                "row_count": int(len(exclusion_qa)),
            },
        },
        "eligibility_suggestion_counts": dict(
            sorted(Counter(documents["eligibility_suggestion"]).items())
        ),
        "candidate_action_counts": dict(
            sorted(Counter(candidates["candidate_action_suggestion"]).items())
        ),
        "exclusion_quality_control": {
            "population_rows": int(
                documents["eligibility_suggestion"].eq("out_of_scope_suggestion").sum()
            ),
            "sample_rows": int(len(exclusion_qa)),
            "strata": int(exclusion_qa["qa_stratum_id"].nunique()),
            "target_fraction": settings["exclusion_quality_control"]["target_fraction"],
            "minimum_per_stratum": settings["exclusion_quality_control"][
                "minimum_per_stratum"
            ],
            "maximum_per_stratum": settings["exclusion_quality_control"][
                "maximum_per_stratum"
            ],
        },
        "interpretation_boundary": (
            "Machine suggestions prioritize manual review and are not final eligibility, "
            "fault, consistency, or fairness findings."
        ),
    }


def _write_or_verify(path: Path, payload: bytes, overwrite: bool) -> str:
    if path.exists():
        current = path.read_bytes()
        if current == payload:
            return "unchanged"
        if not overwrite:
            raise FileExistsError(
                f"{path} differs from the generated seed; rerun with overwrite only after review"
            )
    path.write_bytes(payload)
    return "written"


def write_full_corpus_seed_bundle(
    population: pd.DataFrame,
    documents: pd.DataFrame,
    candidates: pd.DataFrame,
    exclusion_qa: pd.DataFrame,
    output_directory: Path,
    settings: dict[str, Any],
    settings_path: Path,
    *,
    overwrite: bool = False,
) -> tuple[dict[str, Any], dict[str, str]]:
    """Write stable CSV queues and a checksum manifest, protecting reviewed edits by default."""

    output_directory.mkdir(parents=True, exist_ok=True)
    document_bytes = _csv_bytes(documents)
    candidate_bytes = _csv_bytes(candidates)
    exclusion_qa_bytes = _csv_bytes(exclusion_qa)
    manifest = build_queue_manifest(
        population,
        documents,
        candidates,
        exclusion_qa,
        document_bytes,
        candidate_bytes,
        exclusion_qa_bytes,
        settings,
        _sha256(settings_path.read_bytes()),
    )
    manifest_bytes = (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    payloads = {
        DOCUMENT_QUEUE_FILENAME: document_bytes,
        ADJUDICATION_QUEUE_FILENAME: candidate_bytes,
        EXCLUSION_QA_FILENAME: exclusion_qa_bytes,
        QUEUE_MANIFEST_FILENAME: manifest_bytes,
    }
    statuses = {
        name: _write_or_verify(output_directory / name, payload, overwrite)
        for name, payload in payloads.items()
    }
    return manifest, statuses


def audit_full_corpus_seed_bundle(
    population: pd.DataFrame,
    documents: pd.DataFrame,
    candidates: pd.DataFrame,
    exclusion_qa: pd.DataFrame,
    output_directory: Path,
    settings: dict[str, Any],
    settings_path: Path,
) -> pd.DataFrame:
    """Compare a stored seed bundle with a deterministic rebuild from the current warehouse."""

    document_bytes = _csv_bytes(documents)
    candidate_bytes = _csv_bytes(candidates)
    exclusion_qa_bytes = _csv_bytes(exclusion_qa)
    expected_manifest = build_queue_manifest(
        population,
        documents,
        candidates,
        exclusion_qa,
        document_bytes,
        candidate_bytes,
        exclusion_qa_bytes,
        settings,
        _sha256(settings_path.read_bytes()),
    )
    expected = {
        DOCUMENT_QUEUE_FILENAME: document_bytes,
        ADJUDICATION_QUEUE_FILENAME: candidate_bytes,
        EXCLUSION_QA_FILENAME: exclusion_qa_bytes,
        QUEUE_MANIFEST_FILENAME: (
            json.dumps(expected_manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8"),
    }
    rows = []
    for name, payload in expected.items():
        path = output_directory / name
        exists = path.exists()
        actual = path.read_bytes() if exists else b""
        rows.append(
            {
                "control": name,
                "status": "pass" if exists and actual == payload else "fail",
                "expected_sha256": _sha256(payload),
                "actual_sha256": _sha256(actual) if exists else "missing",
            }
        )
    return pd.DataFrame(rows)
