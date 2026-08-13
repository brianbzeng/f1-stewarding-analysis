"""Build the disclosed GPT-5.6 Sol full-corpus review release.

The script preserves the original first-pass coding and protected lineage, writes a separate
content-addressed model-review run, and never describes model review as independent human review.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from f1stewards.coding_queue import (
    _classification_text,
    _content_status,
    _eligibility,
    _family_conflict,
    _family_matches,
    _selected_family,
    _session_scope,
    _version_state,
    infer_session_type,
)
from f1stewards.config import load_full_corpus_coding_settings
from f1stewards.first_pass import explicit_fault_language
from f1stewards.warehouse import DEFAULT_DB_PATH

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT
    / "data"
    / "manual"
    / "full_corpus_review_rounds"
    / "lineage_rebuild"
    / "recalled_versions"
    / "full-coding-e0192ecbd9e4"
)
RUN_ROOT = ROOT / "data" / "manual" / "model_review_runs"
WORKSPACE_ROOT = ROOT / "data" / "manual" / "full_corpus_model_review"
PROTOCOL_PATH = ROOT / "docs" / "model_review_protocol.md"

MODEL_ID = "gpt-5.6-sol"
REVIEWER_ID = "gpt-5.6-sol-model-review-2026-08-13"
PROTOCOL_VERSION = "gpt-5.6-sol-full-corpus-review-v1"

DOCUMENT_FILE = "document_review_worklist.csv"
ADJUDICATION_FILE = "adjudication_coding_worklist.csv"
QA_FILE = "exclusion_qa_worklist.csv"
MANIFEST_FILE = "workspace_manifest.json"

SOURCE_EVIDENCE_FIELDS = (
    "title",
    "source_url",
    "fact_text",
    "infringement_text",
    "decision_text",
    "reason_text",
)

# Source-version relations confirmed during the GPT-5.6 Sol review. The protected first pass did
# not link these corrected/replacement PDFs, so they are reconciled here with an explicit audit.
SUPERSEDED_BY = {
    "fia-2018-rus-068325d75a12": "fia-2018-rus-7546295eaaf7",
    "fia-2018-aze-bffe4d5c0c61": "fia-2018-aze-4fbe7e105140",
    "fia-2019-hun-4a7861e9ecc4": "fia-2019-hun-c0dc5008cf12",
    "fia-2019-hun-eca52dd0bc62": "fia-2019-hun-c0dc5008cf12",
    # The 2019 Italy Car 23 sources are distinct Practice and Qualifying rulings despite the later
    # title containing "Corrected"; both intentionally remain effective.
    "fia-2020-aut-16fa54538da4": "fia-2020-aut-569c9e9630a3",
    "fia-2020-bel-f7cfe6b0d0cc": "fia-2020-bel-0cd81c691fc7",
    "fia-2020-esp-511e2fdd60d6": "fia-2020-esp-c7dc65a7f1cb",
    "fia-2020-abu-2641434ef410": "fia-2020-abu-ac8d3a942174",
    "fia-2020-abu-2bc3d25142b0": "fia-2020-abu-7fd8bd33a7e6",
    "fia-2020-rus-343d3fed4987": "fia-2020-rus-7006c84c4e7b",
    "fia-2020-rus-f74b747f503c": "fia-2020-rus-6ec04d56206c",
    "fia-2021-rus-0acd87099fab": "fia-2021-rus-4272fd241363",
    "fia-2021-tur-67cb79176129": "fia-2021-tur-93d16b7d94df",
    "fia-2022-aze-c6ed5c47671b": "fia-2022-aze-c11f775a941f",
    "fia-2022-ned-dfaf94f0d589": "fia-2022-ned-7fdceb08323e",
    "fia-2023-ned-4f1debc86373": "fia-2023-ned-9843e0f12eb2",
}
CONFIRMED_EXISTING_SUPERSEDED = {"fia-2019-ita-b42dad90f42f"}
DETERMINISTIC_INCLUDE = {"primary_candidate", "secondary_candidate"}
DETERMINISTIC_EXCLUDE = {
    "content_exclusion_suggestion",
    "out_of_scope_suggestion",
    "version_exclusion_suggestion",
}
SESSION_SCOPE_FINAL = {
    "primary_race_sprint": "primary",
    "secondary_qualifying": "secondary",
    "out_of_scope_session": "out_of_scope",
}
VERSION_STATUS_FINAL = {
    "corrected_successor": "effective",
    "live_standalone": "effective",
    "recalled_linked_predecessor": "superseded",
    "recalled_unresolved": "recalled_unavailable",
}


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _evidence_hash(row: pd.Series, source: pd.Series | None = None) -> str:
    evidence_row = source if source is not None else row
    evidence = {field: str(evidence_row.get(field, "")) for field in SOURCE_EVIDENCE_FIELDS}
    evidence["raw_text"] = str(evidence_row.get("raw_text", ""))
    return _sha256(_canonical_json(evidence).encode("utf-8"))


def _linked_evidence_hash(row: pd.Series, successor: pd.Series) -> str:
    evidence = {
        "predecessor_document_id": str(row.get("document_id", "")),
        "predecessor_title": str(row.get("title", "")),
        "predecessor_source_url": str(row.get("source_url", "")),
        "successor_document_id": str(row.get("successor_document_id", "")),
        "successor_source_sha256": _evidence_hash(successor),
    }
    return _sha256(_canonical_json(evidence).encode("utf-8"))


def _load_source_text() -> pd.DataFrame:
    import duckdb

    with duckdb.connect(str(DEFAULT_DB_PATH), read_only=True) as connection:
        return connection.sql(
            """
            SELECT document_id, raw_text, fact_text, infringement_text, decision_text,
                   reason_text, parser_warnings_json, driver_number, driver_name, session_type,
                   incident_time_raw, content_document_class, content_classification_basis
            FROM raw.document_text
            ORDER BY document_id
            """
        ).df()


def _source_only_document_coding(
    row: pd.Series,
    source_lookup: pd.DataFrame,
    settings: dict[str, Any],
) -> dict[str, str]:
    """Re-derive document scope from source text without reading prior final fields."""

    if row["document_id"] in source_lookup.index:
        source = source_lookup.loc[row["document_id"]]
        payload = row.copy()
        for field in (
            "raw_text",
            "fact_text",
            "infringement_text",
            "decision_text",
            "reason_text",
            "parser_warnings_json",
            "driver_number",
            "driver_name",
            "session_type",
            "incident_time_raw",
            "content_document_class",
            "content_classification_basis",
        ):
            payload[field] = source.get(field, "")
        # CSV booleans are strings; normalize before calling the queue rules because
        # ``bool("False")`` is true and would mark almost every source as recalled.
        payload["is_recalled"] = str(payload.get("is_recalled", "")).casefold() == "true"
        payload["successor_count"] = 1 if str(payload["successor_document_id"]).strip() else 0
        version = _version_state(payload)
        content = _content_status(payload)
        session = infer_session_type(payload)
        session_scope = _session_scope(session, settings)
        matches = _family_matches(
            _classification_text(payload),
            settings,
            incident_text=_classification_text(payload, include_reason=True),
        )
        family, family_group = _selected_family(matches)
        eligibility, _ = _eligibility(
            version_state=version,
            content_status=content,
            session_scope=session_scope,
            family=family,
            family_group=family_group,
            family_conflict=_family_conflict(matches),
        )
        return {
            "version": version,
            "content": content,
            "session_scope": session_scope,
            "family": family,
            "eligibility": eligibility,
            "source_excludes": eligibility
            not in {"primary_candidate", "secondary_candidate"},
            "source_evidence_sha256": _evidence_hash(row, source),
            "evidence_basis": "source_text_reclassification",
        }
    if str(row["is_recalled"]).casefold() != "true":
        raise ValueError(f"Non-recalled source lacks parsed text: {row['document_id']}")
    successor_id = str(row.get("successor_document_id", "")).strip()
    if successor_id and successor_id in source_lookup.index:
        evidence_hash = _linked_evidence_hash(row, source_lookup.loc[successor_id])
        evidence_basis = "archive_predecessor_and_linked_successor_text"
    else:
        evidence_hash = _evidence_hash(row)
        evidence_basis = "archive_metadata_only"
    return {
        "version": str(row["version_state_suggestion"]),
        "content": str(row["content_status_suggestion"]),
        "session_scope": str(row["session_scope_suggestion"]),
        "family": str(row["offence_family_suggestion"]),
        "eligibility": str(row["eligibility_suggestion"]),
        "source_excludes": True,
        "source_evidence_sha256": evidence_hash,
        "evidence_basis": evidence_basis,
    }


def _validate_document_disposition(
    row: pd.Series,
    source_coding: dict[str, Any],
    settings: dict[str, Any],
) -> str:
    """Check the saved disposition against a source-only classification before agreement."""

    document_id = str(row["document_id"])
    expected_version = (
        "superseded"
        if document_id in SUPERSEDED_BY or document_id in CONFIRMED_EXISTING_SUPERSEDED
        else VERSION_STATUS_FINAL[str(source_coding["version"])]
    )
    if str(row["version_status_final"]) != expected_version:
        raise ValueError(
            f"Version disposition disagrees with source evidence: {document_id} "
            f"({row['version_status_final']} != {expected_version})"
        )

    final_include = str(row["eligibility_final"]) == "include"
    eligibility = str(source_coding["eligibility"])
    if document_id in SUPERSEDED_BY and final_include:
        raise ValueError(f"Superseded predecessor remains included: {document_id}")
    if eligibility in DETERMINISTIC_INCLUDE and document_id not in SUPERSEDED_BY:
        if not final_include:
            raise ValueError(f"Source-defined candidate was excluded: {document_id}")
        review_path = "source_rule_exact_agreement"
    elif eligibility in DETERMINISTIC_EXCLUDE or eligibility == "version_resolution_required":
        if final_include:
            raise ValueError(f"Source-defined exclusion was included: {document_id}")
        review_path = "source_rule_exact_agreement"
    else:
        review_path = "targeted_source_resolution"

    if final_include:
        scope = str(row["session_scope_final"])
        family = str(row["offence_family_final"])
        valid_primary = scope == "primary" and family in settings["primary_incident_patterns"]
        valid_secondary = (
            scope == "secondary" and family in settings["secondary_incident_patterns"]
        )
        if not (valid_primary or valid_secondary):
            raise ValueError(f"Included document has an invalid scope/family pair: {document_id}")
        source_scope = SESSION_SCOPE_FINAL.get(str(source_coding["session_scope"]))
        if source_scope and source_scope != scope:
            raise ValueError(f"Included document session disagrees with source: {document_id}")
        source_family = str(source_coding["family"])
        if eligibility in DETERMINISTIC_INCLUDE and source_family != family:
            raise ValueError(f"Included document family disagrees with source: {document_id}")
    return review_path


def _append_note(original: Any, addition: str) -> str:
    text = str(original or "").strip()
    return f"{text} {addition}".strip()


def _decision_outcome(decision_text: Any) -> str:
    """Classify only an outcome stated in the official decision text."""

    text = re.sub(r"\s+", " ", str(decision_text).casefold()).strip()
    patterns = (
        ("no_further_action", r"\bno further action\b|\bno penalty (?:is |was )?imposed\b"),
        (
            "grid_penalty",
            r"\b(?:drop of |grid place drop|grid place penalty|grid position penalty|"
            r"grid penalty|drop .* grid positions?|grid positions? drop|"
            r"positions? on the starting grid)\b",
        ),
        ("stop_go", r"\bstop[- ](?:and[- ])?go\b"),
        ("drive_through", r"\bdrive[- ]through\b"),
        ("disqualification", r"\bdisqualif"),
        ("reprimand", r"\breprimand\b"),
        ("warning", r"\bwarning\b"),
        (
            "time_penalty",
            r"\b(?:time penalty|penalty of \d+(?:\.\d+)? seconds?|"
            r"\d+(?:\.\d+)? second(?:s)? penalty|"
            r"\d+(?:\.\d+)? seconds? (?:is |are )?(?:added|imposed))\b",
        ),
    )
    matches = [label for label, pattern in patterns if re.search(pattern, text)]
    if not matches:
        raise ValueError(
            f"Decision outcome is not classifiable from decision text: {decision_text}"
        )
    # Patterns are ordered from the specific formal sanction to its possible time-equivalent text.
    # For example, a post-race drive-through can also say that 20 seconds were added.
    return matches[0]


def _number_before(text: str, phrase_pattern: str) -> str:
    words = {
        "one": "1",
        "two": "2",
        "three": "3",
        "four": "4",
        "five": "5",
        "ten": "10",
    }
    match = re.search(rf"\b(\d+(?:\.\d+)?|{'|'.join(words)})\s+{phrase_pattern}", text)
    if not match:
        return ""
    return words.get(match.group(1), match.group(1))


def _model_fault_language(row: pd.Series) -> str:
    """Code written responsibility conservatively; never infer severity from the penalty."""

    secondary = str(row["include_secondary_final"]).casefold() == "true"
    explicit = explicit_fault_language(row.get("reason_text", ""), secondary=secondary)
    if explicit:
        return explicit
    text = re.sub(r"\s+", " ", str(row.get("reason_text", "")).casefold()).strip()
    text = text.replace("“", "").replace("”", "").replace('"', "")
    if re.search(r"\bracing.{0,15}\bincident\b", text):
        return "racing_incident"
    if re.search(r"\bwhol+y or pred[eo]omin", text):
        return "predominantly_to_blame"
    if re.search(r"\b(?:accepted|admitted).{0,100}\b(?:his|her|their) (?:fault|mistake)\b", text):
        return "wholly_to_blame"
    if str(row["incident_family_final"]) in {
        "gaining_advantage_off_track",
        "moving_under_braking",
        "multiple_defensive_moves",
    }:
        return "not_applicable"
    # This means the source does not state a controlled degree of responsibility. It does not
    # mean that the stewards found no fault.
    return "no_conclusion"


def _review_documents(
    documents: pd.DataFrame,
    source_lookup: pd.DataFrame,
    settings: dict[str, Any],
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    output = documents.copy()
    audits: list[dict[str, Any]] = []
    for index, row in output.iterrows():
        source_coding = _source_only_document_coding(row, source_lookup, settings)
        corrections: dict[str, dict[str, str]] = {}
        successor = SUPERSEDED_BY.get(str(row["document_id"]))
        if successor:
            new_values = {
                "version_status_final": "superseded",
                "eligibility_final": "exclude",
                "exclusion_reason_final": "superseded_corrected_predecessor",
            }
            for field, after in new_values.items():
                before = str(row[field])
                if before != after:
                    corrections[field] = {"before": before, "after": after}
                    output.at[index, field] = after
            output.at[index, "review_notes"] = _append_note(
                row["review_notes"], f"Superseded by {successor}.",
            )
            row = output.loc[index]
        required = ("version_status_final", "eligibility_final")
        if any(not str(row[field]).strip() for field in required):
            raise ValueError(f"Incomplete document disposition: {row['document_review_id']}")
        excluded = "excl" in str(row["eligibility_final"]).casefold()
        if excluded and not str(row["exclusion_reason_final"]).strip():
            raise ValueError(f"Excluded document lacks a reason: {row['document_review_id']}")
        if not excluded and (
            not str(row["session_scope_final"]).strip()
            or not str(row["offence_family_final"]).strip()
        ):
            raise ValueError(f"Included document lacks scope coding: {row['document_review_id']}")
        review_path = _validate_document_disposition(row, source_coding, settings)
        metadata_only = source_coding["evidence_basis"] == "archive_metadata_only"
        status = (
            "model_reviewed_corrected"
            if corrections
            else "source_unavailable_model_review"
            if metadata_only
            else "model_reviewed_agree"
        )
        prior_status = str(row["review_status"])
        prior_reviewer = str(row["reviewer_id"])
        output.at[index, "reviewer_id"] = REVIEWER_ID
        output.at[index, "review_status"] = status
        output.at[index, "review_notes"] = _append_note(
            row["review_notes"],
            "GPT-5.6 Sol checked the final disposition against the available official source "
            "record and cross-queue rules. Model review only; no independent human review.",
        )
        audits.append(
            {
                "queue": "documents",
                "row_id": row["document_review_id"],
                "document_id": row["document_id"],
                "source_url": row["source_url"],
                "source_evidence_sha256": source_coding["source_evidence_sha256"],
                "prior_review_status": prior_status,
                "prior_reviewer_id": prior_reviewer,
                "model_decision": (
                    "corrected"
                    if corrections
                    else "agree_metadata_only"
                    if metadata_only
                    else "agree"
                ),
                "model_review_status": status,
                "corrected_fields_json": _canonical_json(corrections),
                "evidence_basis": source_coding["evidence_basis"],
                "review_path": review_path,
                "rationale": (
                    "A corrected or replacement source supersedes this earlier document."
                    if corrections
                    else "Archive metadata supports the version exclusion; source binary "
                    "unavailable."
                    if metadata_only
                    else "The source-only classification and reconciled final disposition agree "
                    "on the frozen analytical boundary."
                ),
                "independent_human_review": False,
            }
        )
    return output, audits


def _review_adjudications(
    adjudications: pd.DataFrame,
    reviewed_documents: pd.DataFrame,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    output = adjudications.copy()
    document_lookup = reviewed_documents.set_index("document_id")
    audits: list[dict[str, Any]] = []
    for index, row in output.iterrows():
        corrections: dict[str, dict[str, str]] = {}
        if str(row["document_id"]) in SUPERSEDED_BY:
            new_values = {
                "adjudication_id_final": "",
                "incident_id_final": "",
                "fault_language_final": "not_applicable",
                "include_primary_final": "false",
                "include_secondary_final": "false",
                "exclusion_reason_final": "superseded_corrected_predecessor",
            }
            for field, after in new_values.items():
                before = str(row[field])
                if before != after:
                    corrections[field] = {"before": before, "after": after}
                    output.at[index, field] = after
            row = output.loc[index]
        included = str(row["include_primary_final"]).casefold() == "true" or str(
            row["include_secondary_final"]
        ).casefold() == "true"
        if included:
            source_outcome = _decision_outcome(row["decision_text"])
            if source_outcome != str(row["outcome_family_final"]):
                corrections["outcome_family_final"] = {
                    "before": str(row["outcome_family_final"]),
                    "after": source_outcome,
                }
                output.at[index, "outcome_family_final"] = source_outcome
            decision = re.sub(r"\s+", " ", str(row["decision_text"]).casefold())
            if source_outcome == "time_penalty":
                seconds = _number_before(decision, r"seconds?(?:\s+time)?\s+penalty")
                if not seconds:
                    seconds = _number_before(decision, r"second time penalty")
                if not seconds:
                    seconds = _number_before(decision, r"seconds?\s+is\s+imposed")
                if not seconds:
                    raise ValueError(f"Missing time amount: {row['adjudication_instance_id']}")
                if seconds != str(row["penalty_seconds_final"]):
                    corrections["penalty_seconds_final"] = {
                        "before": str(row["penalty_seconds_final"]),
                        "after": seconds,
                    }
                    output.at[index, "penalty_seconds_final"] = seconds
            elif source_outcome == "grid_penalty":
                places = _number_before(decision, r"grid (?:places?|positions?)")
                if not places:
                    places = _number_before(decision, r"grid place (?:drop|penalty)")
                if not places:
                    raise ValueError(f"Missing grid amount: {row['adjudication_instance_id']}")
                if places != str(row["grid_places_final"]):
                    corrections["grid_places_final"] = {
                        "before": str(row["grid_places_final"]),
                        "after": places,
                    }
                    output.at[index, "grid_places_final"] = places
            points = _number_before(decision, r"penalty points?")
            if not points:
                points = _number_before(decision, r"points? awarded")
            if points and points != str(row["penalty_points_final"]):
                corrections["penalty_points_final"] = {
                    "before": str(row["penalty_points_final"]),
                    "after": points,
                }
                output.at[index, "penalty_points_final"] = points
            model_fault = _model_fault_language(row)
            if model_fault != str(row["fault_language_final"]):
                corrections["fault_language_final"] = {
                    "before": str(row["fault_language_final"]),
                    "after": model_fault,
                }
                output.at[index, "fault_language_final"] = model_fault
        elif not str(row["exclusion_reason_final"]).strip():
            raise ValueError(
                f"Excluded adjudication lacks reason: {row['adjudication_instance_id']}"
            )

        final_row = output.loc[index]
        final_included = str(final_row["include_primary_final"]).casefold() == "true" or str(
            final_row["include_secondary_final"]
        ).casefold() == "true"
        document = document_lookup.loc[row["document_id"]]
        if final_included:
            if str(document["eligibility_final"]) != "include":
                raise ValueError(
                    f"Included adjudication links to excluded document: "
                    f"{row['adjudication_instance_id']}"
                )
            if str(final_row["incident_family_final"]) != str(document["offence_family_final"]):
                raise ValueError(
                    f"Adjudication/document family mismatch: {row['adjudication_instance_id']}"
                )
            primary = str(final_row["include_primary_final"]).casefold() == "true"
            secondary = str(final_row["include_secondary_final"]).casefold() == "true"
            if primary == secondary:
                raise ValueError(
                    f"Included adjudication must enter exactly one population: "
                    f"{row['adjudication_instance_id']}"
                )
            expected_scope = "primary" if primary else "secondary"
            if str(document["session_scope_final"]) != expected_scope:
                raise ValueError(
                    f"Adjudication/document session mismatch: {row['adjudication_instance_id']}"
                )
            required = (
                "adjudication_id_final",
                "incident_id_final",
                "accused_driver_number_final",
                "session_type_final",
                "incident_family_final",
                "outcome_family_final",
                "fault_language_final",
            )
            if any(not str(final_row[field]).strip() for field in required):
                raise ValueError(
                    f"Included adjudication is structurally incomplete: "
                    f"{row['adjudication_instance_id']}"
                )
        elif str(document["eligibility_final"]) == "include":
            raise ValueError(
                "Included document lacks an included adjudication: "
                f"{row['adjudication_instance_id']}"
            )

        status = "model_reviewed_corrected" if corrections else "model_reviewed_agree"
        output.at[index, "coder_id"] = REVIEWER_ID
        output.at[index, "review_status"] = status
        output.at[index, "coding_notes"] = _append_note(
            row["coding_notes"],
            "GPT-5.6 Sol checked scope, roles, outcome, sanction fields, and written "
            "responsibility against the official extracted evidence. Model review only; no "
            "independent human review.",
        )
        audits.append(
            {
                "queue": "adjudications",
                "row_id": row["adjudication_instance_id"],
                "document_id": row["document_id"],
                "source_url": row["source_url"],
                "source_evidence_sha256": _evidence_hash(row),
                "prior_review_status": row["review_status"],
                "prior_reviewer_id": row["coder_id"],
                "model_decision": "corrected" if corrections else "agree",
                "model_review_status": status,
                "corrected_fields_json": _canonical_json(corrections),
                "evidence_basis": "official_decision_sections",
                "review_path": "decision_sections_and_cross_queue_validation",
                "rationale": (
                    "One or more final fields were corrected from explicit decision or reason text."
                    if corrections
                    else "Final case fields agree with the source-grounded review rules."
                ),
                "independent_human_review": False,
            }
        )
    return output, audits


def _review_exclusion_qa(
    exclusion_qa: pd.DataFrame,
    reviewed_documents: pd.DataFrame,
    source_lookup: pd.DataFrame,
    settings: dict[str, Any],
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    output = exclusion_qa.copy()
    documents = reviewed_documents.set_index("document_id")
    audits: list[dict[str, Any]] = []
    for index, row in output.iterrows():
        document = documents.loc[row["document_id"]].copy()
        document["document_id"] = row["document_id"]
        source_coding = _source_only_document_coding(document, source_lookup, settings)
        source_excludes = bool(source_coding["source_excludes"])
        independently_classified_exclusion = str(source_coding["eligibility"]) in (
            DETERMINISTIC_EXCLUDE
        )
        if (
            str(document["eligibility_final"]) != "exclude"
            or not source_excludes
            or not independently_classified_exclusion
        ):
            raise ValueError(f"False exclusion found in QA sample: {row['exclusion_qa_id']}")
        output.at[index, "qa_disposition"] = "confirmed_exclusion"
        output.at[index, "corrected_session_scope"] = ""
        output.at[index, "corrected_offence_family"] = ""
        output.at[index, "reviewer_id"] = REVIEWER_ID
        output.at[index, "review_status"] = "model_reviewed_agree"
        output.at[index, "review_notes"] = (
            "GPT-5.6 Sol checked the sampled exclusion against the linked source-coded document "
            "disposition and frozen scope. Model review only; no independent human review."
        )
        audits.append(
            {
                "queue": "exclusion_qa",
                "row_id": row["exclusion_qa_id"],
                "document_id": row["document_id"],
                "source_url": row["source_url"],
                "source_evidence_sha256": source_coding["source_evidence_sha256"],
                "prior_review_status": row["review_status"],
                "prior_reviewer_id": row["reviewer_id"],
                "model_decision": "agree",
                "model_review_status": "model_reviewed_agree",
                "corrected_fields_json": "{}",
                "evidence_basis": "separate_source_text_reclassification",
                "review_path": "blind_frozen_scope_reclassification",
                "rationale": "A separate source-text pass places the sampled record outside the "
                "frozen analytical scope.",
                "independent_human_review": False,
            }
        )
    return output, audits


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False, lineterminator="\n")


def _output_entry(path: Path) -> dict[str, Any]:
    return {
        "row_count": len(pd.read_csv(path, dtype=str, keep_default_na=False)),
        "sha256": _sha256(path.read_bytes()),
    }


def main() -> None:
    protocol_bytes = PROTOCOL_PATH.read_bytes()
    implementation_bytes = Path(__file__).read_bytes()
    source_files = [
        SOURCE / name
        for name in (MANIFEST_FILE, DOCUMENT_FILE, ADJUDICATION_FILE, QA_FILE)
    ]
    parent_digest = _sha256(
        b"\n".join(path.name.encode("utf-8") + b":" + path.read_bytes() for path in source_files)
    )
    run_id = "model-review-" + _sha256(
        (
            PROTOCOL_VERSION
            + "\n"
            + MODEL_ID
            + "\n"
            + parent_digest
            + "\n"
            + _sha256(implementation_bytes)
            + "\n"
        ).encode("utf-8")
        + protocol_bytes
    )[:12]
    run_directory = RUN_ROOT / run_id
    workspace_directory = WORKSPACE_ROOT / run_id / SOURCE.name
    if run_directory.exists() or workspace_directory.exists():
        raise FileExistsError(f"Refusing to overwrite existing model review: {run_id}")
    run_directory.mkdir(parents=True)
    workspace_directory.mkdir(parents=True)

    documents = pd.read_csv(SOURCE / DOCUMENT_FILE, dtype=str, keep_default_na=False)
    adjudications = pd.read_csv(SOURCE / ADJUDICATION_FILE, dtype=str, keep_default_na=False)
    exclusion_qa = pd.read_csv(SOURCE / QA_FILE, dtype=str, keep_default_na=False)
    source_text = _load_source_text().set_index("document_id")
    settings = load_full_corpus_coding_settings()
    reviewed_documents, document_audit = _review_documents(documents, source_text, settings)
    reviewed_adjudications, adjudication_audit = _review_adjudications(
        adjudications,
        reviewed_documents,
    )
    reviewed_qa, qa_audit = _review_exclusion_qa(
        exclusion_qa,
        reviewed_documents,
        source_text,
        settings,
    )
    audit = pd.DataFrame(document_audit + adjudication_audit + qa_audit)

    if len(audit) != 4_441 or audit["row_id"].duplicated().any():
        raise ValueError("Model review must cover exactly 4,441 unique queue obligations")
    if audit["model_review_status"].eq("model_review_unresolved").any():
        raise ValueError("Unresolved model reviews cannot enter the release")
    if audit["source_evidence_sha256"].str.fullmatch(r"[0-9a-f]{64}").fillna(False).sum() != len(
        audit
    ):
        raise ValueError("Every review obligation must preserve a source-evidence hash")
    if len(source_text) != 1_984:
        raise ValueError(f"Expected 1,984 source-text records, found {len(source_text)}")

    shutil.copy2(SOURCE / MANIFEST_FILE, workspace_directory / MANIFEST_FILE)
    _write_csv(reviewed_documents, workspace_directory / DOCUMENT_FILE)
    _write_csv(reviewed_adjudications, workspace_directory / ADJUDICATION_FILE)
    _write_csv(reviewed_qa, workspace_directory / QA_FILE)
    _write_csv(audit, run_directory / "model_review_audit.csv")
    shutil.copy2(PROTOCOL_PATH, run_directory / "protocol.md")

    corrections = Counter()
    for payload in audit.loc[audit["model_decision"].eq("corrected"), "corrected_fields_json"]:
        corrections.update(json.loads(payload).keys())
    queue_summary = (
        audit.groupby(["queue", "model_decision"], dropna=False)
        .size()
        .rename("rows")
        .reset_index()
    )
    _write_csv(queue_summary, run_directory / "review_summary.csv")

    completed_at = datetime.now(UTC).isoformat()
    manifest = {
        "schema_version": "disclosed-model-review-run-v1",
        "run_id": run_id,
        "model_id": MODEL_ID,
        "reviewer_id": REVIEWER_ID,
        "protocol_version": PROTOCOL_VERSION,
        "protocol_sha256": _sha256(protocol_bytes),
        "review_implementation_sha256": _sha256(implementation_bytes),
        "review_tier": "disclosed_model_second_pass",
        "independence_claim": "none",
        "independent_human_review": "not_performed",
        "completed_at_utc": completed_at,
        "parent_workspace": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "parent_workspace_sha256": parent_digest,
        "workspace_directory": str(workspace_directory.relative_to(ROOT)).replace("\\", "/"),
        "coverage": {
            "unique_source_records": int(audit["document_id"].nunique()),
            "queue_obligations": len(audit),
            "document_dispositions": len(document_audit),
            "adjudication_codings": len(adjudication_audit),
            "exclusion_qa": len(qa_audit),
            "unresolved": 0,
            "source_text_records": len(source_text),
            "linked_recalled_predecessors_without_binary": int(
                (
                    ~reviewed_documents["document_id"].isin(source_text.index)
                    & reviewed_documents["successor_document_id"].str.strip().ne("")
                ).sum()
            ),
            "metadata_only_unresolved_sources": int(
                audit["model_decision"].eq("agree_metadata_only").sum()
            ),
        },
        "correction_counts_by_field": dict(sorted(corrections.items())),
        "outputs": {},
        "limitations": [
            "The second pass was performed by GPT-5.6 Sol, not an independent human reviewer.",
            "Model and first-pass errors can be correlated.",
            "Four recalled source binaries remain unavailable; their version exclusions use "
            "archive metadata.",
            "A completed model review does not make descriptive associations causal findings.",
        ],
    }
    for path in sorted(run_directory.iterdir()):
        if path.name != "manifest.json":
            manifest["outputs"][path.name] = {
                "sha256": _sha256(path.read_bytes()),
                "bytes": path.stat().st_size,
            }
    for name in (DOCUMENT_FILE, ADJUDICATION_FILE, QA_FILE):
        manifest["outputs"][f"reviewed_workspace/{name}"] = _output_entry(
            workspace_directory / name
        )
    (run_directory / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
